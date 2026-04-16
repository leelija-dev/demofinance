import os
import json
import logging
import pandas as pd

from decimal import Decimal, InvalidOperation
from datetime import datetime, date
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.views import View
from django.utils import timezone
from rest_framework import status
from django.contrib import messages
from django.shortcuts import render, redirect
from rest_framework.views import APIView
from django.core.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

# Import HQ authentication decorators
from agent.models import Agent
from branch.models import BranchTransaction, BranchAccount
from headquater.models import Branch, HeadquarterEmployee
from headquater.decorators import require_super_admin

# Import models
from loan.models import (
    LoanApplication, CustomerDetail, CustomerAddress, CustomerAccount,
    CustomerLoanDetail, LoanEMISchedule, LoanCategory, LoanInterest, LoanTenure,
    Product, Shop, ShopBankAccount, CustomerDocument, DisbursementLog, EmiCollectionDetail
)

# Set up logging
logger = logging.getLogger(__name__)

def validate_required_columns(df):
    """Validate that required columns are present in the Excel file"""
    required_columns = [
        'customer_type', 'full_name', 'date_of_birth', 'gender', 'contact', 'adhar_number',
        'address_line_1', 'city_or_town', 'district', 'state', 'post_code',
        'current_address_line_1', 'current_city_or_town', 'current_district', 'current_state', 'current_post_code',
        'account_number', 'bank_name', 'ifsc_code', 'account_type',
        'loan_category_name', 'loan_amount', 'tenure_value', 'tenure_unit', 
        'loan_purpose', 'interest_rate', 'emi_amount', 'branch_name'
    ]
    
    # Optional columns (nullable fields from new application form)
    optional_columns = [
        'father_name', 'guarantor_name', 'email', 'pan_number', 'voter_number',
        'address_line_2', 'landmark', 'post_office', 'country',
        'current_address_line_2', 'current_landmark', 'current_post_office', 'current_country', 'residential_proof_type',
        'product_main_category', 'product_subcategory', 'product_name', 'sale_price', 'loan_percentage', 'down_payment',
        'shop_id', 'shop_bank_account_number',
        'emi_start_date', 'emi_frequency',
        # Document file paths (optional)
        'id_proof_path', 'id_proof_back_path', 'guarantor_id_proof_path', 'pan_card_document_path',
        'photo_path', 'signature_path', 'income_proof_path', 'collateral_path', 'residential_proof_file_path',
        # Application status and timeline (optional)
        'application_status', 'approved_at', 'disbursed_at', 'rejection_reason', 'document_request_reason',
        'ever_branch_approved', 'submitted_at',
        # Disbursement information (optional)
        'disbursement_amount', 'disbursement_mode', 'disbursement_bank_name', 'disbursement_account_number',
        'disbursement_net_amount', 'disbursement_tax_charges', 'disbursement_proof', 'disbursement_remarks',
        'disbursement_branch_account_number', 'disbursement_shop_bank_account_number', 'disbursement_date',
        # EMI collection information (optional)
        'emi_collected_amount', 'emi_principal_received', 'emi_interest_received', 'emi_penalty_received',
        'emi_payment_mode', 'emi_payment_reference', 'emi_collected_at', 'emi_collected_by_agent',
        'emi_collection_remarks', 'emi_status',
        # Branch transaction information (optional)
        'branch_transaction_type', 'branch_transaction_amount', 'branch_transaction_purpose',
        'branch_transaction_code', 'branch_transaction_mode', 'branch_transaction_description',
        'branch_transaction_date', 'branch_transaction_account_number'
    ]
    
    # Check required columns
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    # Log which optional columns are available
    available_optional = [col for col in optional_columns if col in df.columns]
    if available_optional:
        logger.info(f"Optional columns found in Excel: {', '.join(available_optional)}")
    
    return missing_columns

def validate_data_types(row_data):
    """Validate data types and formats"""
    errors = []
    
    # Validate date format
    if row_data.get('date_of_birth'):
        try:
            pd.to_datetime(row_data['date_of_birth']).date()
        except:
            errors.append("Invalid date_of_birth format. Use YYYY-MM-DD")
    
    # Validate email if provided
    if row_data.get('email'):
        try:
            from django.core.validators import validate_email
            validate_email(row_data['email'])
        except ValidationError:
            errors.append("Invalid email format")
    
    # Validate phone number
    if row_data.get('contact'):
        contact = str(row_data['contact'])
        if not contact.isdigit() or len(contact) < 10:
            errors.append("Contact must be a valid 10-digit phone number")
    
    # Validate Aadhar number
    if row_data.get('adhar_number'):
        aadhar = str(row_data['adhar_number'])
        if not aadhar.isdigit() or len(aadhar) != 12:
            errors.append("Aadhar number must be 12 digits")
    
    # Validate monetary values
    for field in ['loan_amount', 'emi_amount', 'interest_rate']:
        if row_data.get(field):
            try:
                Decimal(str(row_data[field]))
            except (InvalidOperation, ValueError):
                errors.append(f"Invalid {field} format. Use decimal numbers")
    
    # Validate application status if provided
    if row_data.get('application_status'):
        status = str(row_data['application_status'])
        valid_statuses = [choice[0] for choice in LoanApplication.STATUS_CHOICES]
        if status not in valid_statuses:
            errors.append(f"Invalid application_status. Valid options: {', '.join(valid_statuses)}")
    
    # Validate timeline dates if provided
    for date_field in ['approved_at', 'disbursed_at', 'submitted_at']:
        if row_data.get(date_field):
            try:
                pd.to_datetime(row_data[date_field]).date()
            except:
                errors.append(f"Invalid {date_field} format. Use YYYY-MM-DD")
    
    # Validate disbursement fields if provided
    if row_data.get('disbursement_amount'):
        try:
            amount = Decimal(str(row_data['disbursement_amount']))
            if amount <= 0:
                errors.append("Disbursement amount must be positive")
        except (InvalidOperation, ValueError):
            errors.append("Invalid disbursement_amount format. Use decimal numbers")
    
    if row_data.get('disbursement_net_amount'):
        try:
            amount = Decimal(str(row_data['disbursement_net_amount']))
            if amount <= 0:
                errors.append("Disbursement net amount must be positive")
        except (InvalidOperation, ValueError):
            errors.append("Invalid disbursement_net_amount format. Use decimal numbers")
    
    # Validate disbursement mode if provided
    if row_data.get('disbursement_mode'):
        mode = str(row_data['disbursement_mode'])
        valid_modes = ['Cash', 'Bank Transfer', 'UPI', 'Cheque']
        if mode not in valid_modes:
            errors.append(f"Invalid disbursement_mode. Valid options: {', '.join(valid_modes)}")
    
    # Validate EMI collection fields if provided
    if row_data.get('emi_collected_amount'):
        try:
            amount = Decimal(str(row_data['emi_collected_amount']))
            if amount <= 0:
                errors.append("EMI collected amount must be positive")
        except (InvalidOperation, ValueError):
            errors.append("Invalid emi_collected_amount format. Use decimal numbers")
    
    # Validate EMI payment mode if provided
    if row_data.get('emi_payment_mode'):
        mode = str(row_data['emi_payment_mode'])
        valid_modes = ['Cash', 'Bank Transfer', 'UPI', 'Cheque']
        if mode not in valid_modes:
            errors.append(f"Invalid emi_payment_mode. Valid options: {', '.join(valid_modes)}")
    
    # Validate EMI status if provided
    if row_data.get('emi_status'):
        status = str(row_data['emi_status'])
        valid_statuses = ['pending', 'collected', 'verified', 'rejected']
        if status not in valid_statuses:
            errors.append(f"Invalid emi_status. Valid options: {', '.join(valid_statuses)}")
    
    # Validate branch transaction fields if provided
    if row_data.get('branch_transaction_amount'):
        try:
            amount = Decimal(str(row_data['branch_transaction_amount']))
            if amount <= 0:
                errors.append("Branch transaction amount must be positive")
        except (InvalidOperation, ValueError):
            errors.append("Invalid branch_transaction_amount format. Use decimal numbers")
    
    # Validate branch transaction type if provided
    if row_data.get('branch_transaction_type'):
        trans_type = str(row_data['branch_transaction_type'])
        valid_types = ['CREDIT', 'DEBIT']
        if trans_type not in valid_types:
            errors.append(f"Invalid branch_transaction_type. Valid options: {', '.join(valid_types)}")
    
    # Validate boolean fields if provided
    if row_data.get('ever_branch_approved'):
        boolean_value = str(row_data['ever_branch_approved']).lower()
        if boolean_value not in ['true', 'false', '1', '0', 'yes', 'no', 'y', 'n', '']:
            errors.append("Invalid ever_branch_approved. Use true/false, 1/0, yes/no")
    
    return errors

def get_or_create_reference(model, field_name, value, **kwargs):
    """Helper to get or create reference objects"""
    if not value or pd.isna(value):
        return None
    
    try:
        return model.objects.get(**{field_name: value, **kwargs})
    except model.DoesNotExist:
        logger.warning(f"Reference not found: {model.__name__} {field_name}={value}")
        return None

def copy_document_file(source_path, destination_path):
    """Helper to copy document files from source to destination"""
    if not source_path or pd.isna(source_path):
        return None
    
    try:
        import shutil
        from django.conf import settings
        
        # Ensure source path exists
        if not os.path.exists(source_path):
            logger.warning(f"Source document file not found: {source_path}")
            return None
        
        # Create destination directory if it doesn't exist
        dest_dir = os.path.dirname(destination_path)
        if dest_dir and not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)
        
        # Copy the file
        shutil.copy2(source_path, destination_path)
        logger.info(f"Document copied: {source_path} -> {destination_path}")
        return destination_path
        
    except Exception as e:
        logger.error(f"Error copying document from {source_path} to {destination_path}: {str(e)}")
        return None

def process_document_upload(row_data, loan_application, agent, branch):
    """Process document uploads from Excel file paths"""
    try:
        document_data = {
            'loan_application': loan_application,
            'agent': agent,
            'branch': branch,
        }
        
        # Process each document if path is provided
        document_fields = {
            'id_proof': 'id_proof_path',
            'id_proof_back': 'id_proof_back_path',
            'guarantor_id_proof': 'guarantor_id_proof_path',
            'pan_card_document': 'pan_card_document_path',
            'photo': 'photo_path',
            'signature': 'signature_path',
            'income_proof': 'income_proof_path',
            'collateral': 'collateral_path',
            'residential_proof_file': 'residential_proof_file_path'
        }
        
        documents_created = False
        for field_name, path_column in document_fields.items():
            source_path = row_data.get(path_column)
            if source_path and pd.notna(source_path):
                # Generate destination path based on field type
                from django.conf import settings
                import uuid
                
                file_extension = os.path.splitext(source_path)[1]
                if not file_extension:
                    file_extension = '.jpg'  # Default extension
                
                unique_filename = f"{uuid.uuid4().hex}{file_extension}"
                
                # Determine upload path based on document type
                upload_paths = {
                    'id_proof': f'static/customer/id_proof/{unique_filename}',
                    'id_proof_back': f'static/customer/id_proof/{unique_filename}',
                    'guarantor_id_proof': f'static/customer/guarantor_id_proof/{unique_filename}',
                    'pan_card_document': f'static/customer/pan_card/{unique_filename}',
                    'photo': f'static/customer/photo/{unique_filename}',
                    'signature': f'static/customer/signature/{unique_filename}',
                    'income_proof': f'static/customer/income_proof/{unique_filename}',
                    'collateral': f'static/customer/collateral/{unique_filename}',
                    'residential_proof_file': f'static/customer/residential_proof/{unique_filename}'
                }
                
                destination_path = upload_paths.get(field_name)
                if destination_path:
                    copied_path = copy_document_file(source_path, destination_path)
                    if copied_path:
                        document_data[field_name] = copied_path
                        documents_created = True
        
        # Create CustomerDocument record if any documents were processed
        if documents_created:
            CustomerDocument.objects.create(**document_data)
            logger.info(f"Documents created for loan application {loan_application.loan_ref_no}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing documents for loan application {loan_application.loan_ref_no}: {str(e)}")
        return False

def process_application_status(row_data, loan_application):
    """Process application status and timeline information"""
    try:
        # Update application status if provided
        if pd.notna(row_data.get('application_status')):
            status = str(row_data['application_status'])
            # Validate status against available choices
            valid_statuses = [choice[0] for choice in LoanApplication.STATUS_CHOICES]
            if status in valid_statuses:
                loan_application.status = status
                logger.info(f"Updated loan application {loan_application.loan_ref_no} status to {status}")
            else:
                logger.warning(f"Invalid status '{status}' for loan application {loan_application.loan_ref_no}")
        
        # Update timeline fields
        if pd.notna(row_data.get('approved_at')):
            try:
                loan_application.approved_at = None
                approved_at = pd.to_datetime(row_data['approved_at'])
                if not pd.isnull(approved_at):
                    loan_application.approved_at = timezone.make_aware(approved_at.to_pydatetime())
            except Exception as e:
                logger.warning(f"Invalid approved_at date for {loan_application.loan_ref_no}: {str(e)}")
        
        if pd.notna(row_data.get('disbursed_at')):
            try:
                loan_application.disbursed_at = None
                disbursed_at = pd.to_datetime(row_data['disbursed_at'])
                if not pd.isnull(disbursed_at):
                    loan_application.disbursed_at = timezone.make_aware(disbursed_at.to_pydatetime())
            except Exception as e:
                logger.warning(f"Invalid disbursed_at date for {loan_application.loan_ref_no}: {str(e)}")
        
        if pd.notna(row_data.get('submitted_at')):
            try:
                dt = pd.to_datetime(row_data['submitted_at'])
                if pd.isnull(dt):
                    submitted_at = None
                else:
                    submitted_at = timezone.make_aware(dt.to_pydatetime())
                loan_application.submitted_at = submitted_at
                print("submitted_at", submitted_at)
            except Exception as e:
                logger.warning(f"Invalid submitted_at date for {loan_application.loan_ref_no}: {str(e)}")
        
        # Update reason fields
        if pd.notna(row_data.get('rejection_reason')):
            loan_application.rejection_reason = str(row_data['rejection_reason'])
        
        if pd.notna(row_data.get('document_request_reason')):
            loan_application.document_request_reason = str(row_data['document_request_reason'])
        
        # Update boolean fields
        if pd.notna(row_data.get('ever_branch_approved')):
            ever_approved = str(row_data['ever_branch_approved']).lower()
            loan_application.ever_branch_approved = ever_approved in ['true', '1', 'yes', 'y']
        
        loan_application.save()
        return True
        
    except Exception as e:
        logger.error(f"Error processing application status for {loan_application.loan_ref_no}: {str(e)}")
        return False

def process_disbursement(row_data, loan_application, branch):
    """Process disbursement information and create disbursement log"""
    try:
        # Only process disbursement if amount is provided
        if not pd.notna(row_data.get('disbursement_amount')):
            return True  # No disbursement to process
                
        # Parse disbursement amount
        disbursement_amount = Decimal(str(row_data['disbursement_amount']))
        
        # Parse other disbursement fields
        disbursement_mode = str(row_data.get('disbursement_mode', 'Cash'))
        bank_name = str(row_data.get('disbursement_bank_name', ''))
        account_number = str(row_data.get('disbursement_account_number', ''))
        net_amount = Decimal(str(row_data.get('disbursement_net_amount', disbursement_amount)))
        tax_charges = disbursement_amount - net_amount
        disbursement_proof = str(row_data.get('disbursement_proof', ''))
        remarks = str(row_data.get('disbursement_remarks', ''))
        
        # Parse disbursement date
        disbursement_date = timezone.now().date()
        if pd.notna(row_data.get('disbursement_date')):
            try:
                dt = pd.to_datetime(row_data['disbursement_date'])
                if not pd.isnull(dt):
                    disbursement_date = timezone.make_aware(dt.to_pydatetime())
            except Exception as e:
                logger.warning(f"Invalid disbursement_date, using today: {str(e)}")
        
        # Create disbursement log
        disbursement_log = DisbursementLog.objects.create(
            loan_id=loan_application,
            amount=disbursement_amount,
            disb_mode=disbursement_mode,
            bank_name=bank_name,
            account_number=account_number,
            net_amount_cust=net_amount,
            tax_charges=tax_charges,
            disburse_proof=disbursement_proof,
            remarks=remarks,
            disbursed_by=branch,
            disbursed_to=loan_application
        )
        
        logger.info(f"Created disbursement log {disbursement_log.dis_id} for {loan_application.loan_ref_no}")
        
        # Update loan application status to disbursed
        loan_application.status = 'disbursed'
        loan_application.disbursed_at = disbursement_date
        loan_application.save()
        
        # Process branch transaction if account is provided
        if pd.notna(row_data.get('disbursement_branch_account_number')):
            process_branch_transaction(
                row_data, 
                loan_application, 
                branch, 
                'DEBIT', 
                disbursement_amount, 
                disbursement_log
            )
        
        return True
        
    except Exception as e:
        logger.error(f"Error processing disbursement for {loan_application.loan_ref_no}: {str(e)}")
        return False

def process_emi_collection(row_data, loan_application, agent):
    """Process EMI collection information"""
    try:
        # Only process EMI collection if amount is provided
        if not pd.notna(row_data.get('emi_collected_amount')):
            return True  # No EMI collection to process
        
        
        # Parse EMI collection fields
        amount_received = Decimal(str(row_data['emi_collected_amount']))
        principal_received = Decimal(str(row_data.get('emi_principal_received', 0)))
        interest_received = Decimal(str(row_data.get('emi_interest_received', 0)))
        emi_penalty_received = row_data.get('emi_penalty_received', 0)
        penalty_received = Decimal(str(emi_penalty_received)) if emi_penalty_received else 0.0

        payment_mode = str(row_data.get('emi_payment_mode', 'Cash'))
        payment_reference = str(row_data.get('emi_payment_reference', ''))
        remarks = str(row_data.get('emi_collection_remarks', ''))
        emi_status = str(row_data.get('emi_status', 'collected'))
        
        # Parse collection date
        collected_at = timezone.now()
        if pd.notna(row_data.get('emi_collected_at')):
            try:
                ct = pd.to_datetime(row_data['emi_collected_at'])
                if not pd.isnull(ct):
                    collected_at = timezone.make_aware(ct.to_pydatetime())
            except Exception as e:
                logger.warning(f"Invalid emi_collected_at, using now: {str(e)}")
        
        # Get collecting agent
        collected_by_agent = None
        if pd.notna(row_data.get('emi_collected_by_agent')):
            agent_name = str(row_data['emi_collected_by_agent'])
            collected_by_agent = get_or_create_reference(Agent, 'full_name', agent_name)
        
        # Create EMI collection detail
        emi_collection = EmiCollectionDetail.objects.create(
            loan_application=loan_application,
            collected_by_agent=collected_by_agent,
            amount_received=amount_received,
            principal_received=principal_received,
            interest_received=interest_received,
            penalty_received=penalty_received,
            payment_mode=payment_mode,
            payment_reference=payment_reference,
            collected_at=collected_at,
            remarks=remarks,
            status=emi_status,
            collected=(emi_status == 'collected')
        )
        
        logger.info(f"Created EMI collection {emi_collection.collected_id} for {loan_application.loan_ref_no}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing EMI collection for {loan_application.loan_ref_no}: {str(e)}")
        return False

def process_branch_transaction(row_data, loan_application, branch, transaction_type=None, amount=None, disbursement_log=None):
    """Process branch transaction information"""
    try:
        # Use provided values or parse from row_data
        if transaction_type is None:
            transaction_type = str(row_data.get('branch_transaction_type', 'DEBIT'))
        if amount is None:
            if not pd.notna(row_data.get('branch_transaction_amount')):
                return True  # No transaction amount to process
            amount = Decimal(str(row_data['branch_transaction_amount']))
        
        # Parse transaction fields
        purpose = str(row_data.get('branch_transaction_purpose', 'Loan Transaction'))
        code = str(row_data.get('branch_transaction_code', ''))
        mode = str(row_data.get('branch_transaction_mode', ''))
        description = str(row_data.get('branch_transaction_description', ''))
        
        # Parse transaction date
        transaction_date = timezone.now()
        if pd.notna(row_data.get('branch_transaction_date')):
            try:
                transaction_date = pd.to_datetime(row_data['branch_transaction_date'])
            except Exception as e:
                logger.warning(f"Invalid branch_transaction_date, using now: {str(e)}")
        
        # Get branch account if provided
        branch_account = None
        if pd.notna(row_data.get('branch_transaction_account_number')):
            account_number = str(row_data['branch_transaction_account_number'])
            # Use 'account_number' for more user-friendly lookup
            branch_account = get_or_create_reference(BranchAccount, 'account_number', account_number)
        
        # Create branch transaction
        branch_transaction = BranchTransaction.objects.create(
            branch=branch,
            branch_account=branch_account,
            disbursement_log=disbursement_log,
            transaction_type=transaction_type,
            purpose=purpose,
            code=code,
            mode=mode,
            amount=amount,
            description=description,
            transaction_date=transaction_date,
            loan_application=loan_application,
            agent=loan_application.agent
        )
        
        logger.info(f"Created branch transaction {branch_transaction.transaction_id} for {loan_application.loan_ref_no}")
        return True
        
    except Exception as e:
        logger.error(f"Error processing branch transaction for {loan_application.loan_ref_no}: {str(e)}")
        return False

def process_customer_loan_data(row_data, request):
    """Process a single row of customer and loan data"""
    errors = []
    
    try:
        with transaction.atomic():
            # Validate data types first
            validation_errors = validate_data_types(row_data)
            if validation_errors:
                return None, validation_errors
            
            # Get branch
            branch = get_or_create_reference(Branch, 'branch_name', row_data['branch_name'])
            if not branch:
                errors.append(f"Branch '{row_data['branch_name']}' not found")
                return None, errors
            
            # Get agent if provided
            agent = None
            if pd.notna(row_data.get('agent_name')) and row_data.get('agent_name'):
                agent = get_or_create_reference(Agent, 'full_name', row_data['agent_name'])
                if not agent:
                    errors.append(f"Agent '{row_data['agent_name']}' not found")
                    return None, errors
            
            # Get loan category
            loan_category = get_or_create_reference(LoanCategory, 'name', row_data['loan_category_name'])
            if not loan_category:
                errors.append(f"Loan category '{row_data['loan_category_name']}' not found")
                return None, errors
            
            # Get or create customer
            customer_type = str(row_data['customer_type']).upper()
            if customer_type == 'EXISTING':
                customer = get_or_create_reference(CustomerDetail, 'adhar_number', row_data['adhar_number'])
                if not customer:
                    errors.append(f"Existing customer with Aadhar '{row_data['adhar_number']}' not found")
                    return None, errors
            else:  # NEW customer
                customer_data = {
                    'full_name': str(row_data['full_name']),
                    'father_name': row_data.get('father_name'),
                    'guarantor_name': row_data.get('guarantor_name'),
                    'date_of_birth': pd.to_datetime(row_data['date_of_birth']).date(),
                    'gender': str(row_data['gender']),
                    'contact': str(row_data['contact']),
                    'email': row_data.get('email'),
                    'adhar_number': str(row_data['adhar_number']),
                    'pan_number': row_data.get('pan_number'),
                    'voter_number': row_data.get('voter_number'),
                    'agent': agent,
                    'branch': branch,
                }
                customer = CustomerDetail.objects.create(**customer_data)
            
            # Create or update customer address
            address_data = {
                'customer': customer,
                'address_line_1': str(row_data['address_line_1']),
                'address_line_2': row_data.get('address_line_2'),
                'landmark': row_data.get('landmark'),
                'post_office': row_data.get('post_office'),
                'city_or_town': str(row_data['city_or_town']),
                'district': str(row_data['district']),
                'state': str(row_data['state']),
                'post_code': str(row_data['post_code']),
                'country': row_data.get('country', 'India'),  # Default to India if not provided
                'current_address_line_1': str(row_data['current_address_line_1']),
                'current_address_line_2': row_data.get('current_address_line_2'),
                'current_landmark': row_data.get('current_landmark'),
                'current_post_office': row_data.get('current_post_office'),
                'current_city_or_town': str(row_data['current_city_or_town']),
                'current_district': str(row_data['current_district']),
                'current_state': str(row_data['current_state']),
                'current_post_code': str(row_data['current_post_code']),
                'current_country': row_data.get('current_country', 'India'),  # Default to India if not provided
                'residential_proof_type': row_data.get('residential_proof_type'),
                'agent': agent,
                'branch': branch,
            }
            
            if hasattr(customer, 'address'):
                # Update existing address
                for key, value in address_data.items():
                    if key != 'customer':
                        setattr(customer.address, key, value)
                customer.address.save()
            else:
                # Create new address
                CustomerAddress.objects.create(**address_data)
            
            # Create or update customer account
            account_data = {
                'customer': customer,
                'account_number': str(row_data['account_number']),
                'bank_name': str(row_data['bank_name']),
                'ifsc_code': str(row_data['ifsc_code']),
                'account_type': str(row_data['account_type']),
                'agent': agent,
                'branch': branch,
            }
            
            if hasattr(customer, 'account'):
                # Update existing account
                for key, value in account_data.items():
                    if key != 'customer':
                        setattr(customer.account, key, value)
                customer.account.save()
            else:
                # Create new account
                CustomerAccount.objects.create(**account_data)
            
            # Get loan interest and tenure
            try:
                interest_rate = float(row_data['interest_rate'])
                loan_interest = LoanInterest.objects.filter(
                    main_category=loan_category.main_category,
                    rate_of_interest=interest_rate
                ).first()
                if not loan_interest:
                    errors.append(f"Interest rate {interest_rate}% for category '{loan_category.name}' not found")
                    return None, errors
            except (ValueError, TypeError):
                errors.append(f"Invalid interest rate: {row_data.get('interest_rate')}")
                return None, errors
            
            try:
                tenure_value = int(row_data['tenure_value'])
                tenure_unit = str(row_data['tenure_unit'])
                loan_tenure = LoanTenure.objects.filter(
                    interest_rate=loan_interest,
                    value=tenure_value,
                    unit=tenure_unit
                ).first()
                if not loan_tenure:
                    errors.append(f"Tenure {tenure_value} {tenure_unit} for interest rate {interest_rate}% not found")
                    return None, errors
            except (ValueError, TypeError):
                errors.append(f"Invalid tenure: {row_data.get('tenure_value')} {row_data.get('tenure_unit')}")
                return None, errors
            
            # Handle product and shop information
            product = None
            shop = None
            shop_bank_account = None
            
            # Get product if product information is provided
            if pd.notna(row_data.get('product_name')):
                product = get_or_create_reference(Product, 'name', row_data['product_name'])
            
            # Get shop if shop information is provided
            if pd.notna(row_data.get('shop_id')):
                shop = get_or_create_reference(Shop, 'shop_id', row_data['shop_id'])
                
                # Get shop bank account if provided
                if pd.notna(row_data.get('shop_bank_account_number')):
                    shop_bank_account = get_or_create_reference(ShopBankAccount, 'bank_account_number', row_data['shop_bank_account_number'])
            
            # Create loan application
            loan_application = LoanApplication.objects.create(
                customer=customer,
                branch=branch,
                agent=agent,
                created_by_agent=agent,
                shop=shop,
                shop_bank_account=shop_bank_account,
            )
            
            # Create customer loan details
            loan_detail_data = {
                'loan_application': loan_application,
                'loan_category': loan_category,
                'loan_amount': Decimal(str(row_data['loan_amount'])),
                'tenure': loan_tenure,
                'loan_purpose': str(row_data['loan_purpose']),
                'interest_rate': loan_interest,
                'emi_amount': Decimal(str(row_data['emi_amount'])),
                'product': product,  # Use the product we found earlier
                'loan_percentage': Decimal(str(row_data.get('loan_percentage', 0))) if pd.notna(row_data.get('loan_percentage')) else None,
                'sale_price': Decimal(str(row_data.get('sale_price', 0))) if pd.notna(row_data.get('sale_price')) else None,
                'processing_fee': Decimal(str(row_data.get('processing_fee', 0))) if pd.notna(row_data.get('processing_fee')) else None,
                'down_payment': Decimal(str(row_data.get('down_payment', 0))) if pd.notna(row_data.get('down_payment')) else None,
                'agent': agent,
                'branch': branch,
            }
            CustomerLoanDetail.objects.create(**loan_detail_data)
            
            # Create EMI schedule if dates provided
            if pd.notna(row_data.get('emi_start_date')) and pd.notna(row_data.get('emi_frequency')):
                try:
                    emi_start_date = pd.to_datetime(row_data['emi_start_date']).date()
                    emi_frequency = str(row_data['emi_frequency'])
                    
                    # Calculate number of installments based on tenure
                    if tenure_unit == 'months':
                        num_installments = tenure_value
                    elif tenure_unit == 'years':
                        num_installments = tenure_value * 12
                    elif tenure_unit == 'weeks':
                        num_installments = tenure_value
                    else:  # days
                        num_installments = tenure_value // 30  # Approximate
                    
                    # Create EMI schedule
                    for i in range(num_installments):
                        installment_date = emi_start_date
                        if emi_frequency == 'monthly':
                            installment_date = date(
                                installment_date.year + (installment_date.month + i - 1) // 12,
                                (installment_date.month + i - 1) % 12 + 1,
                                installment_date.day
                            )
                        elif emi_frequency == 'weekly':
                            installment_date = emi_start_date + pd.Timedelta(weeks=i)
                        else:  # daily
                            installment_date = emi_start_date + pd.Timedelta(days=i)
                        
                        loan_amount = Decimal(str(row_data['loan_amount']))
                        installment_amount = Decimal(str(row_data['emi_amount']))
                        
                        LoanEMISchedule.objects.create(
                            loan_application=loan_application,
                            installment_date=installment_date,
                            frequency=emi_frequency,
                            installment_amount=installment_amount,
                            principal_amount=loan_amount / num_installments,
                            interest_amount=installment_amount - (loan_amount / num_installments)
                        )
                except Exception as e:
                    logger.error(f"Error creating EMI schedule: {str(e)}")
                    errors.append(f"Error creating EMI schedule: {str(e)}")
            
            # Process document uploads if paths are provided
            document_success = process_document_upload(row_data, loan_application, agent, branch)
            if not document_success:
                errors.append("Failed to process document uploads")
                return None, errors
            
            # Process application status and timeline information
            status_success = process_application_status(row_data, loan_application)
            if not status_success:
                errors.append("Failed to process application status")
                return None, errors
            
            # Process disbursement information
            disbursement_success = process_disbursement(row_data, loan_application, branch)
            if not disbursement_success:
                errors.append("Failed to process disbursement")
                return None, errors
            
            # Process EMI collection information
            emi_success = process_emi_collection(row_data, loan_application, agent)
            if not emi_success:
                errors.append("Failed to process EMI collection")
                return None, errors
            
            # Process branch transaction information (standalone transactions)
            transaction_success = process_branch_transaction(row_data, loan_application, branch)
            if not transaction_success:
                errors.append("Failed to process branch transaction")
                return None, errors
            
            # Update all relationships after successful import
            update_relationships_after_import(loan_application, customer)
            
            return loan_application, []
    
    except Exception as e:
        logger.error(f"Processing error for row {row_data}: {str(e)}")
        errors.append(f"Processing error: {str(e)}")
        return None, errors

def update_relationships_after_import(loan_application, customer):
    """
    Update all relationships after successful import to ensure proper linking
    between related models
    """
    try:
        # Update CustomerDetail.loan_application relationship
        customer.loan_application = loan_application
        customer.save(update_fields=['loan_application'])
        
        # Update CustomerAddress.loan_application relationship
        if hasattr(customer, 'address'):
            customer.address.loan_application = loan_application
            customer.address.save(update_fields=['loan_application'])
        
        # Update CustomerAccount.loan_application relationship
        if hasattr(customer, 'account'):
            customer.account.loan_application = loan_application
            customer.account.save(update_fields=['loan_application'])
        
        # Update CustomerLoanDetail.loan_application relationship (already set during creation)
        # This is already handled in the main import logic
        
        # Update LoanApplication.customer_snapshot for historical data
        loan_application.populate_customer_snapshot(force=True)
        loan_application.save(update_fields=['customer_snapshot'])
        
        # Update EMI schedules loan_application relationship (already set during creation)
        # This is already handled in the main import logic
        
        logger.info(f"Successfully updated relationships for loan application {loan_application.loan_ref_no}")
        
    except Exception as e:
        logger.error(f"Error updating relationships for loan application {loan_application.loan_ref_no}: {str(e)}")
        # Don't raise exception here as the main import was successful
        # Just log the error for debugging

@method_decorator(require_super_admin, name='dispatch')
class UploadExcelView(View):
    """Handle Excel file upload for customer and loan data"""
    
    def get(self, request):
        return render(request, 'data_import/upload_excel.html')
    
    def post(self, request):
        excel_file = request.FILES.get('excel_file')
        
        if not excel_file:
            messages.error(request, 'Please select an Excel file to upload.')
            return render(request, 'data_import/upload_excel.html')
        
        # Check if file is an Excel file
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, 'Please upload a valid Excel file (.xlsx or .xls).')
            return render(request, 'data_import/upload_excel.html')
        
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Basic validation
            if df.empty:
                messages.error(request, 'The Excel file is empty.')
                return render(request, 'data_import/upload_excel.html')
            
            # Validate required columns
            missing_columns = validate_required_columns(df)
            if missing_columns:
                messages.error(request, f'Missing required columns: {", ".join(missing_columns)}')
                return render(request, 'data_import/upload_excel.html', {
                    'data_preview': df.head(5).to_html(classes='table table-striped'),
                    'total_rows': len(df),
                    'columns': df.columns.tolist(),
                    'missing_columns': missing_columns
                })
            
            # Store DataFrame in session for processing
            request.session['excel_data'] = df.to_dict('records')
            request.session['excel_columns'] = df.columns.tolist()
            
            messages.success(request, f'Successfully uploaded {len(df)} rows from {excel_file.name}. Click "Process Data" to import customer and loan information.')
            return render(request, 'data_import/upload_excel.html', {
                'data_preview': df.head(10).to_html(classes='table table-striped'),
                'total_rows': len(df),
                'columns': df.columns.tolist(),
                'show_process_button': True
            })
            
        except Exception as e:
            logger.error(f"Error reading Excel file: {str(e)}")
            messages.error(request, f'Error reading Excel file: {str(e)}')
            return render(request, 'data_import/upload_excel.html')

@method_decorator(require_super_admin, name='dispatch')
class ProcessExcelDataView(APIView):
    """Process uploaded Excel data and create customer/loan records"""
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        excel_data = request.session.get('excel_data', [])
        
        if not excel_data:
            return Response({
                'success': False,
                'message': 'No data to process. Please upload an Excel file first.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        successful_imports = 0
        failed_imports = 0
        error_details = []
        created_loan_refs = []  # Track all created loan references for potential rollback
        
        try:
            with transaction.atomic():
                # Process all rows within a single transaction
                for index, row_data in enumerate(excel_data, 1):
                    # Clean NaN values
                    print('******************************---------------------------------------------')
                    row_data = {k: (v if pd.notna(v) else None) for k, v in row_data.items()}
                    print('$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$---------------------------------------------')
                    loan_application, errors = process_customer_loan_data(row_data, request)
                    print('##############################---------------------------------------------')
                    
                    if loan_application:
                        successful_imports += 1
                        created_loan_refs.append(loan_application.loan_ref_no)
                    else:
                        failed_imports += 1
                        error_details.append(f"Row {index}: {'; '.join(errors)}")
                        
                        # If any row fails, raise exception to trigger rollback
                        raise Exception(f"Import failed at row {index}: {'; '.join(errors)}")
                
                # If we reach here, all rows processed successfully
                # Transaction commits automatically when exiting atomic block
                
        except Exception as e:
            # Entire transaction rolled back automatically
            failed_imports = len(excel_data)  # All rows failed
            successful_imports = 0
            created_loan_refs = []
            
            error_msg = str(e)
            if "Import failed at row" in error_msg:
                # This was a row-specific failure
                error_details = [error_msg]
            else:
                # This was a system-level failure
                error_details = [f"System error during import: {error_msg}"]
            
            logger.error(f"Batch import failed, all changes rolled back: {error_msg}")
        
        # Clear session data
        request.session.pop('excel_data', None)
        request.session.pop('excel_columns', None)
        
        result_data = {
            'success': successful_imports > 0,
            'successful_imports': successful_imports,
            'failed_imports': failed_imports,
            'error_details': error_details[:10],  # Limit to first 10 errors
            'has_more_errors': len(error_details) > 10,
            'created_loan_refs': created_loan_refs[:5]  # Show what would have been created
        }
        
        if failed_imports > 0:
            result_data['message'] = f'Import failed: all changes have been rolled back due to errors. {successful_imports} records were processed successfully before the failure.'
            if successful_imports > 0:
                result_data['message'] += f' No data was saved to maintain database integrity.'
            else:
                result_data['message'] += ' No data was saved to maintain database integrity.'
        else:
            result_data['message'] = f'Successfully imported {successful_imports} records.'
        
        return Response(result_data, status=status.HTTP_200_OK)

@require_super_admin
def upload_excel(request):
    """Legacy function for backward compatibility"""
    view = UploadExcelView()
    if request.method == 'GET':
        return view.get(request)
    elif request.method == 'POST':
        return view.post(request)
    return render(request, 'data_import/upload_excel.html')

@require_super_admin
def process_excel_data(request):
    """Legacy function for backward compatibility"""
    if request.method == 'POST':
        api_view = ProcessExcelDataView()
        response = api_view.post(request)
        
        # Convert API response to messages for template rendering
        if response.status_code == 200:
            data = response.data
            if data.get('success'):
                messages.success(request, data.get('message', 'Import completed successfully.'))
            else:
                messages.error(request, data.get('message', 'Import completed with errors.'))
            
            if data.get('successful_imports', 0) > 0:
                messages.success(request, f"Successfully imported: {data['successful_imports']} records")
            
            if data.get('failed_imports', 0) > 0:
                messages.error(request, f"Failed to import: {data['failed_imports']} records")
                
                for error in data.get('error_details', []):
                    messages.error(request, error)
                
                if data.get('has_more_errors', False):
                    messages.error(request, f"... and {data['failed_imports'] - 10} more errors.")
            
            return render(request, 'data_import/upload_excel.html', {
                'import_complete': True,
                'successful_imports': data.get('successful_imports', 0),
                'failed_imports': data.get('failed_imports', 0),
                'error_details': data.get('error_details', [])
            })
        else:
            messages.error(request, 'Error processing data.')
            return redirect('data_import:upload_excel')
    
    return redirect('data_import:upload_excel')

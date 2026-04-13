from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
import pandas as pd
import os
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
import json
import logging

# Import HQ authentication decorators
from headquater.decorators import require_super_admin

# Import models
from loan.models import (
    LoanApplication, CustomerDetail, CustomerAddress, CustomerAccount,
    CustomerLoanDetail, LoanEMISchedule, LoanCategory, LoanInterest, LoanTenure,
    Product, Shop, ShopBankAccount
)
from headquater.models import Branch, HeadquarterEmployee
from agent.models import Agent

# Set up logging
logger = logging.getLogger(__name__)

def validate_required_columns(df):
    """Validate that required columns are present in DataFrame"""
    required_columns = [
        'customer_type', 'full_name', 'date_of_birth', 'gender', 'contact', 
        'adhar_number', 'address_line_1', 'city_or_town', 'district', 'state', 'post_code',
        'current_address_line_1', 'current_city_or_town', 'current_district', 'current_state', 'current_post_code',
        'account_number', 'bank_name', 'ifsc_code', 'account_type',
        'loan_category_name', 'loan_amount', 'tenure_value', 'tenure_unit', 
        'loan_purpose', 'interest_rate', 'emi_amount', 'branch_name'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
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
                'current_address_line_1': str(row_data['current_address_line_1']),
                'current_address_line_2': row_data.get('current_address_line_2'),
                'current_landmark': row_data.get('current_landmark'),
                'current_city_or_town': str(row_data['current_city_or_town']),
                'current_district': str(row_data['current_district']),
                'current_state': str(row_data['current_state']),
                'current_post_code': str(row_data['current_post_code']),
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
            
            # Create loan application
            loan_application = LoanApplication.objects.create(
                customer=customer,
                branch=branch,
                agent=agent,
                created_by_agent=agent,
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
                'product': None,
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
            
            return loan_application, []
    
    except Exception as e:
        logger.error(f"Processing error for row {row_data}: {str(e)}")
        errors.append(f"Processing error: {str(e)}")
        return None, errors

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
                    row_data = {k: (v if pd.notna(v) else None) for k, v in row_data.items()}
                    
                    loan_application, errors = process_customer_loan_data(row_data, request)
                    
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

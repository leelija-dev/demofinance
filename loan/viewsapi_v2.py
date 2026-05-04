import os
import re
import sys
import base64
import asyncio
import subprocess

from django.conf import settings
from django.shortcuts import get_object_or_404
from playwright.async_api import async_playwright
from django.template.loader import render_to_string
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from typing import Optional, Union
from decimal import Decimal, InvalidOperation
from datetime import date,datetime
from zoneinfo import ZoneInfo
from django.db import transaction, IntegrityError
from django.http import QueryDict
from agent.models import Agent
from django.utils import timezone
from branch.models import BranchEmployee, BranchTransaction
from rest_framework import status
from django.core.mail import EmailMultiAlternatives
from django.http.request import MultiValueDict
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from loan.models import (
    CustomerDetail, CustomerAddress, CustomerLoanDetail, CustomerDocument,
    LoanCategory, LoanInterest, LoanApplication, LoanPeriod, LoanTenure,
    CustomerAccount, Product, Shop, ShopBankAccount
)



class ShopBankAccountsAPI(APIView):
    """API to get bank accounts for a specific shop"""

    def get(self, request, *args, **kwargs):
        shop_id = request.GET.get('shop_id')
        if not shop_id:
            return Response({
                'success': False,
                'message': 'shop_id parameter is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Get the shop
            shop = Shop.objects.get(shop_id=shop_id, status='active')

            # Get active bank accounts for this shop
            bank_accounts = ShopBankAccount.objects.filter(
                shop=shop,
                status='active'
            ).select_related('bank').values(
                'bank_account_id',
                'account_number',
                'bank__name'
            )

            # Format the response
            data = []
            for account in bank_accounts:
                data.append({
                    'bank_account_id': account['bank_account_id'],
                    'account_number': account['account_number'],
                    'bank_name': account['bank__name']
                })

            return Response({
                'success': True,
                'data': data
            })

        except Shop.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Shop not found or inactive'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"Error fetching shop bank accounts: {str(e)}")
            return Response({
                'success': False,
                'message': 'Internal server error'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NewLoanApplicationAPIV2(APIView):
    parser_classes = (MultiPartParser, FormParser)

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        max_retries = 3
        retry_delay = 0.1  # seconds

        print(request.data)
        print(request.FILES)
        
        for attempt in range(max_retries):
            try:
                data: QueryDict = request.data
                files: MultiValueDict = request.FILES
                errors = {}
                existing_customer: Optional[CustomerDetail] = self._get_customer_detail(data)

                same_address = self._validate_data_fields(data, files, errors)

                account_number, bank_name, ifsc_code = self._validate_bank_details(data, errors, existing_customer)
                # Account type is optional - no validation needed if empty
                account_type = data.get('account_type')


                self._check_duplicate_customer_identity(data, errors) if not existing_customer else None

                loan_amount_decimal, interest_instance, emi_amount_decimal = self._loan_and_emi_validation(data, errors)

                post_code, current_post_code = self._post_code_validation(data, errors, same_address) 

                # Validate ForeignKeys
                loan_category_instance, interest_instance, tenure_instance = self._get_valid_instances(data, errors)

                # Set rate_of_interest_decimal from interest_instance
                rate_of_interest_decimal = interest_instance.rate_of_interest if interest_instance else None

                # Check required document files
                self._check_required_document_files(files, errors)

                # Check if got any error then return response with the errors
                if errors:
                    return Response({'success': False, 'errors': errors}, status=400)
                # import time
                # time.sleep(5)
                # return Response({'success': False, 'errors': {}}, status=400)

                # All validation passed, now create objects
                with transaction.atomic():
                    agent_id, agent, created_by_agent, branch_manager_id, branch, created_by_branch_manager = self._check_authentication(request)
                    if not agent_id and not branch_manager_id:
                        return Response({'success': False, 'message': 'Authentication required.'}, status=400)

                    # Handle address fields based on same_address flag
                    current_address_line_1 = data['address_line_1'] if same_address else data['current_address_line_1']
                    current_address_line_2 = data.get('address_line_2') if same_address else data.get('current_address_line_2')
                    current_state = data['state'] if same_address else data['current_state']
                    current_post_code = data['post_code'] if same_address else data['current_post_code']


                    # Get Product data
                    product_id, product = self._get_product_data(data)

                    # Convert date_of_birth string to date object
                    date_of_birth = self._convert_date_of_birth(data['date_of_birth'])

                    # Save Customer Details
                    customer = self._save_customer(data, date_of_birth, branch, agent, existing_customer)

                    ########### Loan Application Data   ------------------------------------------------------
                    loan_application_kwargs = dict(
                        customer=customer,
                        status='pending',
                        branch=branch,
                        rejection_reason='',
                        document_request_reason='',
                    )
                    if agent_id and agent:
                        loan_application_kwargs['agent'] = agent
                        loan_application_kwargs['created_by_agent'] = created_by_agent
                    if branch_manager_id and created_by_branch_manager:
                        loan_application_kwargs['created_by_branch_manager'] = created_by_branch_manager
                    ## validate and populate shop_data
                    _get_shop_data = self._validate_and_populate_shop_data(
                        data,
                        agent,
                        branch,
                        loan_category_instance,
                        loan_application_kwargs,
                    )
                    if _get_shop_data:
                        return _get_shop_data

                    # Save Loan Application Data
                    loan_application:LoanApplication = LoanApplication.objects.create(**loan_application_kwargs)

                    #Update Loan Application in the Customer Details Model
                    customer.loan_application = loan_application
                    customer.save()




                










                
                    # Create or update Customer address ------------------------------------------ 
                    address_kwargs = dict(
                        loan_application=loan_application,
                        customer=customer,
                        address_line_1=data['address_line_1'],
                        address_line_2=data.get('address_line_2'),
                        landmark=data.get('landmark'),
                        post_office=data.get('post_office'),
                        city_or_town=data.get('city_or_town'),
                        district=data.get('district'),
                        state=data['state'],
                        country=data.get('country', 'India'),
                        post_code=data['post_code'],
                        current_address_line_1=current_address_line_1,
                        current_address_line_2=current_address_line_2,
                        current_landmark=data.get('current_landmark'),
                        current_post_office=data.get('current_post_office'),
                        current_city_or_town=data.get('current_city_or_town'),
                        current_district=data.get('current_district'),
                        current_state=current_state,
                        current_country=data.get('current_country', 'India'),
                        current_post_code=current_post_code,
                        residential_proof_type=data.get('residential_proof_type'),
                        branch=branch
                    )
                    if agent:
                        address_kwargs['agent'] = agent

                    if existing_customer:
                        existing_address = CustomerAddress.objects.filter(customer=customer).first()
                        if existing_address:
                            existing_address.__dict__.update(**address_kwargs)
                            existing_address.save()
                        else:
                            CustomerAddress.objects.create(**address_kwargs)
                    else:
                        CustomerAddress.objects.create(**address_kwargs)




                    ##  Create Loan Details ----------------------------------------
                    loan_detail_kwargs = dict(
                        loan_application=loan_application,
                        loan_category=loan_category_instance,
                        loan_amount=loan_amount_decimal,
                        sale_price=data['sale_price'],
                        processing_fee=data['total_processing_fees'][1:].replace(',', ''),
                        processing_fee_snapshot=data['processing_fees_data'],
                        down_payment=data['down_payment'],
                        tenure=tenure_instance,
                        loan_purpose=data['loan_purpose'],
                        interest_rate=interest_instance,
                        emi_amount=emi_amount_decimal,
                        branch=branch
                    )
                    

                    loan_percentage_str = data.get('loan_percentage')
                    loan_percentage = None
                    if loan_percentage_str and loan_percentage_str.strip():
                        try:
                            loan_percentage = Decimal(loan_percentage_str)
                        except (ValueError, TypeError, InvalidOperation):
                            loan_percentage = None
                    if agent:
                        loan_detail_kwargs['agent'] = agent
                    CustomerLoanDetail.objects.create(**loan_detail_kwargs, product=product, loan_percentage=loan_percentage)

                    LoanPeriod.objects.create(
                        loan_application=loan_application,
                        loan_amount=loan_amount_decimal,
                        rate_of_interest=rate_of_interest_decimal,
                        installment_size=emi_amount_decimal,
                        realizable_amount=emi_amount_decimal * Decimal(tenure_instance.value),
                        number_of_installments=tenure_instance.value,
                        remaining_balance=0,
                        remaining_principal=0,
                        remaining_interest=0,
                    )
                    # document_kwargs = dict(
                    #     loan_application=loan_application,
                    #     id_proof=files.get('id_proof'),
                    #     income_proof=files.get('income_proof'),
                    #     photo=files.get('photo'),
                    document_kwargs = dict(
                        loan_application=loan_application,
                        guarantor_id_proof=files.get('guarantor_id_proof'),
                        id_proof=files.get('id_proof'),
                        id_proof_back=files.get('id_proof_back'),
                        photo=files.get('photo'),
                        signature=files.get('signature'),
                        collateral=files.get('collaterol'),
                        residential_proof_file=files.get('residential_proof_file'),
                        branch=branch
                    )
                    # Only add income_proof if provided
                    if files.get('income_proof'):
                        document_kwargs['income_proof'] = files.get('income_proof')

                    # Only add PAN card document if provided
                    if files.get('pan_card_document'):
                        document_kwargs['pan_card_document'] = files.get('pan_card_document')
                        
                    if agent:
                        document_kwargs['agent'] = agent
                    CustomerDocument.objects.create(**document_kwargs)


                    # Only create CustomerAccount if at least one bank field is provided
                    if account_number or bank_name or ifsc_code or account_type:
                        account_kwargs = {
                            'loan_application': loan_application,
                            'customer': customer,
                            'branch': branch,
                        }
                        
                        if agent:
                            account_kwargs['agent'] = agent
                        
                        # Only add non-empty values
                        if account_number:
                            account_kwargs['account_number'] = account_number
                        if bank_name:
                            account_kwargs['bank_name'] = bank_name
                        if ifsc_code:
                            account_kwargs['ifsc_code'] = ifsc_code
                        if account_type:
                            account_kwargs['account_type'] = account_type
                        
                        if existing_customer:
                            existing_account = CustomerAccount.objects.filter(customer=customer).first()
                            if existing_account:
                                existing_account.__dict__.update(**account_kwargs)
                                existing_account.save()
                            else:
                                CustomerAccount.objects.create(**account_kwargs)
                        else:
                            CustomerAccount.objects.create(**account_kwargs)



                    #  Takking Customer detaiails snapshot ------------------------------------------------
                    

                    loan_application.populate_customer_snapshot()        # or force=True
                    loan_application.save(update_fields=['customer_snapshot'])


                    # Down Payment in shop ----------------------------------------------------------
                    if product_id and product:
                        print("data['down_payment'] ->", data['down_payment'])
                        BranchTransaction.objects.create(
                            branch=branch if branch_manager_id else agent.branch,
                            transaction_type='CREDIT',
                            purpose=f"Down Payment - {product.name}",
                            code="DOWN_PAYMENT",
                            mode="CASH",
                            bank_payment_method=None,
                            amount=data['down_payment'],
                            transfer_to_from=loan_application.shop.name,
                            description=f"Down Payment recived in shop for {product.name}.",
                            transaction_date=timezone.now(),
                            loan_application=loan_application,
                            agent=agent if agent else None, 
                            shop=loan_application.shop if loan_application.shop else None,
                            created_by=created_by_branch_manager if created_by_branch_manager else None,
                        )

                        shop_id = (data.get('shop_id') or '').strip()
                        shop_bank_account_id = (data.get('shop_bank_account_id') or '').strip()
                        print('shop_bank_account_id -> ', shop_bank_account_id)
                        if shop_bank_account_id:
                            shop_bank_account = ShopBankAccount.objects.select_for_update().get(
                                bank_account_id=shop_bank_account_id,
                                shop=loan_application.shop,
                            )
                            print('shop_bank_account -> ', shop_bank_account)
                            if shop_bank_account:
                                print("Decimal(data['down_payment'] -> ", Decimal(data['down_payment']))
                                print('Decimal(shop_bank_account.current_balance) -> ', Decimal(shop_bank_account.current_balance))
                                print("(Decimal(shop_bank_account.current_balance) + Decimal(data['down_payment']))  ->", (Decimal(shop_bank_account.current_balance) + Decimal(data['down_payment'])))
                                print('shop_bank_account.current_balance -> ', (Decimal(shop_bank_account.current_balance) + Decimal(data['down_payment'])).quantize(Decimal('0.01')))
                                shop_bank_account.current_balance = (Decimal(shop_bank_account.current_balance) + Decimal(data['down_payment'])).quantize(Decimal('0.01'))
                                shop_bank_account.save(update_fields=['current_balance', 'updated_at'])
                                print("[Shop Bank Account] Done Updating Shop Bank Account ---------------------------------------------------")


                # --- Generate Logo --------------------------------------------------
                

                try:
                    logo_base64 = self._get_base64_logo()
                except Exception as e:
                    print(f"[PDF] Could not load logo: {str(e)}")
                    logo_base64 = None

                # Generate PDF for automatic download (reuse the same PDF content if available).
                # pdf_content is guaranteed to be defined above; if PDF
                # generation failed or there were no recipients, it will be
                # None and we fall back to attempting a fresh generation
                # for download only.

                pdf_context = {
                    'customer': customer,
                    'loan_application': loan_application,
                    'loan_detail': {
                        'loan_category': loan_category_instance,
                        'loan_amount': loan_amount_decimal,
                        'tenure': tenure_instance,
                        'loan_purpose': data['loan_purpose'],
                        'interest_rate': interest_instance,
                    },
                    'address': address_kwargs,
                    'generated_date': timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).strftime('%B %d, %Y at %I:%M %p'),
                    'logo_base64': logo_base64,
                }
                if product:
                    pdf_context['loan_detail']['product'] = product.sub_category.main_category.name, product.sub_category.name, product.name
                pdf_content = self._generate_pdf(pdf_context)
                print('pdf_content generated ...................................   ')

                 # --- Email Notification with PDF Attachment ---
                # Initialize pdf_content so that later download logic never
                # fails with an UnboundLocalError when there are no
                # recipients or PDF generation is skipped.
                self._send_email(data, customer, loan_application, pdf_content)
                # --- End Email Notification ---
                print('pdf_content after send email  ----------------------------------   ')

                # If we get here, the transaction was successful
                response_data = {
                    'success': True,
                    'message': 'Loan application submitted successfully',
                    'loan_ref_no': loan_application.loan_ref_no,
                    'customer_id': customer.customer_id,
                }
                
                return self._add_pdf_at_final_response(response_data, pdf_content)

            except Exception as e:
                import time
                if 'database is locked' in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                    
                # Handle specific database errors
                if isinstance(e, IntegrityError):
                    msg = str(e).lower()
                    if 'adhar_number' in msg:
                        return Response({'success': False, 'message': 'A customer with this Aadhaar number already exists.'}, status=400)
                    if 'pan_number' in msg:
                        return Response({'success': False, 'message': 'A customer with this PAN number already exists.'}, status=400)
                    if 'voter_number' in msg:
                        return Response({'success': False, 'message': 'A customer with this Voter ID already exists.'}, status=400)
                    return Response({'success': False, 'message': 'A database error occurred. Please try again.'}, status=400)
                    
                # Handle operational errors (like database locked)
                if 'database is locked' in str(e):
                    return Response({
                        'success': False, 
                        'message': 'The system is busy processing other requests. Please try again in a moment.'
                    }, status=503)  # 503 Service Unavailable
                    
                # Log other errors
                import traceback
                print(traceback.format_exc())
                return Response({
                    'success': False, 
                    'message': 'An unexpected error occurred. Please try again later.'
                }, status=500)
        
        # This will only be reached if all retries are exhausted without success
        return Response({
            'success': False,
            'message': 'The system is currently busy. Please try again in a few moments.'
        }, status=503)



    ## function for customer detail ##

    def _is_customer_detail_locked(self, data:QueryDict, field_name:str):
        return_field_data = data.get(field_name)
        if (return_field_data and 
            return_field_data.strip() and 
            len(return_field_data.strip()) > 0 and 
            not return_field_data.isspace() and 
            CustomerDetail.objects.filter(**{field_name: return_field_data.strip()}).exclude(**{field_name: None}).exclude(**{field_name: ''}).select_for_update(nowait=True).exists()):
            return return_field_data
        return None

    

    def _get_customer_detail(self, data: QueryDict) -> Optional[CustomerDetail]:
        customer_id = data.get('customer_id')
        print('customer_id -> ', customer_id)
        if customer_id and customer_id.strip():
            try:
                customer = CustomerDetail.objects.get(customer_id=customer_id)
                return customer
            except CustomerDetail.DoesNotExist:
                return None
        return None




    ##  function for request data validation ---------------------------------------------------------------  ##
    def _validate_bank_details(self, data:QueryDict, errors: dict, existing_customer:Optional[CustomerDetail]):
        account_number = (data.get('account_number') or '').strip()
        confirm_account_number = (data.get('confirm_account_number') or '').strip()
        bank_name = (data.get('bank_name') or '').strip()
        ifsc_code = (data.get('ifsc_code') or '').strip().upper()
        account_errors = {}
        
        # Only validate if account_number is provided
        if account_number:
            if not account_number.isdigit():
                account_errors['account_number'] = 'Account number must contain digits only.'
            elif not 9 <= len(account_number) <= 18:
                account_errors['account_number'] = 'Account number must be between 9 and 18 digits.'
            elif CustomerAccount.objects.filter(account_number=account_number).exists():
                if not existing_customer:
                    account_errors['account_number'] = 'This account number is already registered.'
            
            # Only validate confirm_account_number if account_number is provided
            if not confirm_account_number:
                account_errors['confirm_account_number'] = 'Please confirm the account number.'
            elif account_number != confirm_account_number:
                account_errors['confirm_account_number'] = 'Account numbers do not match.'
        
        
        
        
        # Only validate bank_name if provided
        if bank_name and len(bank_name.strip()) < 3:
            account_errors['bank_name'] = 'Bank name must be at least 3 characters.'
        
        # Only validate ifsc_code if provided
        if ifsc_code:
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
                account_errors['ifsc_code'] = 'Enter a valid IFSC code (e.g., SBIN0001234).'
        
        errors.update(account_errors)
        return account_number, bank_name, ifsc_code


    ##   Validatiion Data Fields ------------------------------------------------------------------------------  ##
    def _validate_data_fields(self, data:QueryDict, files:MultiValueDict, errors:dict):
        same_address = data.get('same_address') == 'on'
        required_file_fields = ['guarantor_id_proof','id_proof', 'photo', 'signature'] + (['residential_proof_file'] if not same_address else [])
        required_fields = [
            'full_name', 'father_name', 'date_of_birth', 'gender', 'contact', 'adhar_number', 'pan_number',
            'address_line_1', 'state', 'post_code',
            'loan_category', 'loan_amount', 'tenure_months', 'loan_purpose', 'interest_rate', 'emi_amount',
        ] 
        if not same_address:
            required_fields.extend(['current_address_line_1', 'current_state', 'current_post_code', 'residential_proof_type'])
                    
        
        for f in required_fields:
            if f in required_file_fields:
                if not files.get(f):
                    errors[f] = 'This file is required.'
            else:
                if not data.get(f):
                    errors[f] = 'This field is required.'
        
        return same_address




    def _check_duplicate_customer_identity(self, data:QueryDict, errors:dict):        
        with transaction.atomic():
            # Use select_for_update to lock the rows we're about to modify
            locked_fields = ['adhar_number', 'pan_number', 'voter_number']
            for field_name in locked_fields:
                if self._is_customer_detail_locked(data, field_name):
                    errors[field_name] = f'A customer with this {field_name.replace("_", " ").title()} already exists.'




    def _loan_and_emi_validation(self, data:QueryDict, errors:dict):
        try:
            loan_amount_decimal = Decimal(str(data.get('loan_amount', '')))
        except (TypeError, ValueError, InvalidOperation):
            errors['loan_amount'] = 'Loan amount must be a number.'
        try:
            interest_instance = LoanInterest.objects.get(interest_id=data['interest_rate']) if data.get('interest_rate') else None
        except LoanInterest.DoesNotExist:
            errors['interest_rate'] = 'Invalid interest rate.'
        try:
            emi_amount_decimal = Decimal(str(data.get('emi_amount', '')))
        except (TypeError, ValueError, InvalidOperation):
            errors['emi_amount'] = 'EMI amount must be a number.'
        
        return loan_amount_decimal, interest_instance, emi_amount_decimal
        
        

    def _post_code_validation(self, data:QueryDict, errors:dict, same_address:bool):
        post_code = data.get('post_code')
        current_post_code = data.get('current_post_code')
        # Validate post_code: must be exactly 6 digits
        if post_code and not (post_code.isdigit() and len(post_code) == 6):
            errors['post_code'] = 'Post code must be exactly 6 digits.'
        # Validate current_post_code: must be exactly 6 digits if required
        if not same_address:
            if current_post_code is None or not (current_post_code.isdigit() and len(current_post_code) == 6):
                errors['current_post_code'] = 'Current post code must be exactly 6 digits.'
        
        return post_code, current_post_code


    def _get_valid_instances(self, data:QueryDict, errors:dict):
        loan_category_instance = None
        interest_instance = None
        tenure_instance = None
        if not errors:
            try:
                loan_category_instance = LoanCategory.objects.get(category_id=data['loan_category'])
            except LoanCategory.DoesNotExist:
                errors['loan_category'] = 'Invalid loan category.'
            try:
                interest_instance = LoanInterest.objects.get(interest_id=data['interest_rate']) if data.get('interest_rate') else None
            except LoanInterest.DoesNotExist:
                errors['interest_rate'] = 'Invalid interest rate.'
            try:
                tenure_instance = LoanTenure.objects.get(tenure_id=data['tenure_months'])
            except (LoanTenure.DoesNotExist, ValueError, TypeError):
                errors['tenure_months'] = 'Invalid loan tenure.'
        return loan_category_instance, interest_instance, tenure_instance

    def _check_required_document_files(self, files:MultiValueDict, errors:dict):
        required_doc_files = ['guarantor_id_proof','id_proof', 'photo', 'signature']
        missing_files = [f for f in required_doc_files if not files.get(f)]
        if missing_files:
            errors['documents'] = f'Missing required document files: {", ".join(missing_files)}'










    ##  functions for data save    ---------------------------------------------------------------------------- ##
    def _check_authentication(self, request):
        agent_id = request.session.get('agent_id')
        branch_manager_id = request.session.get('logged_user_id')
        agent = None
        branch = None
        created_by_agent = None
        created_by_branch_manager = None
        if agent_id:
            agent = Agent.objects.get(agent_id=agent_id)
            branch = agent.branch
            created_by_agent = agent
        elif branch_manager_id:
            branch_manager = BranchEmployee.objects.get(id=branch_manager_id)
            branch = branch_manager.branch
            created_by_branch_manager = branch_manager
            agent = None
        return agent_id, agent, created_by_agent, branch_manager_id, branch, created_by_branch_manager
        
    
    def _convert_date_of_birth(self, date_str:str):
        """Convert date_of_birth string to date object"""
        try:
            # Try to parse the date string (assuming format: YYYY-MM-DD or DD/MM/YYYY)
            if '/' in date_str:
                # Handle DD/MM/YYYY format
                date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
            elif '-' in date_str:
                # Handle YYYY-MM-DD or DD-MM-YYYY format
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    date_obj = datetime.strptime(date_str, '%d-%m-%Y').date()
            else:
                raw = str(date_str)
                digits = re.sub(r'\D', '', raw)
                if len(digits) == 8:
                    # Handle DDMMYYYY format
                    date_obj = datetime.strptime(digits, '%d%m%Y').date()
                else:
                    # Try ISO format
                    date_obj = datetime.fromisoformat(date_str).date()
        except (ValueError, TypeError) as e:
            print(f"[Date Error] Failed to parse date_of_birth: {date_str}, error: {str(e)}")
            # Fallback to original string if parsing fails
            date_obj = date_str
        return date_obj


    def _save_customer(self, data:QueryDict, date_of_birth:date, branch, agent, existing_customer:CustomerDetail = None) -> CustomerDetail:
        """Save customer details"""
        customer_kwargs = dict(
            full_name=data['full_name'],
            father_name=data.get('father_name'),
            date_of_birth=date_of_birth,
            gender=data['gender'],
            contact=data['contact'],
            email=data.get('email'),
            adhar_number=data['adhar_number'],
            pan_number=data['pan_number'],
            guarantor_name=data.get('guarantor_name'),
            branch=branch,
        )
        #Only add voter_number if it's provided and not empty
        if data.get('voter_number') and data['voter_number'].strip():
            customer_kwargs['voter_number'] = data['voter_number']

        if agent:
            customer_kwargs['agent'] = agent
        if existing_customer:
            existing_customer.__dict__.update(**customer_kwargs)
            existing_customer.save()
            customer = existing_customer
        else:
            customer = CustomerDetail.objects.create(**customer_kwargs)
        return customer


    def _get_product_data(self, data:QueryDict):
        product_id = data.get('product_id')
        product = None
        if product_id and product_id.strip():
            try:
                product = Product.objects.get(product_id=product_id.strip())
            except Product.DoesNotExist:
                pass
        return product_id, product


    def _validate_and_populate_shop_data(
        self,
        data: QueryDict,
        agent,
        branch,
        loan_category_instance: Optional[LoanCategory],
        loan_application_kwargs: dict,
    ) -> Union[None, Response]:
        shop_id = (data.get('shop_id') or '').strip()
        shop_bank_account_id = (data.get('shop_bank_account_id') or '').strip()

        is_shop_active = False
        if loan_category_instance and loan_category_instance.main_category:
            is_shop_active = bool(loan_category_instance.main_category.is_shop_active)

        if not is_shop_active:
            return None

        if not shop_id and not shop_bank_account_id:
            return Response(
                {
                    'success': False,
                    'errors': {
                        'shop_id': 'Shop is required for this loan category.'
                    },
                },
                status=400,
            )

        selected_shop = None
        selected_shop_bank_account = None

        if shop_id:
            if agent:
                selected_shop = Shop.objects.filter(shop_id=shop_id, agent=agent).first()
            else:
                selected_shop = Shop.objects.filter(shop_id=shop_id, branch=branch).first()
            if not selected_shop:
                return Response(
                    {'success': False, 'errors': {'shop_id': 'Invalid shop.'}},
                    status=400,
                )

        if shop_bank_account_id:
            selected_shop_bank_account = ShopBankAccount.objects.filter(
                bank_account_id=shop_bank_account_id
            ).select_related('shop').first()
            if not selected_shop_bank_account:
                return Response(
                    {'success': False, 'errors': {'shop_bank_account_id': 'Invalid shop bank account.'}},
                    status=400,
                )
            if selected_shop and selected_shop_bank_account.shop_id != selected_shop.shop_id:
                return Response(
                    {'success': False, 'errors': {'shop_bank_account_id': 'Bank account does not belong to selected shop.'}},
                    status=400,
                )
            if not selected_shop:
                selected_shop = selected_shop_bank_account.shop

        if selected_shop:
            loan_application_kwargs['shop'] = selected_shop
        if selected_shop_bank_account:
            loan_application_kwargs['shop_bank_account'] = selected_shop_bank_account
        return None




















































    ###  function for Email Notification with PDF Attachment

    def _get_base64_logo(self) -> Optional[str]:
        import base64
        import os
        logo_base64: Optional[str] = None
        try:
            logo_path = os.path.join(settings.BASE_DIR, 'static', 'main', 'images', 'company-logo.png')
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as logo_file:
                    logo_data = logo_file.read()
                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                    logo_base64 = f"data:image/png;base64,{logo_base64}"
        except Exception as e:
            print(f"[PDF] Could not load logo: {str(e)}")
        return logo_base64

    def _send_email(self, data:QueryDict, customer:CustomerDetail, loan_application:LoanApplication, pdf_content):
        try:
            recipient_list = []

            # Customer email
            customer_email = getattr(customer, 'email', None)
            if customer_email and customer_email.strip():
                recipient_list.append(customer_email.strip())

            # Branch email
            # Prefer loan_application.branch but fall back to other known relations.
            branch_obj = (
                getattr(loan_application, 'branch', None)
                or getattr(customer, 'branch', None)
                or getattr(getattr(loan_application, 'agent', None), 'branch', None)
                or getattr(getattr(loan_application, 'created_by_branch_manager', None), 'branch', None)
            )
            branch_email = getattr(branch_obj, 'email', None) if branch_obj else None
            if branch_email and branch_email.strip():
                recipient_list.append(branch_email.strip())

            # HQ email from settings
            hq_email = getattr(settings, 'HQ_NOTIFICATION_EMAIL', None)
            if hq_email and str(hq_email).strip():
                recipient_list.append(str(hq_email).strip())

            # De-duplicate while keeping order
            seen = set()
            recipient_list = [e for e in recipient_list if not (e in seen or seen.add(e))]

            if recipient_list:
                subject = f"New Loan Application Received - Ref: {loan_application.loan_ref_no}"
                from django.template.loader import render_to_string
                from django.core.mail import EmailMultiAlternatives
                context = {
                    'loan_ref_no': loan_application.loan_ref_no,
                    'customer_name': customer.full_name,
                    'customer_contact': customer.contact,
                    'loan_amount': data.get('loan_amount'),
                    'sub_header': 'New Loan Application Submitted',
                    'purpose_flag': 'loan_application_submitted',
                }
                message_text = (
                    "SUNDARAM\n"
                    "=========\n\n"
                    "A new loan application has been submitted.\n\n"
                    f"Reference No: {loan_application.loan_ref_no}\n"
                    f"Customer Name: {customer.full_name}\n"
                    f"Contact Number: {customer.contact}\n"
                    f"Loan Amount Requested: {data.get('loan_amount')}\n"
                )
                try:
                    message_html = render_to_string('loan/loan_application_email.html', context)
                except Exception:
                    message_html = None

                

                # Send individually to each recipient to avoid exposing addresses
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
                for recipient in recipient_list:
                    try:
                        email = EmailMultiAlternatives(
                            subject,
                            message_text,
                            from_email,
                            [recipient],
                        )
                        if message_html:
                            email.attach_alternative(message_html, "text/html")
                        
                        # Attach PDF to all emails
                        if pdf_content:
                            filename = f"loan_application_{loan_application.loan_ref_no}.pdf"
                            email.attach(filename, pdf_content, 'application/pdf')
                            print(f"[Email] PDF attached to email for {recipient}: {filename}")
                        else:
                            print(f"[Email] No PDF content available for {recipient}")
                        
                        email.send(fail_silently=False)
                        print(f"[Email] Successfully sent email to: {recipient}")
                    except Exception as email_error:
                        print(f"[Email Error] Failed to send email to {recipient}: {str(email_error)}")
                        import traceback
                        print(traceback.format_exc())

        except Exception as e:
            import traceback
            print("[Email Send Error]", traceback.format_exc())


    def _send_email_with_pdf(self, to_email, subject, html_content, pdf_content):
        """Send email with PDF attachment"""
        try:
            msg = EmailMessage(
                subject=subject,
                body=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
            )
            msg.content_subtype = "html"
            msg.attach('application.pdf', pdf_content, 'application/pdf')
            msg.send()
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False






    ## function for pdf generate ##
    def _generate_pdf(self, pdf_context):
        try:
            print("[Download] Generating PDF for automatic download...")
            
            
            html_content = render_to_string('loan-application-pdf/loan-application-pdf.html', pdf_context)
            pdf_content = self._generate_pdf_file(html_content)
            print("[Download] PDF generated successfully for automatic download")
        except Exception as pdf_error:
            print(f"[Download Error] Failed to generate PDF for download: {str(pdf_error)}")
            pdf_content = None
        return pdf_content

    def _generate_pdf_file(self, html_content):
        """Generate PDF for email attachment using Playwright"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Generate PDF; if this fails we log and return None so that
            # the main API call can still succeed without breaking the
            # application submission flow.
            result = loop.run_until_complete(self._generate_pdf_file_async(html_content))
            return result
        except Exception as e:
            print(f"Error in _generate_pdf_file: {str(e)}")
            import traceback
            traceback.print_exc()
            # Do not propagate the exception further; PDF is optional for
            # the main loan application API response.
            return None
        finally:
            loop.close()
    
    async def _generate_pdf_file_async(self, html_content):
        """Generate PDF from HTML content using Playwright with optimized performance"""
        browser = None
        try:
            async with async_playwright() as p:
                # Try launching with optimized settings for better performance
                for attempt in (1, 2):
                    try:
                        browser = await p.chromium.launch(
                            headless=True,
                            args=[
                                '--no-sandbox',
                                '--disable-dev-shm-usage',
                                '--disable-gpu',
                                '--disable-web-security',
                                '--disable-features=VizDisplayCompositor'
                            ]
                        )
                        break
                    except Exception as launch_err:
                        msg = str(launch_err)
                        if "Executable doesn't exist" in msg and attempt == 1:
                            print("[PDF] Installing Playwright browsers...")
                            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
                        else:
                            raise launch_err
                
                page = await browser.new_page()
                
                # Set shorter timeout and optimized page settings
                page.set_default_timeout(30000)  # 30 seconds timeout
                await page.set_content(html_content, wait_until='domcontentloaded')
                
                # Generate PDF with optimized settings
                pdf_bytes = await page.pdf(
                    format='A4',
                    print_background=True,
                    prefer_css_page_size=True,
                    margin={
                        'top': '15mm',
                        'right': '15mm',
                        'bottom': '15mm',
                        'left': '15mm'
                    }
                )
                
                return pdf_bytes
        except Exception as e:
            print(f"[PDF Error] Failed to generate PDF: {str(e)}")
            raise e
        finally:
            if browser:
                try:
                    await browser.close()
                except:
                    pass 

    async def _install_playwright_chromium_for_email(self):
        """Install Playwright Chromium browser if missing. Runs once when needed."""
        cmd = [sys.executable, '-m', 'playwright', 'install', 'chromium']
        def _run():
            return subprocess.run(cmd, check=True, capture_output=True)
        # Execute in a worker thread to avoid blocking the event loop
        await asyncio.to_thread(_run)

    
    def _add_pdf_at_final_response(self, response_data, pdf_content):
        """Generate final response with PDF download data if available"""
        if pdf_content:
            pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')
            response_data['pdf_download'] = {
                'filename': f"loan_application_{response_data['loan_ref_no']}.pdf",
                'content': pdf_base64,
                'content_type': 'application/pdf'
            }
            print(f"[Download] PDF ready for download: {response_data['pdf_download']['filename']}")
        return Response(response_data)

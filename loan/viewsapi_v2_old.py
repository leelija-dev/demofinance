from django.db import transaction, IntegrityError
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser

from decimal import Decimal, InvalidOperation
import re
import asyncio
import subprocess
import sys
import base64
import os
from zoneinfo import ZoneInfo
from playwright.async_api import async_playwright

from agent.models import Agent
from branch.models import BranchEmployee
from loan.models import (
    CustomerDetail, CustomerAddress, CustomerLoanDetail, CustomerDocument,
    LoanCategory, LoanInterest, LoanApplication, LoanPeriod, LoanTenure,
    CustomerAccount, Product, Shop, ShopBankAccount
)



class NewLoanApplicationAPIV2(APIView):
    parser_classes = (MultiPartParser, FormParser)

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        max_retries = 3
        retry_delay = 0.1  # seconds
        
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    # Use select_for_update to lock the rows we're about to modify
                    if 'adhar_number' in request.data:
                        CustomerDetail.objects.filter(
                            adhar_number=request.data['adhar_number']
                        ).select_for_update(nowait=True).exists()
                    if 'pan_number' in request.data:
                        CustomerDetail.objects.filter(
                            pan_number=request.data['pan_number']
                        ).select_for_update(nowait=True).exists()
                    if 'voter_number' in request.data and request.data['voter_number']:
                        CustomerDetail.objects.filter(
                            voter_number=request.data['voter_number']
                        ).select_for_update(nowait=True).exists()
                        
                    data = request.data
                    files = request.FILES
                same_address = data.get('same_address') == 'on'
                required_fields = [
                    'full_name', 'father_name', 'date_of_birth', 'gender', 'contact', 'adhar_number', 'pan_number',
                    'address_line_1', 'state', 'post_code',
                    'loan_category', 'loan_amount', 'tenure_months', 'loan_purpose', 'interest_rate', 'emi_amount',
                ]
                required_file_fields = [
                    'id_proof', 'photo', 'signature'
                ]
                if not same_address:
                    required_fields.extend(['current_address_line_1', 'current_state', 'current_post_code', 'residential_proof_type'])
                    required_file_fields.append('residential_proof_file')
                errors = {}

                # account_number = (data.get('account_number') or '').strip()
                # confirm_account_number = (data.get('confirm_account_number') or '').strip()
                # bank_name = (data.get('bank_name') or '').strip()
                # ifsc_code = (data.get('ifsc_code') or '').strip().upper()
                # account_type = data.get('account_type')
                
                # account_errors = {}
                
                # if not account_number:
                #     account_errors['account_number'] = 'Account number is required.'
                # else:
                #     if not account_number.isdigit():
                #         account_errors['account_number'] = 'Account number must contain digits only.'
                #     elif not 9 <= len(account_number) <= 18:
                #         account_errors['account_number'] = 'Account number must be between 9 and 18 digits.'
                #     elif CustomerAccount.objects.filter(account_number=account_number).exists():
                #         account_errors['account_number'] = 'This account number is already registered.'
                
                # if not confirm_account_number:
                #     account_errors['confirm_account_number'] = 'Please confirm the account number.'
                # elif account_number and account_number != confirm_account_number:
                #     account_errors['confirm_account_number'] = 'Account numbers do not match.'
                
                # if not bank_name:
                #     account_errors['bank_name'] = 'Bank name is required.'
                
                # if not ifsc_code:
                #     account_errors['ifsc_code'] = 'IFSC code is required.'
                # else:
                #     if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
                #         account_errors['ifsc_code'] = 'Enter a valid IFSC code (e.g., SBIN0001234).'
                
                # if not account_type:
                #     account_errors['account_type'] = 'Account type is required.'
                # elif account_type not in dict(CustomerAccount.ACCOUNT_TYPES):
                #     account_errors['account_type'] = 'Invalid account type selected.'

                account_number = (data.get('account_number') or '').strip()
                confirm_account_number = (data.get('confirm_account_number') or '').strip()
                bank_name = (data.get('bank_name') or '').strip()
                ifsc_code = (data.get('ifsc_code') or '').strip().upper()
                account_type = data.get('account_type')
                
                account_errors = {}
                
                # Only validate if account_number is provided
                if account_number:
                    if not account_number.isdigit():
                        account_errors['account_number'] = 'Account number must contain digits only.'
                    elif not 9 <= len(account_number) <= 18:
                        account_errors['account_number'] = 'Account number must be between 9 and 18 digits.'
                    elif CustomerAccount.objects.filter(account_number=account_number).exists():
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
                
                # Account type is optional - no validation needed if empty
                
                if account_errors:
                    errors.update(account_errors)

                for f in required_fields:
                    if f in required_file_fields:
                        if not files.get(f):
                            errors[f] = 'This file is required.'
                    else:
                        if not data.get(f):
                            errors[f] = 'This field is required.'
                adhar_number = data.get('adhar_number')
                pan_number = data.get('pan_number')
                voter_number = data.get('voter_number')
                if adhar_number and CustomerDetail.objects.filter(adhar_number=adhar_number).exists():
                    errors['adhar_number'] = 'A customer with this Adhar Number already exists.'
                if pan_number and CustomerDetail.objects.filter(pan_number=pan_number).exists():
                    errors['pan_number'] = 'A customer with this PAN Number already exists.'
                # if voter_number and CustomerDetail.objects.filter(voter_number=voter_number).exists():
                #     errors['voter_number'] = 'A customer with this Voter ID already exists.'
                if (voter_number and 
                    voter_number.strip() and 
                    len(voter_number.strip()) > 0 and 
                    not voter_number.isspace() and 
                    CustomerDetail.objects.filter(voter_number=voter_number.strip()).exclude(voter_number__isnull=True).exclude(voter_number='').exists()):
                    errors['voter_number'] = 'A customer with this Voter ID already exists.'
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
                post_code = data.get('post_code')
                current_post_code = data.get('current_post_code')
                # Validate post_code: must be exactly 6 digits
                if post_code and not (post_code.isdigit() and len(post_code) == 6):
                    errors['post_code'] = 'Post code must be exactly 6 digits.'
                # Validate current_post_code: must be exactly 6 digits if required
                if not same_address:
                    if current_post_code is None or not (current_post_code.isdigit() and len(current_post_code) == 6):
                        errors['current_post_code'] = 'Current post code must be exactly 6 digits.'
                # Validate ForeignKeys
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
                # Set rate_of_interest_decimal from interest_instance
                rate_of_interest_decimal = interest_instance.rate_of_interest if interest_instance else None
                # Check required document files
                required_doc_files = ['id_proof', 'photo', 'signature']
                missing_files = [f for f in required_doc_files if not files.get(f)]
                if missing_files:
                    errors['documents'] = f'Missing required document files: {", ".join(missing_files)}'
                if errors:
                    return Response({'success': False, 'errors': errors}, status=400)


                # All validation passed, now create objects
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
                else:
                    return Response({'success': False, 'message': 'Authentication required.'}, status=400)

                if same_address:
                    current_address_line_1 = data['address_line_1']
                    current_address_line_2 = data.get('address_line_2')
                    current_state = data['state']
                    current_post_code = data['post_code']
                else:
                    current_address_line_1 = data['current_address_line_1']
                    current_address_line_2 = data.get('current_address_line_2')
                    current_state = data['current_state']
                    current_post_code = data['current_post_code']

                # Convert date_of_birth string to date object
                from datetime import datetime
                try:
                    # Try to parse the date string (assuming format: YYYY-MM-DD or DD/MM/YYYY)
                    date_str = data['date_of_birth']
                    if '/' in date_str:
                        # Handle DD/MM/YYYY format
                        date_obj = datetime.strptime(date_str, '%d/%m/%Y').date()
                    elif '-' in date_str:
                        # Handle YYYY-MM-DD format
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    else:
                        # Try ISO format
                        date_obj = datetime.fromisoformat(date_str).date()
                except (ValueError, TypeError) as e:
                    print(f"[Date Error] Failed to parse date_of_birth: {date_str}, error: {str(e)}")
                    # Fallback to original string if parsing fails
                    date_obj = data['date_of_birth']

                customer_kwargs = dict(
                    full_name=data['full_name'],
                    father_name=data.get('father_name'),
                    date_of_birth=date_obj,
                    gender=data['gender'],
                    contact=data['contact'],
                    email=data.get('email'),
                    adhar_number=data['adhar_number'],
                    pan_number=data['pan_number'],
                    # voter_number=data['voter_number'],
                    branch=branch,
                )
                #Only add voter_number if it's provided and not empty
                if data.get('voter_number') and data['voter_number'].strip():
                    customer_kwargs['voter_number'] = data['voter_number']

                if agent:
                    customer_kwargs['agent'] = agent
                customer = CustomerDetail.objects.create(**customer_kwargs)

                loan_application_kwargs = dict(
                    customer=customer,
                    status='pending',
                    branch=branch,
                    rejection_reason='',
                    document_request_reason='',
                )
                ############ shop ID and shop Bank #############
                product_id = (data.get('product_id') or '').strip()
                shop_id = (data.get('shop_id') or '').strip()
                shop_bank_account_id = (data.get('shop_bank_account_id') or '').strip()

                if product_id and (not shop_id and not shop_bank_account_id):
                    return Response(
                        {
                            'success': False,
                            'errors': {
                                'shop_id': 'Shop is required for product-based (mobile) loans.'
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
               ############ end shop ID and shop Bank #############
                if agent_id and agent:
                    loan_application_kwargs['agent'] = agent
                    loan_application_kwargs['created_by_agent'] = created_by_agent
                if branch_manager_id and created_by_branch_manager:
                    loan_application_kwargs['created_by_branch_manager'] = created_by_branch_manager
                loan_application = LoanApplication.objects.create(**loan_application_kwargs)

                customer.loan_application = loan_application
                customer.save()
                
                # Create address and loan detail data FIRST
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
                CustomerAddress.objects.create(**address_kwargs)

                loan_detail_kwargs = dict(
                    loan_application=loan_application,
                    loan_category=loan_category_instance,
                    loan_amount=loan_amount_decimal,
                    tenure=tenure_instance,
                    loan_purpose=data['loan_purpose'],
                    interest_rate=interest_instance,
                    emi_amount=emi_amount_decimal,
                    branch=branch
                )
                product_id = data.get('product_id')
                product = None
                if product_id and product_id.strip():
                    try:
                        product = Product.objects.get(product_id=product_id)
                    except Product.DoesNotExist:
                        product = None
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

                # CustomerAccount.objects.create(
                #     loan_application=loan_application,
                #     customer=customer,
                #     account_number=account_number,
                #     bank_name=bank_name,
                #     ifsc_code=ifsc_code,
                #     account_type=account_type,
                #     branch=branch,
                #     agent=agent if agent else None,
                # )

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
                    
                    CustomerAccount.objects.create(**account_kwargs)

                # --- Email Notification with PDF Attachment ---
                # Initialize pdf_content so that later download logic never
                # fails with an UnboundLocalError when there are no
                # recipients or PDF generation is skipped.
                pdf_content = None
                try:
                    recipient_list = []
                    # Customer email
                    if customer.email:
                        recipient_list.append(customer.email)
                    # Branch email (from branch object used in loan_application)
                    branch_email = getattr(loan_application.branch, 'email', None)
                    if branch_email:
                        recipient_list.append(branch_email)
                    # HQ email from settings (add to settings if not present)
                    hq_email = getattr(settings, 'HQ_NOTIFICATION_EMAIL', None)
                    if hq_email:
                        recipient_list.append(hq_email)

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

                        # Generate PDF for email attachment (optional).
                        # Any failure here must not break the main
                        # application flow.
                        try:
                            print("[Email] Generating PDF for loan application attachment...")
                            # Convert logo to base64 for PDF
                            import base64
                            import os
                            logo_base64 = None
                            try:
                                logo_path = os.path.join(settings.BASE_DIR, 'static', 'main', 'images', 'company-logo.png')
                                if os.path.exists(logo_path):
                                    with open(logo_path, 'rb') as logo_file:
                                        logo_data = logo_file.read()
                                        logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                                        logo_base64 = f"data:image/png;base64,{logo_base64}"
                            except Exception as e:
                                print(f"[PDF] Could not load logo: {str(e)}")
                            
                            # Prepare context for PDF with actual data
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
                            # Debug: Print customer date_of_birth info
                            print(f"[PDF Debug] Customer date_of_birth: {customer.date_of_birth}, type: {type(customer.date_of_birth)}")
                            # Generate HTML content for PDF
                            html_content = render_to_string('loan-application-pdf/loan-application-pdf.html', pdf_context)
                            # Generate PDF
                            pdf_content = self._generate_pdf_for_email(html_content)
                            print("[Email] PDF generated successfully for email attachment")
                        except Exception as pdf_error:
                            print(f"[Email Error] Failed to generate PDF for email: {str(pdf_error)}")
                            import traceback
                            print(traceback.format_exc())
                            pdf_content = None

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
                # --- End Email Notification ---

                # Generate PDF for automatic download (reuse the same PDF content if available).
                # pdf_content is guaranteed to be defined above; if PDF
                # generation failed or there were no recipients, it will be
                # None and we fall back to attempting a fresh generation
                # for download only.
                download_pdf_content = pdf_content  # Use the PDF generated for email, if any

                if not download_pdf_content:
                    # If email PDF generation failed, try again for download
                    try:
                        print("[Download] Generating PDF for automatic download...")
                        # Convert logo to base64 for PDF download as well
                        import base64
                        import os
                        logo_base64 = None
                        try:
                            logo_path = os.path.join(settings.BASE_DIR, 'static', 'main', 'images', 'company-logo.png')
                            if os.path.exists(logo_path):
                                with open(logo_path, 'rb') as logo_file:
                                    logo_data = logo_file.read()
                                    logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                                    logo_base64 = f"data:image/png;base64,{logo_base64}"
                        except Exception as e:
                            print(f"[PDF Download] Could not load logo: {str(e)}")
                        
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
                        html_content = render_to_string('loan-application-pdf/loan-application-pdf.html', pdf_context)
                        download_pdf_content = self._generate_pdf_for_email(html_content)
                        print("[Download] PDF generated successfully for automatic download")
                    except Exception as pdf_error:
                        print(f"[Download Error] Failed to generate PDF for download: {str(pdf_error)}")
                        download_pdf_content = None

                # If we get here, the transaction was successful
                response_data = {
                    'success': True,
                    'message': 'Loan application submitted successfully',
                    'loan_ref_no': loan_application.loan_ref_no,
                    'customer_id': customer.customer_id,
                }
                
                # Add PDF download data if generated successfully
                if download_pdf_content:
                    import base64
                    pdf_base64 = base64.b64encode(download_pdf_content).decode('utf-8')
                    response_data['pdf_download'] = {
                        'filename': f"loan_application_{loan_application.loan_ref_no}.pdf",
                        'content': pdf_base64,
                        'content_type': 'application/pdf'
                    }
                    print(f"[Download] PDF ready for download: {response_data['pdf_download']['filename']}")
                
                return Response(response_data)
                
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
    ## function for pdf generate ##
    def _generate_pdf_for_email(self, html_content):
        """Generate PDF for email attachment using Playwright"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Generate PDF; if this fails we log and return None so that
            # the main API call can still succeed without breaking the
            # application submission flow.
            result = loop.run_until_complete(self._generate_pdf_async(html_content))
            return result
        except Exception as e:
            print(f"Error in _generate_pdf_for_email: {str(e)}")
            import traceback
            traceback.print_exc()
            # Do not propagate the exception further; PDF is optional for
            # the main loan application API response.
            return None
        finally:
            loop.close()
    
    async def _generate_pdf_async(self, html_content):
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


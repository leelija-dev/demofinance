from django.db.models import Q, OuterRef, Subquery
from django.http import response
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views import View
from rest_framework.views import APIView
from django.urls import reverse
from django.views.generic import ListView
from rest_framework.response import Response
from rest_framework import status
from headquater.models import Branch
from branch.models import BranchEmployee
from agent.models import Agent
from loan.models import (
    CustomerAddress, CustomerDocument, CustomerLoanDetail, LoanApplication, CustomerDetail, 
    DocumentRequest, DocumentReupload, DocumentReview, LoanMainCategory, LoanCategory, LoanInterest, 
    LoanTenure, LoanPeriod, DisbursementLog, Deductions, LateFeeSetting, LoanCloseRequest, 
    ChartOfAccount, ProductCategory, ProductSubCategory, Product,
    EmiAgentAssign, EmiCollectionDetail, LoanEMISchedule, LoanEMIReschedule,
    LoanCloseRequest, CustomerAccount, LoanApplicationDraft, Shop, ShopBankAccount
)
from loan.services.bank import CashfreeService, AutoPaymentService
from agent.decorators import AgentSessionRequiredMixin
from django.views.generic import TemplateView
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.parsers import MultiPartParser, FormParser
from .serializers import LoanApplicationSerializer, CustomerDetailSerializer, DocumentRequestSerializer, LoanApplicationDetailSerializer, LoanApplicationListSerializer
from .serializers import ( CustomerLoanDetailSerializer, CustomerAddressSerializer, CustomerDocumentSerializer,
AgentSerializer,LoanRejectedSerializer, LoanApprovedSerializer, EMICollectSerializer, CustomerAccountSerializer, LoanEMIScheduleSerializer,
)
import re
from django.db import transaction, IntegrityError
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import time
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_aware
from zoneinfo import ZoneInfo
from datetime import datetime

# for PDF generation
import asyncio
from playwright.async_api import async_playwright
import subprocess
import sys
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from main.pagination import AgentPagination
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
# Loan Application Views
class NewLoanApplication(AgentSessionRequiredMixin, TemplateView):
    template_name = 'loan/new-application.html'

    def get(self, request, *args, **kwargs):
        # Initialize context
        context = {
            'is_active': True,
            'error_message': None,
            'agent_id': request.session.get('agent_id'),
            'branch_manager_id': request.session.get('logged_user_id')
        }
        
        # Get agent or branch manager from session
        agent_id = request.session.get('agent_id')
        branch_manager_id = request.session.get('logged_user_id')
        
        if agent_id:
            try:
                agent = Agent.objects.get(agent_id=agent_id)
                print(agent)
                if  agent.status == 'inactive':
                    context['is_active'] = False
                    context['error_message'] = 'Cannot create loan application. Agent is currently inactive.'
            except Agent.DoesNotExist:
                context['is_active'] = False
                context['error_message'] = 'Agent not found.'
        else:
            context['is_active'] = False
            context['error_message'] = 'Authentication required.'
        
        return render(request, self.template_name, context)

class LoanApplicationView(AgentSessionRequiredMixin, TemplateView):
    template_name ='loan/loan-application.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.request.session.get('agent_id')

        qs = (
            LoanApplication.objects
            .select_related('customer', 'agent')
            .prefetch_related('loan_details')
            .filter(agent__agent_id=agent_id)
            .order_by('-submitted_at')
        )

        rows_all = []
        for app in qs:
            loan = None
            try:
                loan = app.loan_details.all().first()
            except Exception:
                loan = None

            rows_all.append({
                'loan_ref_no': getattr(app, 'loan_ref_no', None),
                'customer_id': getattr(getattr(app, 'customer', None), 'customer_id', None),
                'full_name': getattr(getattr(app, 'customer', None), 'full_name', None),
                'status': getattr(app, 'status', None),
                'submitted_at': app.submitted_at.strftime('%d-%m-%Y %H:%M') if getattr(app, 'submitted_at', None) else '-',
                'loan_amount': getattr(loan, 'loan_amount', '-') if loan else '-',
                'tenure_display': None,
                'interest_rate': None,
                'emi_amount': getattr(loan, 'emi_amount', '-') if loan else '-',
            })

            if loan and getattr(loan, 'tenure', None):
                try:
                    rows_all[-1]['tenure_display'] = f"{loan.tenure.value} {loan.tenure.unit}"
                except Exception:
                    rows_all[-1]['tenure_display'] = '-'
            else:
                rows_all[-1]['tenure_display'] = '-'

            if loan and getattr(loan, 'interest_rate', None):
                try:
                    rows_all[-1]['interest_rate'] = float(loan.interest_rate.rate_of_interest)
                except Exception:
                    rows_all[-1]['interest_rate'] = '-'
            else:
                rows_all[-1]['interest_rate'] = '-'

        paginator = Paginator(rows_all, 15)
        page_number = self.request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        context['rows'] = list(page_obj.object_list)
        context['has_next'] = page_obj.has_next()
        context['next_page_number'] = page_obj.next_page_number() if page_obj.has_next() else None
        return context


class LoanApplicationListPagePartialView(AgentSessionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')

        qs = (
            LoanApplication.objects
            .select_related('customer', 'agent')
            .prefetch_related('loan_details')
            .filter(agent__agent_id=agent_id)
            .order_by('-submitted_at')
        )

        rows_all = []
        for app in qs:
            loan = None
            try:
                loan = app.loan_details.all().first()
            except Exception:
                loan = None

            row = {
                'loan_ref_no': getattr(app, 'loan_ref_no', None),
                'customer_id': getattr(getattr(app, 'customer', None), 'customer_id', None),
                'full_name': getattr(getattr(app, 'customer', None), 'full_name', None),
                'status': getattr(app, 'status', None),
                'submitted_at': app.submitted_at.strftime('%d-%m-%Y %H:%M') if getattr(app, 'submitted_at', None) else '-',
                'loan_amount': getattr(loan, 'loan_amount', '-') if loan else '-',
                'tenure_display': '-',
                'interest_rate': '-',
                'emi_amount': getattr(loan, 'emi_amount', '-') if loan else '-',
            }

            if loan and getattr(loan, 'tenure', None):
                try:
                    row['tenure_display'] = f"{loan.tenure.value} {loan.tenure.unit}"
                except Exception:
                    row['tenure_display'] = '-'

            if loan and getattr(loan, 'interest_rate', None):
                try:
                    row['interest_rate'] = float(loan.interest_rate.rate_of_interest)
                except Exception:
                    row['interest_rate'] = '-'

            rows_all.append(row)

        paginator = Paginator(rows_all, 15)
        page_number = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return HttpResponse('')

        html = render_to_string(
            'loan/partials/loan-application-rows.html',
            {'rows': list(page_obj.object_list), 'page_obj': page_obj},
            request=request,
        )
        return HttpResponse(html)

class LoanRejectApplication(AgentSessionRequiredMixin, TemplateView):
    template_name = 'loan/loan-reject.html'

class LoanApproveApplication(AgentSessionRequiredMixin, TemplateView):
    template_name = 'loan/loan-approve.html'

class LoanDocumentRequest(AgentSessionRequiredMixin, TemplateView):
    template_name = 'loan/document_request.html'

class AgentApplicationDetailView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'loan/agent_application_detail.html'

class NewLaonApplicationPdf(TemplateView):
    template_name='loan-application-pdf/loan-application-pdf.html'


class NewLoanApplicationAPI(APIView):
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

                # account_number = (data.get('account_number') or '').strip()
                # confirm_account_number = (data.get('confirm_account_number') or '').strip()
                # bank_name = (data.get('bank_name') or '').strip()
                # ifsc_code = (data.get('ifsc_code') or '').strip().upper()
                # account_type = data.get('account_type')
                
                # account_errors = {}
                
                # # Only validate if account_number is provided
                # if account_number:
                #     if not account_number.isdigit():
                #         account_errors['account_number'] = 'Account number must contain digits only.'
                #     elif not 9 <= len(account_number) <= 18:
                #         account_errors['account_number'] = 'Account number must be between 9 and 18 digits.'
                #     else:
                #         account_qs = CustomerAccount.objects.filter(account_number=account_number)
                #         if existing_account_for_customer:
                #             account_qs = account_qs.exclude(pk=existing_account_for_customer.pk)
                #         if account_qs.exists():
                #             account_errors['account_number'] = 'This account number is already registered.'
                    
                #     # Only validate confirm_account_number if account_number is provided
                #     if not confirm_account_number:
                #         account_errors['confirm_account_number'] = 'Please confirm the account number.'
                #     elif account_number != confirm_account_number:
                #         account_errors['confirm_account_number'] = 'Account numbers do not match.'
                
                # # Only validate bank_name if provided
                # if bank_name and len(bank_name.strip()) < 3:
                #     account_errors['bank_name'] = 'Bank name must be at least 3 characters.'
                
                # # Only validate ifsc_code if provided
                # if ifsc_code:
                #     if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
                #         account_errors['ifsc_code'] = 'Enter a valid IFSC code (e.g., SBIN0001234).'
                
                # # Account type is optional - no validation needed if empty
                
                # if account_errors:
                #     errors.update(account_errors)

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

                existing_customer_by_aadhaar = None
                existing_customer_by_pan = None
                if adhar_number:
                    existing_customer_by_aadhaar = CustomerDetail.objects.filter(adhar_number=adhar_number).first()
                if pan_number:
                    existing_customer_by_pan = CustomerDetail.objects.filter(pan_number=pan_number).first()

                existing_customer = None
                if existing_customer_by_aadhaar and existing_customer_by_pan:
                    if existing_customer_by_aadhaar.customer_id != existing_customer_by_pan.customer_id:
                        errors['adhar_number'] = 'A customer with this Adhar Number already exists.'
                        errors['pan_number'] = 'A customer with this PAN Number already exists.'
                    else:
                        existing_customer = existing_customer_by_aadhaar
                else:
                    existing_customer = existing_customer_by_aadhaar or existing_customer_by_pan

                existing_account_for_customer = None
                if existing_customer:
                    existing_account_for_customer = getattr(existing_customer, 'account', None)

                if existing_customer:
                    non_rejected_loan_qs = (
                        LoanApplication.objects
                        .filter(customer=existing_customer)
                        .exclude(status__in=['reject', 'hq_rejected', 'rejected_by_branch'])
                    )
                    
                    active_loan_statuses = [
                        'active',
                        'hq_approved',
                        'disbursed',
                        'disbursed_fund_released',
                        'success',
                    ]
                    has_any_open_loan = (
                        non_rejected_loan_qs
                        .filter(status__in=active_loan_statuses)
                        .exclude(close_requests__status='approved')
                        .exists()
                    )

                    if has_any_open_loan:
                        errors['__all__'] = 'This customer already has an active loan. Please complete/close the existing loan (HQ approval required) before applying again.'
                        if adhar_number and existing_customer_by_aadhaar:
                            errors['adhar_number'] = 'A customer with this Adhar Number already exists.'
                        if pan_number and existing_customer_by_pan:
                            errors['pan_number'] = 'A customer with this PAN Number already exists.'
                


                
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
                    else:
                        account_qs = CustomerAccount.objects.filter(account_number=account_number)
                        if existing_account_for_customer:
                            account_qs = account_qs.exclude(pk=existing_account_for_customer.pk)
                        if account_qs.exists():
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


                # if voter_number and CustomerDetail.objects.filter(voter_number=voter_number).exists():
                #     errors['voter_number'] = 'A customer with this Voter ID already exists.'
                if (voter_number and 
                    voter_number.strip() and 
                    len(voter_number.strip()) > 0 and 
                    not voter_number.isspace() and 
                    CustomerDetail.objects.filter(voter_number=voter_number.strip()).exclude(voter_number__isnull=True).exclude(voter_number='').exclude(customer_id=getattr(existing_customer, 'customer_id', None)).exists()):
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
                if existing_customer:
                    for k, v in customer_kwargs.items():
                        setattr(existing_customer, k, v)
                    existing_customer.save()
                    customer = existing_customer
                else:
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
                existing_address = getattr(customer, 'address', None)
                if existing_address:
                    for k, v in address_kwargs.items():
                        setattr(existing_address, k, v)
                    existing_address.save()
                else:
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
                if agent:
                    loan_detail_kwargs['agent'] = agent
                CustomerLoanDetail.objects.create(**loan_detail_kwargs)

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
                    
                    existing_account = getattr(customer, 'account', None)
                    if existing_account:
                        for k, v in account_kwargs.items():
                            setattr(existing_account, k, v)
                        existing_account.save()
                    else:
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


### --------- after applied form details edit --------- ###    
class LoanApplicationEdit(AgentSessionRequiredMixin, APIView):
    def post(self, request, customer_id, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            customer = CustomerDetail.objects.get(customer_id=customer_id)
        except CustomerDetail.DoesNotExist:
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Only allow updating specific fields
        allowed_fields = ['full_name', 'father_name', 'gender', 'date_of_birth', 'contact', 'email', 'adhar_number', 'pan_number', 'voter_number']
        updated = False
        for field in allowed_fields:
            if field in request.data:
                setattr(customer, field, request.data[field])
                updated = True

        if updated:
            customer.save()
            return Response({'success': True, 'message': 'Customer information updated.'}, status=status.HTTP_200_OK)
        else:
            return Response({'detail': 'No valid fields to update.'}, status=status.HTTP_400_BAD_REQUEST)
### --------- after applied form details edit --------- ###

class DocumentReuploadAPI(APIView):
    parser_classes = [MultiPartParser, FormParser]
    
    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        try:
            agent_id = request.session.get('agent_id')
            if not agent_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            
            agent = Agent.objects.get(agent_id=agent_id)
            data = request.data
            files = request.FILES
            
            # Validate required fields
            required_fields = ['customer_id', 'document_request_id', 'document_type']
            for field in required_fields:
                if field not in data:
                    return Response({'detail': f'{field} is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if 'uploaded_file' not in files:
                return Response({'detail': 'Document file is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get customer and document request
            try:
                customer = CustomerDetail.objects.get(customer_id=data['customer_id'], agent=agent)
                loan_application = customer.loan_application
                document_request = DocumentRequest.objects.get(
                    id=data['document_request_id'],
                    loan_application=loan_application,
                    is_resolved=False
                )
            except (CustomerDetail.DoesNotExist, DocumentRequest.DoesNotExist):
                return Response({'detail': 'Customer or document request not found.'}, status=status.HTTP_404_NOT_FOUND)
            
            # Create document reupload
            reupload = DocumentReupload.objects.create(
                document_request=document_request,
                loan_application=loan_application,
                document_type=data['document_type'],
                uploaded_file=files['uploaded_file'],
                agent_note=data.get('agent_note', ''),
                uploaded_by=agent
            )
            
            # Mark document request as resolved
            document_request.mark_as_resolved()

            # Check if all document requests for this loan are resolved
            remaining_requests = DocumentRequest.objects.filter(
                loan_application=loan_application,
                is_resolved=False
            ).exists()
            
            # Update loan application status to resubmitted only if all requests are resolved
            if loan_application and not remaining_requests:
                loan_application.status = 'resubmitted'
                loan_application.save()
            # # Update loan application status to resubmitted
            # loan_application = customer.loan_application
            # if loan_application:
            #     loan_application.status = 'resubmitted'
            #     loan_application.save()
            
            return Response({
                'success': True,
                'message': 'Document uploaded successfully',
                'reupload_id': reupload.id
            }, status=status.HTTP_201_CREATED)
            
        except Agent.DoesNotExist:
            return Response({'detail': 'Agent not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoanApplicationAPI(APIView):
    def get(self, request):
        agent_id = request.session.get('agent_id')
        loan_applications = LoanApplication.objects.filter(agent__agent_id=agent_id)
        serializer = LoanApplicationListSerializer(loan_applications, many=True)
        return Response(serializer.data)

class LoanDocumentRequestAPI(APIView):
    def get(self, request):
        agent_id = request.session.get('agent_id')
        loan_applications = LoanApplication.objects.filter(agent__agent_id=agent_id)
        requests = DocumentRequest.objects.filter(loan_application__in=loan_applications)
        serializer = DocumentRequestSerializer(requests, many=True)
        return Response(serializer.data)

class LoanRejectApplicationAPI(APIView):
    def get(self, request):
        agent_id = request.session.get('agent_id')
        loan_application = LoanApplication.objects.filter(
            agent__agent_id=agent_id,
            status__in=['rejected_by_branch', 'reject', 'rejected','hq_rejected']
        )
        serializer = LoanRejectedSerializer(loan_application, many=True)
        return Response(serializer.data)

class LoanApproveApplicationAPI(APIView):
    def get(self, request):
        agent_id = request.session.get('agent_id')
        loan_application = LoanApplication.objects.filter(
            agent__agent_id = agent_id,
            status__in=['branch_approved', 'hq_approved']
        )   
        serializer = LoanApprovedSerializer(loan_application, many= True)
        return Response(serializer.data)

class AgentApplicationDetailAPI(APIView):
    def get(self, request, customer_id, loan_ref_no):
        agent_id = request.session.get('agent_id')
        try:
            # Find the LoanApplication for this customer and agent
            loan_app = LoanApplication.objects.get(loan_ref_no=loan_ref_no, agent__agent_id=agent_id, customer__customer_id=customer_id)
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        # Build the response dict manually for full control
        customer = loan_app.customer
        address = customer.address if hasattr(customer, 'address') else None
        loans = loan_app.loan_details.select_related('loan_category__main_category').all()
        documents = getattr(loan_app, 'documents', None)
        agent = loan_app.agent

        first_loan = loans.first()
        is_shop_active = bool(
            first_loan
            and getattr(first_loan, 'loan_category', None)
            and getattr(first_loan.loan_category, 'main_category', None)
            and bool(getattr(first_loan.loan_category.main_category, 'is_shop_active', False))
        )

        # Helper to get latest document reupload or original
        from loan.models import DocumentReupload
        def get_latest_document(loan_application, doc_type, original_file):
            # Special handling for residential proof: check both possible doc_type values
            if doc_type in ['residential_proof', 'residential_proof_file']:
                reupload = DocumentReupload.objects.filter(
                    loan_application=loan_application,
                    document_type__in=['residential_proof', 'residential_proof_file']
                ).order_by('-uploaded_at').first()
            else:
                reupload = DocumentReupload.objects.filter(
                    loan_application=loan_application,
                    document_type=doc_type
                ).order_by('-uploaded_at').first()
            if reupload and reupload.uploaded_file:
                try:
                    return reupload.uploaded_file.url
                except Exception:
                    return None
            return getattr(original_file, 'url', None) if original_file else None

        documents_data = None
        if documents:
            documents_data = {
                'id_proof': get_latest_document(loan_app, 'id_proof', documents.id_proof),
                'pan_card_document': get_latest_document(loan_app, 'pan_card_document', getattr(documents, 'pan_card_document', None)),
                'id_proof_back': get_latest_document(loan_app, 'id_proof_back', documents.id_proof_back),
                'income_proof': get_latest_document(loan_app, 'income_proof', documents.income_proof),
                'photo': get_latest_document(loan_app, 'photo', documents.photo),
                'signature': get_latest_document(loan_app, 'signature', documents.signature),
                'collateral': get_latest_document(loan_app, 'collateral', documents.collateral),
                'residential_proof_file': get_latest_document(loan_app, 'residential_proof', documents.residential_proof_file),
            }

        # Get document reuploads and reviews for history
        document_reuploads = loan_app.document_reuploads.all()
        document_reviews = loan_app.document_reviews.all()
        document_requests = loan_app.document_requests.all()
        customer_detail_snapshot = loan_app.customer_snapshot.get('customer_details', {}) if loan_app.customer_snapshot else {}
        customer_address_snapshot = loan_app.customer_snapshot.get('address', {}) if loan_app.customer_snapshot else {}
        customer_documents_snapshot = loan_app.customer_snapshot.get('documents', {}) if loan_app.customer_snapshot else {}
        customer_bank_details_snapshot = loan_app.customer_snapshot.get('bank_details', {}) if loan_app.customer_snapshot else {}
        print(customer_detail_snapshot)
        is_old_loan = customer.loan_application_id != loan_app.loan_ref_no
        print('is_old_loan -> ', is_old_loan)

        data = {
            'loan_ref_no': loan_app.loan_ref_no,
            'customer_id': customer.customer_id if customer else '',
            'full_name':  self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'full_name'),
            'father_name': self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'father_name'),
            'date_of_birth': self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'date_of_birth'),
            'gender': self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'gender'),
            'contact': self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'contact'),
            'email': self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'email'),
            'adhar_number':  self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'adhar_number'), 
            'pan_number':  self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'pan_number'), 
            'voter_number':  self._get_customer_details(customer, is_old_loan, customer_detail_snapshot, 'voter_number'), 
            'status': loan_app.status,
            'submitted_at': loan_app.submitted_at,
            'agent': AgentSerializer(agent).data if agent else None,
            'shop': {
                'shop_id': loan_app.shop.shop_id,
                'name': loan_app.shop.name
            } if loan_app.shop else None,
            'is_shop_active': is_shop_active,
            'loans': CustomerLoanDetailSerializer(loans, many=True).data,
            'address': customer_address_snapshot if is_old_loan else CustomerAddressSerializer(address).data if address else None,
            'customer_account': (
                customer_bank_details_snapshot if is_old_loan else 
                CustomerAccountSerializer(customer.account).data
                if customer and hasattr(customer, 'account') and customer.account else None
            ),
            'documents': documents_data,
            'document_requests': [
                {
                    'id': request.id,
                    'document_type': request.document_type,
                    'reason': request.reason,
                    'comment': request.comment,
                    'requested_by': (
                        request.requested_by.get_full_name() if request.requested_by and hasattr(request.requested_by, 'get_full_name')
                        else f"{request.requested_by.first_name} {request.requested_by.last_name}" if request.requested_by and hasattr(request.requested_by, 'first_name')
                        else str(request.requested_by) if request.requested_by else None
                    ),
                    'requested_by_hq': getattr(request.requested_by_hq, 'get_full_name', lambda: str(request.requested_by_hq) if request.requested_by_hq else None)() if request.requested_by_hq else None,
                    'requested_at': request.requested_at,
                    'is_resolved': request.is_resolved,
                    'resolved_at': request.resolved_at,
                    'category': 'hq' if request.requested_by_hq else 'branch'
                }
                for request in document_requests
            ],
            'document_reuploads': [
                {
                    'id': reupload.id,
                    'document_type': reupload.document_type,
                    'uploaded_file': reupload.uploaded_file.url if reupload.uploaded_file else None,
                    'agent_note': reupload.agent_note,
                    'uploaded_by': reupload.uploaded_by.full_name if reupload.uploaded_by else None,
                    'uploaded_at': reupload.uploaded_at,
                    'reviews': [
                        {
                            'decision': review.decision,
                            'review_comment': review.review_comment,
                            'reviewed_by': review.reviewed_by.user.get_full_name() if (review.reviewed_by and hasattr(review.reviewed_by, 'user') and hasattr(review.reviewed_by.user, 'get_full_name')) else (str(review.reviewed_by) if review.reviewed_by else None),
                            'reviewed_at': review.reviewed_at,
                        }
                        for review in reupload.reviews.all()
                    ]
                }
                for reupload in document_reuploads
            ],
            'document_reviews': [
                {
                    'decision': review.decision,
                    'review_comment': review.review_comment,
                    'reviewed_by': review.reviewed_by.user.get_full_name() if (review.reviewed_by and hasattr(review.reviewed_by, 'user') and hasattr(review.reviewed_by.user, 'get_full_name')) else (str(review.reviewed_by) if review.reviewed_by else None),
                    'reviewed_at': review.reviewed_at,
                    'document_type': review.document_reupload.document_type if review.document_reupload else None,
                }
                for review in document_reviews
            ]
        }
        print(data['address'])
        return Response(data)
    
    def _get_customer_details(self, customer:CustomerDetail, isOld:bool, customer_detail_snapshot, field_name):
        return getattr(customer, field_name, '') if not isOld else customer_detail_snapshot.get(field_name, '')

class ApplicationTrackingAPI(APIView):
    def get(self, request, loan_ref_no):
        try:
            application = LoanApplication.objects.select_related('agent', 'branch', 'customer').get(loan_ref_no=loan_ref_no)
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=404)
        serializer = LoanApplicationSerializer(application)
        return Response(serializer.data)


# for category select 
class LoanCategoryListAPI(APIView):
    def get(self, request):
        main_category_id = request.GET.get('main_category_id')
        categories = LoanCategory.objects.filter(is_active=True).order_by('name')
        if main_category_id:
            categories = categories.filter(main_category_id=main_category_id)
        data = [
            {"id": cat.category_id, "name": cat.name}
            for cat in categories
        ]
        return Response(data)

# for tenure select 
class LoanTenureListAPI(APIView):
    def get(self, request):
        tenures = LoanTenure.objects.filter(is_active=True).order_by('value', 'unit')
        data = [
            {
                "id": tenure.tenure_id,
                "value": tenure.value,
                "unit": tenure.unit,
                "interest_rate": float(tenure.interest_rate.rate_of_interest) if tenure.interest_rate else None,
                "interest_id": tenure.interest_rate.interest_id if tenure.interest_rate else None,
                "display": f"{tenure.value} {tenure.unit} ({tenure.interest_rate.rate_of_interest if tenure.interest_rate else ''}%)"
            }
            for tenure in tenures
        ]
        return Response(data)

# Tenure API filtered by subcategory
class LoanSubCategoryTenureListAPI(APIView):
    def get(self, request):
        subcategory_id = request.GET.get('subcategory_id')
        if not subcategory_id:
            return Response({"error": "subcategory_id is required"}, status=400)
            
        try:
            # Get the subcategory and its main category
            subcategory = LoanCategory.objects.get(category_id=subcategory_id, is_active=True)
            main_category = subcategory.main_category
            
            if not main_category:
                return Response({"error": "Subcategory has no main category"}, status=400)
            
            # Filter tenures by the main category
            tenures = LoanTenure.objects.filter(
                interest_rate__main_category=main_category,
                is_active=True
            ).order_by('value', 'unit')
            
            data = [
                {
                    "id": tenure.tenure_id,
                    "value": tenure.value,
                    "unit": tenure.unit,
                    "interest_rate": float(tenure.interest_rate.rate_of_interest) if tenure.interest_rate else None,
                    "interest_id": tenure.interest_rate.interest_id if tenure.interest_rate else None,
                    "display": f"{tenure.value} {tenure.unit} ({tenure.interest_rate.rate_of_interest if tenure.interest_rate else ''}%)"
                }
                for tenure in tenures
            ]
            return Response(data)
            
        except LoanCategory.DoesNotExist:
            return Response({"error": "Subcategory not found"}, status=404)

# Main Category API
class LoanMainCategoryListAPI(APIView):
    def get(self, request):
        main_categories = LoanMainCategory.objects.filter(is_active=True).order_by('name')
        data = [
            {
                "id": category.main_category_id,
                "name": category.name,
                "category_count": LoanCategory.objects.filter(main_category=category, is_active=True).count(),
                "is_shop_active": category.is_shop_active,
            }
            for category in main_categories
        ]
        return Response(data)

# Sub Categories API (filtered by main category)
class LoanSubCategoryListAPI(APIView):
    def get(self, request):
        main_category_id = request.GET.get('main_category_id')
        if not main_category_id:
            return Response({"error": "main_category_id is required"}, status=400)
            
        try:
            main_category = LoanMainCategory.objects.get(main_category_id=main_category_id, is_active=True)
            categories = LoanCategory.objects.filter(main_category=main_category, is_active=True).order_by('name')
            data = [
                {
                    "id": category.category_id,
                    "name": category.name,
                    "main_category": main_category.name,
                    "has_product_categories": ProductCategory.objects.filter(loan_category=category, is_active=True).exists()
                }
                for category in categories
            ]
            return Response(data)
        except LoanMainCategory.DoesNotExist:
            return Response({"error": "Main category not found"}, status=404)

# Product Main Category API
class ProductCategoryListAPI(APIView):
    def get(self, request):
        loan_category_id = request.GET.get('loan_category_id')
        main_categories = ProductCategory.objects.filter(is_active=True)
        if loan_category_id:
            main_categories = main_categories.filter(loan_category_id=loan_category_id)
        main_categories = main_categories.order_by('name')
        data = [
            {
                "id": category.main_category_id,
                "name": category.name,
                "subcategory_count": ProductSubCategory.objects.filter(main_category=category, is_active=True).count()
            }
            for category in main_categories
        ]
        return Response(data)

# Product Subcategories API (filtered by main category)
class ProductSubCategoryListAPI(APIView):
    def get(self, request):
        main_category_id = request.GET.get('main_category_id')
        if not main_category_id:
            return Response({"error": "main_category_id is required"}, status=400)
            
        try:
            main_category = ProductCategory.objects.get(main_category_id=main_category_id, is_active=True)
            subcategories = ProductSubCategory.objects.filter(main_category=main_category, is_active=True).order_by('name')
            data = [
                {
                    "id": subcategory.sub_category_id,
                    "name": subcategory.name,
                    "main_category": main_category.name
                }
                for subcategory in subcategories
            ]
            return Response(data)
        except ProductCategory.DoesNotExist:
            return Response({"error": "Main category not found"}, status=404)

# Product Types API (filtered by subcategory)
class ProductListAPI(APIView):
    def get(self, request):
        subcategory_id = request.GET.get('subcategory_id')
        if not subcategory_id:
            return Response({"error": "subcategory_id is required"}, status=400)
            
        try:
            subcategory = ProductSubCategory.objects.get(sub_category_id=subcategory_id, is_active=True)
            products = Product.objects.filter(sub_category=subcategory, is_active=True).order_by('name')
            data = [
                {
                    "id": product.product_id,
                    "name": product.name,
                    "price": float(product.price),
                    "subcategory": subcategory.name
                }
                for product in products
            ]
            return Response(data)
        except ProductSubCategory.DoesNotExist:
            return Response({"error": "Subcategory not found"}, status=404)

# Loan Deductions API
class LoanDeductionsListAPI(APIView):
    def get(self, request):
        main_category_id = request.GET.get('main_category_id')
        if not main_category_id:
            return Response({"error": "main_category_id is required"}, status=400)
            
        try:
            main_category = LoanMainCategory.objects.get(main_category_id=main_category_id, is_active=True)
            deductions = Deductions.objects.filter(main_category=main_category, is_active=True).order_by('deduction_name')
            data = [
                {
                    "id": deduction.deduction_id,
                    "name": deduction.deduction_name,
                    "deduction_type": deduction.deduction_type,
                    "deduction_value": float(deduction.deduction_value),
                }
                for deduction in deductions
            ]
            return Response(data)
        except LoanMainCategory.DoesNotExist:
            return Response({"error": "Main category not found"}, status=404)

# EMI Collect view #

class EmiCollectView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'emi/emi-collection.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.request.session.get('agent_id')

        qs = (
            EmiAgentAssign.objects
            .select_related(
                'agent',
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'assigned_by',
                'assigned_by__branch'
            )
            .order_by('emi__loan_application__loan_ref_no', 'installment_date', 'emi__id')
        )

        qs = qs.exclude(
            Q(emi__loan_application__close_requests__status__in=['pending', 'approved'])
            | Q(reschedule_emi__loan_application__close_requests__status__in=['pending', 'approved'])
        ).distinct()

        if agent_id:
            qs = qs.filter(agent__agent_id=agent_id)

        # Build a set of EMI ids that are already collected/verified
        emi_ids = list(qs.values_list('emi__id', flat=True))
        res_emi_ids = list(qs.values_list('reschedule_emi__id', flat=True))

        collected_original = set(
            EmiCollectionDetail.objects
            .filter(emi_id__in=[eid for eid in emi_ids if eid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('emi_id', flat=True)
        )
        collected_rescheduled = set(
            EmiCollectionDetail.objects
            .filter(reschedule_emi_id__in=[rid for rid in res_emi_ids if rid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('reschedule_emi_id', flat=True)
        )

        # Pick first pending per loan (same logic as EmiCollectionListAPIView?first=1)
        first_by_loan = []
        seen_loans = set()
        for assign in qs:
            emi_obj = assign.emi or getattr(assign, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None)
            loan = getattr(loan_app, 'loan_ref_no', None)
            if not loan or loan in seen_loans:
                continue

            is_collected = False
            if assign.emi_id and assign.emi_id in collected_original:
                is_collected = True
            if getattr(assign, 'reschedule_emi_id', None) and assign.reschedule_emi_id in collected_rescheduled:
                is_collected = True
            if is_collected:
                continue

            first_by_loan.append(assign)
            seen_loans.add(loan)

        paginator = Paginator(first_by_loan, 15)
        page_number = self.request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        serializer = EMICollectSerializer(page_obj.object_list, many=True)
        context['rows'] = serializer.data
        context['page_obj'] = page_obj
        context['has_next'] = page_obj.has_next()
        context['next_page_number'] = page_obj.next_page_number() if page_obj.has_next() else None
        return context


class EmiCollectionListPagePartialView(AgentSessionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        qs = (
            EmiAgentAssign.objects
            .select_related(
                'agent',
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'assigned_by',
                'assigned_by__branch'
            )
            .order_by('emi__loan_application__loan_ref_no', 'installment_date', 'emi__id')
        )

        qs = qs.exclude(
            Q(emi__loan_application__close_requests__status__in=['pending', 'approved'])
            | Q(reschedule_emi__loan_application__close_requests__status__in=['pending', 'approved'])
        ).distinct()

        if agent_id:
            qs = qs.filter(agent__agent_id=agent_id)

        # Build a set of EMI ids that are already collected/verified
        emi_ids = list(qs.values_list('emi__id', flat=True))
        res_emi_ids = list(qs.values_list('reschedule_emi__id', flat=True))

        collected_original = set(
            EmiCollectionDetail.objects
            .filter(emi_id__in=[eid for eid in emi_ids if eid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('emi_id', flat=True)
        )
        collected_rescheduled = set(
            EmiCollectionDetail.objects
            .filter(reschedule_emi_id__in=[rid for rid in res_emi_ids if rid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('reschedule_emi_id', flat=True)
        )

        # Pick first pending per loan (same logic as EmiCollectionListAPIView?first=1)
        first_by_loan = []
        seen_loans = set()
        for assign in qs:
            emi_obj = assign.emi or getattr(assign, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None)
            loan = getattr(loan_app, 'loan_ref_no', None)
            if not loan or loan in seen_loans:
                continue

            is_collected = False
            if assign.emi_id and assign.emi_id in collected_original:
                is_collected = True
            if getattr(assign, 'reschedule_emi_id', None) and assign.reschedule_emi_id in collected_rescheduled:
                is_collected = True
            if is_collected:
                continue

            first_by_loan.append(assign)
            seen_loans.add(loan)

        paginator = Paginator(first_by_loan, 15)
        page_number = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return HttpResponse('')

        serializer = EMICollectSerializer(page_obj.object_list, many=True)

        html = render_to_string(
            'emi/partials/emi-collect-rows.html',
            {'rows': serializer.data, 'page_obj': page_obj},
            request=request,
        )
        return HttpResponse(html)


class EmiCollectionListAPIView(APIView):
    def get(self, request):
        agent_id = request.session.get('agent_id')
        first_only = request.GET.get('first') in ('1', 'true', 'yes', 'y', 'True')
        

        emi_collect_qs = (
            EmiAgentAssign.objects
            .select_related(
                'agent',
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'assigned_by',
                'assigned_by__branch'
            )
            .order_by('emi__loan_application__loan_ref_no', 'installment_date', 'emi__id')
        )

        emi_collect_qs = emi_collect_qs.exclude(
            Q(emi__loan_application__close_requests__status__in=['pending', 'approved'])
            | Q(reschedule_emi__loan_application__close_requests__status__in=['pending', 'approved'])
        ).distinct()

        if agent_id:
            emi_collect_qs = emi_collect_qs.filter(agent__agent_id=agent_id)

        if not first_only:
            serializer = EMICollectSerializer(emi_collect_qs, many=True)
            return Response(serializer.data)

        # Build a set of EMI ids that are already collected/verified
        emi_ids = list(emi_collect_qs.values_list('emi__id', flat=True))
        res_emi_ids = list(emi_collect_qs.values_list('reschedule_emi__id', flat=True))

        collected_original = set(
            EmiCollectionDetail.objects
            .filter(emi_id__in=[eid for eid in emi_ids if eid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('emi_id', flat=True)
        )
        collected_rescheduled = set(
            EmiCollectionDetail.objects
            .filter(reschedule_emi_id__in=[rid for rid in res_emi_ids if rid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('reschedule_emi_id', flat=True)
        )

        # Pick first pending per loan
        first_by_loan = []
        seen_loans = set()
        for assign in emi_collect_qs:
            emi_obj = assign.emi or getattr(assign, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None)
            loan = getattr(loan_app, 'loan_ref_no', None)
            if not loan or loan in seen_loans:
                continue
            # Skip collected ones (original or rescheduled), continue to look for first not collected within this loan
            is_collected = False
            if assign.emi_id and assign.emi_id in collected_original:
                is_collected = True
            if getattr(assign, 'reschedule_emi_id', None) and assign.reschedule_emi_id in collected_rescheduled:
                is_collected = True
            if is_collected:
                continue
            first_by_loan.append(assign)
            seen_loans.add(loan)

        # Edge case: if all EMIs for a loan are collected, nothing for that loan is included
        serializer = EMICollectSerializer(first_by_loan, many=True)
        return Response(serializer.data)

class CollectedEMIView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'emi/collected-emi.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.request.session.get('agent_id')
        if not agent_id:
            return context

        collections = (
            EmiCollectionDetail.objects
            .select_related(
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'assignment',
                'assignment__assigned_by',
                'collected_by_agent',
                'collected_by_branch',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'reschedule_emi__loan_application__branch',
            )
            .filter(collected_by_agent__agent_id=agent_id, status='collected')
            .order_by('-collected_at')
        )

        rows = []
        for c in collections:
            # Support both original and rescheduled EMIs.
            emi_obj = getattr(c, 'emi', None) or getattr(c, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None)
            customer = getattr(loan_app, 'customer', None)
            assigned_by = getattr(c.assignment, 'assigned_by', None) if c.assignment else None
            branch = getattr(assigned_by, 'branch', None) if assigned_by else getattr(loan_app, 'branch', None)

            # Ensure precise 2-decimal totals for display in the template
            try:
                amt = Decimal(str(getattr(c, 'amount_received', Decimal('0')) or 0))
            except Exception:
                amt = Decimal('0')
            try:
                pen = Decimal(str(getattr(c, 'penalty_received', Decimal('0')) or 0))
            except Exception:
                pen = Decimal('0')
            row_total = (amt + pen).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            rows.append({
                'collected_id': getattr(c, 'collected_id', None),
                'assignment_id': getattr(c.assignment, 'assignment_id', None),
                'loan_ref_no': getattr(loan_app, 'loan_ref_no', None),
                'customer_name': getattr(customer, 'full_name', None),
                'branch_name': getattr(branch, 'branch_name', None) if branch else None,
                'emi_amount': getattr(emi_obj, 'installment_amount', None),
                'principal_amount': getattr(emi_obj, 'principal_amount', None),
                'interest_amount': getattr(emi_obj, 'interest_amount', None),
                'installment_date': getattr(emi_obj, 'installment_date', None),
                'collected_amount': getattr(c, 'amount_received', None),
                'penalty_received': getattr(c, 'penalty_received', None),
                'total_collected': row_total,
                'collected_at': getattr(c, 'collected_at', None),
                'status': getattr(c, 'status', None),
            })

        context['collections'] = rows

        # Compute summary totals for cards
        # total_emi = Decimal('0')
        total_collected = Decimal('0')
        total_emi_collected = Decimal('0')
        total_penalty = Decimal('0')
        for r in rows:
            coll_amt = Decimal(str(r.get('collected_amount') or 0))
            emi_amt = Decimal(str(r.get('emi_amount') or 0))
            penalty = Decimal(str(r.get('penalty_received') or 0))
            total_collected += (coll_amt + penalty)
            total_emi_collected += emi_amt
            total_penalty += penalty

        context['summary'] = {
            'collected': float(total_collected),
            'emi_collected': float(total_emi_collected),
            'penalty_collected': float(total_penalty),
        }
        return context

class GetEmiCollectedDetailAPI(AgentSessionRequiredMixin, APIView):
    def get(self, request, collected_id=None, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id or not collected_id:
            return Response(
                {'error': 'Agent ID and Collection ID are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            coll = (
                EmiCollectionDetail.objects
                .select_related(
                    'emi',
                    'emi__loan_application',
                    'emi__loan_application__customer',
                    'emi__loan_application__branch',
                    'assignment',
                    'assignment__assigned_by',
                    'collected_by_agent',
                    'collected_by_branch',
                    'reschedule_emi',
                    'reschedule_emi__loan_application',
                    'reschedule_emi__loan_application__customer',
                    'reschedule_emi__loan_application__branch',
                )
                .get(collected_id=collected_id, collected_by_agent__agent_id=agent_id)
            )
        except EmiCollectionDetail.DoesNotExist:
            return Response(
                {'error': 'Collection not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Prefer the original EMI; if not present, use rescheduled EMI so
        # details work for both types.
        emi_obj = getattr(coll, 'emi', None) or getattr(coll, 'reschedule_emi', None)
        loan_app = emi_obj.loan_application if emi_obj else None
        customer = getattr(loan_app, 'customer', None)
        branch = getattr(loan_app, 'branch', None)
        assigned_by = getattr(coll.assignment, 'assigned_by', None) if coll.assignment else None

        # Determine collector info
        collector = {}
        if coll.collected_by_agent:
            collector = {
                'name': coll.collected_by_agent.get_full_name(),
                'type': 'agent'
            }
        elif coll.collected_by_branch:
            collector = {
                'name': str(coll.collected_by_branch),
                'type': 'branch'
            }

        response_data = {
            'collected_id': coll.collected_id,
            'loan_ref_no': loan_app.loan_ref_no if loan_app else None,
            'customer_name': customer.full_name if customer else None,
            'branch_name': branch.branch_name if branch else None,
            'amount_received': float(coll.amount_received) if coll.amount_received is not None else None,
            'principal_received': float(coll.principal_received) if coll.principal_received is not None else None,
            'interest_received': float(coll.interest_received) if coll.interest_received is not None else None,
            'late_fee': float(coll.penalty_received) if coll.penalty_received is not None else 0.0,
            'payment_mode': coll.payment_mode,
            'payment_reference': coll.payment_reference,
            'collector': collector,
            'collected_at': coll.collected_at.isoformat() if coll.collected_at else None,
            'status': coll.status,
            'remarks': coll.remarks,
        }

        return Response(response_data)
class AssignedEMIView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'emi/assigned-emi.html'    

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.request.session.get('agent_id')

        try:
            agent = Agent.objects.select_related('branch').get(agent_id=agent_id)
        except Agent.DoesNotExist:
            context['rows'] = []
            context['has_next'] = False
            context['next_page_number'] = None
            return context

        status_filter = self.request.GET.get('status')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        search = self.request.GET.get('search')

        status_sq = (
            EmiCollectionDetail.objects
            .filter(assignment__assignment_id=OuterRef('assignment_id'))
            .order_by('-collected_at')
            .values('status')[:1]
        )
        collected_at_sq = (
            EmiCollectionDetail.objects
            .filter(assignment__assignment_id=OuterRef('assignment_id'))
            .order_by('-collected_at')
            .values('collected_at')[:1]
        )

        qs = (
            EmiAgentAssign.objects
            .select_related(
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'emi__loan_application__branch',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'reschedule_emi__loan_application__branch',
                'assigned_by',
                'agent',
            )
            .filter(agent=agent, is_active=True)
            .annotate(latest_status=Subquery(status_sq), collected_at=Subquery(collected_at_sq))
            .order_by('-assigned_at')
        )

        if status_filter and status_filter != 'all':
            if status_filter.lower() == 'pending':
                qs = qs.exclude(Q(collections__status='collected') | Q(collections__status='verified'))
            else:
                qs = qs.filter(collections__status=status_filter)

        if date_from and date_to:
            try:
                df = make_aware(datetime.strptime(date_from, '%Y-%m-%d'))
                dt = make_aware(datetime.strptime(date_to, '%Y-%m-%d')).replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
                qs = qs.filter(Q(installment_date__range=(df, dt))).distinct()
            except Exception:
                pass

        if search:
            search_term = search.strip()
            if search_term:
                qs = qs.filter(
                    Q(assignment_id__icontains=search_term)
                    |
                    Q(emi__loan_application__loan_ref_no__icontains=search_term)
                    |
                    Q(emi__loan_application__customer__full_name__icontains=search_term)
                    |
                    Q(reschedule_emi__loan_application__loan_ref_no__icontains=search_term)
                    |
                    Q(reschedule_emi__loan_application__customer__full_name__icontains=search_term)
                ).distinct()

        rows_all = []
        for a in qs:
            emi_obj = getattr(a, 'emi', None) or getattr(a, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None) if emi_obj else None
            customer = getattr(loan_app, 'customer', None) if loan_app else None
            branch = getattr(loan_app, 'branch', None) if loan_app else None

            rows_all.append({
                'assignment_id': a.assignment_id,
                'loan_ref_no': getattr(loan_app, 'loan_ref_no', None) if loan_app else None,
                'customer_name': getattr(customer, 'full_name', None) if customer else None,
                'branch_name': getattr(branch, 'branch_name', None) if branch else None,
                'emi_amount': float(a.installment_amount) if a.installment_amount is not None else 0.0,
                'principal_amount': float(a.principal_amount) if a.principal_amount is not None else 0.0,
                'interest_amount': float(a.interest_amount) if a.interest_amount is not None else 0.0,
                'installment_date': a.installment_date.strftime('%d-%m-%Y') if a.installment_date else None,
                'collected_at': a.collected_at.strftime('%d-%m-%Y') if a.collected_at else None,
                'status': getattr(a, 'latest_status', None) or 'pending',
            })

        paginator = Paginator(rows_all, 15)
        page_number = self.request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        context['rows'] = list(page_obj.object_list)
        context['has_next'] = page_obj.has_next()
        context['next_page_number'] = page_obj.next_page_number() if page_obj.has_next() else None
        return context


class AssignedEmiListPagePartialView(AgentSessionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        try:
            agent = Agent.objects.select_related('branch').get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return HttpResponse('')

        status_filter = request.GET.get('status')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        search = request.GET.get('search')

        status_sq = (
            EmiCollectionDetail.objects
            .filter(assignment__assignment_id=OuterRef('assignment_id'))
            .order_by('-collected_at')
            .values('status')[:1]
        )
        collected_at_sq = (
            EmiCollectionDetail.objects
            .filter(assignment__assignment_id=OuterRef('assignment_id'))
            .order_by('-collected_at')
            .values('collected_at')[:1]
        )

        qs = (
            EmiAgentAssign.objects
            .select_related(
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'emi__loan_application__branch',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'reschedule_emi__loan_application__branch',
                'assigned_by',
                'agent',
            )
            .filter(agent=agent, is_active=True)
            .annotate(latest_status=Subquery(status_sq), collected_at=Subquery(collected_at_sq))
            .order_by('-assigned_at')
        )

        if status_filter and status_filter != 'all':
            if status_filter.lower() == 'pending':
                qs = qs.exclude(Q(collections__status='collected') | Q(collections__status='verified'))
            else:
                qs = qs.filter(collections__status=status_filter)

        if date_from and date_to:
            try:
                df = make_aware(datetime.strptime(date_from, '%Y-%m-%d'))
                dt = make_aware(datetime.strptime(date_to, '%Y-%m-%d')).replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
                qs = qs.filter(Q(installment_date__range=(df, dt))).distinct()
            except Exception:
                pass

        if search:
            search_term = search.strip()
            if search_term:
                qs = qs.filter(
                    Q(assignment_id__icontains=search_term)
                    |
                    Q(emi__loan_application__loan_ref_no__icontains=search_term)
                    |
                    Q(emi__loan_application__customer__full_name__icontains=search_term)
                    |
                    Q(reschedule_emi__loan_application__loan_ref_no__icontains=search_term)
                    |
                    Q(reschedule_emi__loan_application__customer__full_name__icontains=search_term)
                ).distinct()

        rows_all = []
        for a in qs:
            emi_obj = getattr(a, 'emi', None) or getattr(a, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None) if emi_obj else None
            customer = getattr(loan_app, 'customer', None) if loan_app else None
            branch = getattr(loan_app, 'branch', None) if loan_app else None

            rows_all.append({
                'assignment_id': a.assignment_id,
                'loan_ref_no': getattr(loan_app, 'loan_ref_no', None) if loan_app else None,
                'customer_name': getattr(customer, 'full_name', None) if customer else None,
                'branch_name': getattr(branch, 'branch_name', None) if branch else None,
                'emi_amount': float(a.installment_amount) if a.installment_amount is not None else 0.0,
                'principal_amount': float(a.principal_amount) if a.principal_amount is not None else 0.0,
                'interest_amount': float(a.interest_amount) if a.interest_amount is not None else 0.0,
                'installment_date': a.installment_date.strftime('%d-%m-%Y') if a.installment_date else None,
                'collected_at': a.collected_at.strftime('%d-%m-%Y') if a.collected_at else None,
                'status': getattr(a, 'latest_status', None) or 'pending',
            })

        paginator = Paginator(rows_all, 15)
        page_number = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return HttpResponse('')

        html = render_to_string(
            'emi/partials/assigned-emi-rows.html',
            {'rows': list(page_obj.object_list), 'page_obj': page_obj},
            request=request,
        )
        return HttpResponse(html)


class AgentEmiStatementAPIView(APIView):
    def get(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Agent authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        loan_ref_no = request.query_params.get('loan_ref_no')
        if not loan_ref_no:
            return Response({'detail': 'loan_ref_no is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            agent = Agent.objects.select_related('branch').get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'detail': 'Agent not found.'}, status=status.HTTP_403_FORBIDDEN)

        if not EmiAgentAssign.objects.filter(agent=agent, emi__loan_application__loan_ref_no=loan_ref_no).exists():
            return Response({'detail': 'Loan EMI schedule not assigned to this agent.'}, status=status.HTTP_404_NOT_FOUND)

        schedules = (
            LoanEMISchedule.objects
            .filter(loan_application__loan_ref_no=loan_ref_no)
            .order_by('installment_date')
        )
        if not schedules.exists():
            return Response({'detail': 'No EMI schedules found for this loan.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = LoanEMIScheduleSerializer(schedules, many=True)
        return Response({
            'loan_ref_no': loan_ref_no,
            'schedules': serializer.data,
            'agent_list': []
        }, status=status.HTTP_200_OK)


class AgentLoanEmiCollectedAPIView(APIView):
    def get(self, request, loan_ref_no, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Agent authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'detail': 'Agent not found.'}, status=status.HTTP_403_FORBIDDEN)

        if not EmiAgentAssign.objects.filter(agent=agent, emi__loan_application__loan_ref_no=loan_ref_no).exists():
            return Response({'detail': 'Loan EMI data not available for this agent.'}, status=status.HTTP_404_NOT_FOUND)

        paid_emis = (
            LoanEMISchedule.objects
            .select_related('loan_application')
            .filter(loan_application__loan_ref_no=loan_ref_no, paid=True)
            .order_by('-paid_date', '-installment_date')
        )

        results = [
            {
                'emi_id': emi.id,
                'loan_ref_no': emi.loan_application.loan_ref_no,
                'installment_date': emi.installment_date,
                'installment_amount': emi.installment_amount,
                'principal_amount': emi.principal_amount,
                'interest_amount': emi.interest_amount,
                'paid': emi.paid,
                'paid_date': emi.paid_date,
                'payment_reference': emi.payment_reference,
            }
            for emi in paid_emis
        ]
        return Response({'count': len(results), 'results': results}, status=status.HTTP_200_OK)


class AgentLoanRemainingAPIView(APIView):
    def get(self, request, loan_ref_no, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Agent authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            agent = Agent.objects.select_related('branch').get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'detail': 'Agent not found.'}, status=status.HTTP_403_FORBIDDEN)

        if not EmiAgentAssign.objects.filter(agent=agent, emi__loan_application__loan_ref_no=loan_ref_no).exists():
            return Response({'detail': 'Loan not assigned to this agent.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            loan_application = LoanApplication.objects.get(loan_ref_no=loan_ref_no)
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Loan not found.'}, status=status.HTTP_404_NOT_FOUND)

        period = (
            LoanPeriod.objects
            .filter(loan_application=loan_application)
            .order_by('-created_at')
            .first()
        )
        if not period:
            return Response({'detail': 'Loan period not found for this loan.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'loan_ref_no': loan_ref_no,
            'remaining_balance': period.remaining_balance,
            'remaining_principal': period.remaining_principal,
            'remaining_interest': period.remaining_interest,
        }, status=status.HTTP_200_OK)

class OverdueEmiCollectView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'emi/overdue-emis.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['api_url'] = reverse('agent:api_overdue_emis')
        agent_id = self.request.session.get('agent_id')
        today = timezone.now().date()

        qs = (
            EmiAgentAssign.objects
            .select_related(
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'emi__loan_application__customer__branch',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'reschedule_emi__loan_application__customer__branch',
            )
            .filter(
                agent_id=agent_id,
                is_active=True,
            )
            .filter(
                Q(emi__isnull=False, emi__paid=False, emi__installment_date__lt=today)
                |
                Q(reschedule_emi__isnull=False, reschedule_emi__paid=False, reschedule_emi__installment_date__lt=today)
            )
            .order_by('installment_date')
        )

        rows_all = []
        for assignment in qs:
            emi_obj = getattr(assignment, 'emi', None) or getattr(assignment, 'reschedule_emi', None)
            if not emi_obj:
                continue

            loan_app = getattr(emi_obj, 'loan_application', None)
            if not loan_app:
                continue

            customer = getattr(loan_app, 'customer', None)
            branch = getattr(customer, 'branch', None) or getattr(loan_app, 'branch', None)
            is_reschedule = bool(getattr(assignment, 'reschedule_emi_id', None))

            due_date = getattr(emi_obj, 'installment_date', None)
            due_date_str = due_date.strftime('%d-%m-%Y') if due_date else ''
            days_overdue = (today - due_date).days if due_date else 0

            rows_all.append({
                'loan_id': getattr(loan_app, 'loan_ref_no', None),
                'branch': getattr(branch, 'branch_name', None) if branch else None,
                'customer_name': (getattr(customer, 'full_name', '') or 'N/A') if customer else 'N/A',
                'assignment_id': assignment.assignment_id,
                'emi_id': getattr(emi_obj, 'id', None),
                'is_reschedule': 1 if is_reschedule else 0,
                'due_date': due_date_str,
                'installment_amount': assignment.installment_amount,
                'principal_amount': assignment.principal_amount,
                'interest_amount': assignment.interest_amount,
                'assigned_date': assignment.assigned_at.strftime('%d-%m-%Y : %H:%M') if assignment.assigned_at else None,
                'is_active': assignment.is_active,
                'days_overdue': days_overdue,
            })

        paginator = Paginator(rows_all, 15)
        page_number = self.request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            page_obj = paginator.page(1)

        context['rows'] = list(page_obj.object_list)
        context['page_obj'] = page_obj
        context['has_next'] = page_obj.has_next()
        context['next_page_number'] = page_obj.next_page_number() if page_obj.has_next() else None
        return context


class OverdueEmiListPagePartialView(AgentSessionRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        today = timezone.now().date()

        qs = (
            EmiAgentAssign.objects
            .select_related(
                'emi',
                'emi__loan_application',
                'emi__loan_application__customer',
                'emi__loan_application__customer__branch',
                'reschedule_emi',
                'reschedule_emi__loan_application',
                'reschedule_emi__loan_application__customer',
                'reschedule_emi__loan_application__customer__branch',
            )
            .filter(
                agent_id=agent_id,
                is_active=True,
            )
            .filter(
                Q(emi__isnull=False, emi__paid=False, emi__installment_date__lt=today)
                |
                Q(reschedule_emi__isnull=False, reschedule_emi__paid=False, reschedule_emi__installment_date__lt=today)
            )
            .order_by('installment_date')
        )

        rows_all = []
        for assignment in qs:
            emi_obj = getattr(assignment, 'emi', None) or getattr(assignment, 'reschedule_emi', None)
            if not emi_obj:
                continue

            loan_app = getattr(emi_obj, 'loan_application', None)
            if not loan_app:
                continue

            customer = getattr(loan_app, 'customer', None)
            branch = getattr(customer, 'branch', None) or getattr(loan_app, 'branch', None)
            is_reschedule = bool(getattr(assignment, 'reschedule_emi_id', None))

            due_date = getattr(emi_obj, 'installment_date', None)
            due_date_str = due_date.strftime('%d-%m-%Y') if due_date else ''
            days_overdue = (today - due_date).days if due_date else 0

            rows_all.append({
                'loan_id': getattr(loan_app, 'loan_ref_no', None),
                'branch': getattr(branch, 'branch_name', None) if branch else None,
                'customer_name': (getattr(customer, 'full_name', '') or 'N/A') if customer else 'N/A',
                'assignment_id': assignment.assignment_id,
                'emi_id': getattr(emi_obj, 'id', None),
                'is_reschedule': 1 if is_reschedule else 0,
                'due_date': due_date_str,
                'installment_amount': assignment.installment_amount,
                'principal_amount': assignment.principal_amount,
                'interest_amount': assignment.interest_amount,
                'assigned_date': assignment.assigned_at.strftime('%d-%m-%Y : %H:%M') if assignment.assigned_at else None,
                'is_active': assignment.is_active,
                'days_overdue': days_overdue,
            })

        paginator = Paginator(rows_all, 15)
        page_number = request.GET.get('page', 1)
        try:
            page_obj = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            return HttpResponse('')

        html = render_to_string(
            'emi/partials/overdue-emi-rows.html',
            {'rows': list(page_obj.object_list), 'page_obj': page_obj},
            request=request,
        )
        return HttpResponse(html)


# EMI Collect view #

class NextEmiForLoanAPIView(APIView):
    def get(self, request, loan_ref_no):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_403_FORBIDDEN)

        # All assignments for this loan and agent ordered by schedule
        qs = (
            EmiAgentAssign.objects
            .select_related(
                'agent', 'emi', 'emi__loan_application', 'emi__loan_application__customer', 'assigned_by', 'assigned_by__branch'
            )
            .filter(agent__agent_id=agent_id, emi__loan_application__loan_ref_no=loan_ref_no)
            .order_by('installment_date', 'emi__id')
        )
        if not qs.exists():
            return Response({'detail': 'No EMIs found for this loan'}, status=status.HTTP_404_NOT_FOUND)

        emi_ids = list(qs.values_list('emi__id', flat=True))
        collected_emis = set(
            EmiCollectionDetail.objects
            .filter(emi_id__in=emi_ids)
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('emi_id', flat=True)
        )

        for assign in qs:
            if assign.emi_id not in collected_emis:
                serializer = EMICollectSerializer(assign)
                return Response(serializer.data)

        return Response({'detail': 'No pending EMI for this loan'}, status=status.HTTP_404_NOT_FOUND)


class LoanDueEmisAPIView(APIView):
    def get(self, request, loan_ref_no):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_403_FORBIDDEN)

        qs = (
            EmiAgentAssign.objects
            .select_related(
                'agent',
                'emi',
                'emi__loan_application',
                'reschedule_emi',
                'reschedule_emi__loan_application',
            )
            .filter(agent__agent_id=agent_id)
            .filter(
                Q(emi__loan_application__loan_ref_no=loan_ref_no)
                |
                Q(reschedule_emi__loan_application__loan_ref_no=loan_ref_no)
            )
            .order_by('installment_date', 'emi__id', 'reschedule_emi__id')
        )

        emi_ids = list(qs.values_list('emi__id', flat=True))
        res_emi_ids = list(qs.values_list('reschedule_emi__id', flat=True))

        collected_original = set(
            EmiCollectionDetail.objects
            .filter(emi_id__in=[eid for eid in emi_ids if eid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('emi_id', flat=True)
        )
        collected_rescheduled = set(
            EmiCollectionDetail.objects
            .filter(reschedule_emi_id__in=[rid for rid in res_emi_ids if rid is not None])
            .filter(Q(collected=True) | Q(status__in=['collected', 'verified']))
            .values_list('reschedule_emi_id', flat=True)
        )

        results = []
        due_amount = Decimal('0.00')

        for assign in qs:
            if assign.emi_id and assign.emi_id in collected_original:
                continue
            if getattr(assign, 'reschedule_emi_id', None) and assign.reschedule_emi_id in collected_rescheduled:
                continue

            try:
                inst_amt = Decimal(str(assign.installment_amount or 0))
            except Exception:
                inst_amt = Decimal('0.00')

            due_amount += inst_amt

            results.append({
                'loan_ref_no': loan_ref_no,
                'assignment_id': assign.assignment_id,
                'installment_date': assign.installment_date.strftime('%Y-%m-%d') if assign.installment_date else None,
                'installment_amount': float(inst_amt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),
            })

        due_amount = due_amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return Response(
            {
                'loan_ref_no': loan_ref_no,
                'due_count': len(results),
                'due_amount': float(due_amount),
                'results': results,
            },
            status=status.HTTP_200_OK,
        )


class EmiCollectedAPIView(APIView):
    def post(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        branch_manager_id = request.session.get('logged_user_id')

        data = request.data
        assignment_id = data.get('assignment_id')
        emi_id = data.get('emi_id')
        loan_ref_no = data.get('loan_ref_no')

        assignment = None
        schedule = None

        # Decide who is collecting based on payload, not session priority
        # - Agent collection when assignment_id is provided
        # - Branch collection when emi_id + loan_ref_no are provided
        mode = None
        if assignment_id:
            mode = 'agent'
        elif emi_id and loan_ref_no:
            mode = 'branch'
        else:
            return Response({'success': False, 'message': 'Provide assignment_id for agent collection OR emi_id and loan_ref_no for branch collection.'}, status=status.HTTP_400_BAD_REQUEST)

        collected_by_agent = None
        collected_by_branch = None

        # Validate and load collector per mode
        if mode == 'agent':
            if not agent_id:
                return Response({'success': False, 'message': 'Agent authentication required for agent collection.'}, status=status.HTTP_403_FORBIDDEN)
            try:
                collected_by_agent = Agent.objects.get(agent_id=agent_id)
            except Agent.DoesNotExist:
                return Response({'success': False, 'message': 'Agent not found in session'}, status=status.HTTP_403_FORBIDDEN)
        else:  # mode == 'branch'
            if not branch_manager_id:
                return Response({'success': False, 'message': 'Branch manager authentication required for branch collection.'}, status=status.HTTP_403_FORBIDDEN)
            try:
                collected_by_branch = BranchEmployee.objects.select_related('branch').get(id=branch_manager_id)
            except BranchEmployee.DoesNotExist:
                return Response({'success': False, 'message': 'Branch manager not found in session'}, status=status.HTTP_403_FORBIDDEN)

        # Resolve assignment/schedule depending on mode
        try:
            if mode == 'agent':
                assignment = (
                    EmiAgentAssign.objects
                    .select_related(
                        'emi',
                        'emi__loan_application',
                        'emi__loan_application__branch',
                        'reschedule_emi',
                        'reschedule_emi__loan_application',
                        'reschedule_emi__loan_application__branch',
                        'agent'
                    )
                    .get(assignment_id=assignment_id)
                )
                # Ensure the assignment belongs to this agent
                if assignment.agent and assignment.agent.agent_id != collected_by_agent.agent_id:
                    return Response({'success': False, 'message': 'Assignment does not belong to the logged-in agent'}, status=status.HTTP_403_FORBIDDEN)
                # Support both original and rescheduled EMIs on the assignment
                schedule = assignment.emi or getattr(assignment, 'reschedule_emi', None)
                if schedule is None:
                    return Response({'success': False, 'message': 'Assignment is not linked to any EMI schedule.'}, status=status.HTTP_400_BAD_REQUEST)
            else:  # mode == 'branch'
                schedule = (
                    LoanEMISchedule.objects
                    .select_related('loan_application')
                    .get(id=emi_id, loan_application__loan_ref_no=loan_ref_no)
                )
                # Try to find an active assignment for this EMI (optional for branch collections)
                assignment = (
                    EmiAgentAssign.objects
                    .select_related('agent')
                    .filter(emi=schedule, is_active=True)
                    .first()
                )
                if assignment is None:
                    # Fallback to latest assignment if exists (still optional)
                    assignment = (
                        EmiAgentAssign.objects
                        .select_related('agent')
                        .filter(emi=schedule)
                        .order_by('-assigned_at')
                        .first()
                )
        except EmiAgentAssign.DoesNotExist:
            return Response({'success': False, 'message': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
        except LoanEMISchedule.DoesNotExist:
            return Response({'success': False, 'message': 'EMI schedule not found'}, status=status.HTTP_404_NOT_FOUND)

        # Enforce sequential collection for agents: previous EMI must be verified
        # NOTE: This sequential rule currently applies only to original LoanEMISchedule EMIs.
        if mode == 'agent' and schedule is not None and isinstance(schedule, LoanEMISchedule):
            loan_app = getattr(schedule, 'loan_application', None)
            if loan_app is not None:
                prev_emi = (
                    LoanEMISchedule.objects
                    .filter(loan_application=loan_app)
                    .filter(
                        Q(installment_date__lt=schedule.installment_date) |
                        Q(installment_date=schedule.installment_date, id__lt=schedule.id)
                    )
                    .order_by('-installment_date', '-id')
                    .first()
                )

                if prev_emi is not None:
                    last_prev_collection = (
                        EmiCollectionDetail.objects
                        .filter(emi=prev_emi)
                        .order_by('-collected_at')
                        .first()
                    )

                    # Previous EMI must have at least one collection and be verified
                    if not last_prev_collection or last_prev_collection.status != 'verified':
                        return Response(
                            {
                                'success': False,
                                'message': 'Cannot collect this EMI until the previous EMI collection is verified by branch.',
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

        # Amounts and payment (default to schedule/assignment values if not provided)
        def d2(val, default):
            # Coerce to Decimal with 2dp rounding; accept strings/numbers, fall back to default
            if val in (None, '', 'null'):
                val = default
            try:
                d = Decimal(str(val))
            except Exception:
                d = Decimal(str(default or 0))
            return d.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

        default_amount = getattr(assignment, 'installment_amount', getattr(schedule, 'installment_amount', 0))
        default_principal = getattr(assignment, 'principal_amount', getattr(schedule, 'principal_amount', 0))
        default_interest = getattr(assignment, 'interest_amount', getattr(schedule, 'interest_amount', 0))

        amount_received = d2(data.get('amount_received'), default_amount)
        principal_received = d2(data.get('principal_received'), default_principal)
        interest_received = d2(data.get('interest_received'), default_interest)
        penalty_received = d2(data.get('penalty_received'), 0)
        payment_mode = data.get('payment_mode') or 'Cash'
        payment_reference = data.get('payment_reference')
        remarks = data.get('remarks')
        # Optional override: allow client to specify collected flag (default True)
        def to_bool(val, default=True):
            if val in (None, '', 'null'):
                return default
            s = str(val).strip().lower()
            return s in ('1', 'true', 'yes', 'y', 't')
        requested_collected = to_bool(data.get('collected'), default=True)

        try:
            with transaction.atomic():
                # Decide whether this collection is for an original EMI or a rescheduled EMI
                emi_obj = schedule if isinstance(schedule, LoanEMISchedule) else None
                res_emi_obj = None if emi_obj is not None else schedule

                collected = EmiCollectionDetail(
                    assignment=assignment,  # may be None for branch collections
                    emi=emi_obj,
                    reschedule_emi=res_emi_obj,
                    loan_application=schedule.loan_application,
                    amount_received=amount_received,
                    principal_received=principal_received,
                    interest_received=interest_received,
                    penalty_received=penalty_received,
                    payment_mode=payment_mode,
                    payment_reference=payment_reference,
                    remarks=remarks,
                    status='collected',
                    collected=requested_collected,
                )
                if collected_by_agent:
                    collected.collected_by_agent = collected_by_agent
                if collected_by_branch:
                    collected.collected_by_branch = collected_by_branch
                collected.save()
                # Ensure only this record is marked collected=True for this EMI (original or rescheduled),
                # but only when requested_collected is True
                if requested_collected:
                    if emi_obj is not None:
                        EmiCollectionDetail.objects.filter(emi=emi_obj).exclude(collected_id=collected.collected_id).update(collected=False)
                    elif res_emi_obj is not None:
                        EmiCollectionDetail.objects.filter(reschedule_emi=res_emi_obj).exclude(collected_id=collected.collected_id).update(collected=False)
        except Exception as e:
            return Response({'success': False, 'message': f'Failed to save collection: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'collected_id': collected.collected_id,
            'emi_id': schedule.id,
            'assignment_id': getattr(assignment, 'assignment_id', None),
            'status': collected.status,
        }, status=status.HTTP_201_CREATED)

class AgentEmiRejectAPIView(APIView):
    """Agent-only EMI reject API used at /agent/api/emi-reject/.

    Logic is the same as the existing commented-out block, with a
    small tweak so it accepts either `reason` or `remarks` from the
    frontend.
    """

    def post(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        # Accept either 'reason' or 'remarks' (current JS sends remarks)
        raw_reason = request.data.get('reason') or request.data.get('remarks') or ''
        reason = str(raw_reason).strip()
        if not reason:
            return Response({'detail': 'Reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        assignment_id = request.data.get('assignment_id')
        emi_id = request.data.get('emi_id')

        if not assignment_id and not emi_id:
            return Response({'detail': 'Provide assignment_id or emi_id to reject.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            agent = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'detail': 'Agent not found.'}, status=status.HTTP_403_FORBIDDEN)

        assignment = None
        if assignment_id:
            try:
                assignment = (
                    EmiAgentAssign.objects
                    .select_related('emi', 'emi__loan_application')
                    .get(assignment_id=assignment_id, agent=agent)
                )
            except EmiAgentAssign.DoesNotExist:
                return Response({'detail': 'Assignment not found for this agent.'}, status=status.HTTP_404_NOT_FOUND)
            emi = assignment.emi
        else:
            try:
                emi = (
                    LoanEMISchedule.objects
                    .select_related('loan_application')
                    .get(id=emi_id)
                )
            except LoanEMISchedule.DoesNotExist:
                return Response({'detail': 'EMI schedule not found.'}, status=status.HTTP_404_NOT_FOUND)
            assignment = (
                EmiAgentAssign.objects
                .select_related('emi', 'emi__loan_application')
                .filter(emi=emi, agent=agent)
                .order_by('-assigned_at')
                .first()
            )

        existing = (
            EmiCollectionDetail.objects
            .filter(
                emi=emi,
                status='rejected',
                collected_by_agent=agent,
            )
            .order_by('-collected_at')
            .first()
        )

        now = timezone.now()

        if existing and existing.collected is False:
            existing.remarks = reason
            existing.agent_reject_reason = reason
            existing.agent_rejected_at = now
            existing.rejected_by_agent = agent
            existing.save(update_fields=['remarks', 'agent_reject_reason', 'agent_rejected_at', 'rejected_by_agent'])
            collection = existing
        else:
            collection = EmiCollectionDetail.objects.create(
                assignment=assignment,
                emi=emi,
                loan_application=emi.loan_application,
                collected_by_agent=agent,
                amount_received=Decimal('0.00'),
                principal_received=Decimal('0.00'),
                interest_received=Decimal('0.00'),
                payment_mode='Cash',
                payment_reference=None,
                status='rejected',
                collected=False,
                remarks=reason,
                agent_reject_reason=reason,
                agent_rejected_at=now,
                rejected_by_agent=agent,
            )

        return Response({
            'success': True,
            'message': 'EMI collection rejected.',
            'emi_id': emi.id,
            'assignment_id': getattr(assignment, 'assignment_id', None),
            'collected_id': collection.collected_id,
            'status': collection.status,
            'agent_reject_reason': collection.agent_reject_reason,
        })

class EmiCollectionRejectAPI(APIView):
    def post(self, request, emi_id, *args, **kwargs):
        # Basic auth check (adjust as needed for your auth flow)
        branch_manager_id = request.session.get('logged_user_id')
        if not branch_manager_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        reason = str(request.data.get('reason', '')).strip()
        if not reason:
            return Response({'detail': 'Reason is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate EMI exists
        try:
            emi = LoanEMISchedule.objects.get(id=emi_id)
        except LoanEMISchedule.DoesNotExist:
            return Response({'detail': 'EMI not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Find the most recent collection record for this EMI that can be rejected
        collection = (
            EmiCollectionDetail.objects
            .filter(emi=emi)
            .order_by('-collected_at')
            .first()
        )
        if not collection:
            return Response({'detail': 'No collection record found for this EMI.'}, status=status.HTTP_404_NOT_FOUND)

        # Update status and remarks
        collection.status = 'rejected'
        collection.remarks = reason
        collection.collected = False
        collection.save(update_fields=['status', 'remarks', 'collected'])

        return Response({
            'success': True,
            'message': f'EMI {emi_id} collection marked as rejected.',
            'emi_id': emi_id,
            'status': collection.status,
            'remarks': collection.remarks,
            'collected_id': collection.collected_id,
        }, status=status.HTTP_200_OK)
        
class EmiReCollectAPI(APIView):
    def post(self, request, emi_id, *args, **kwargs):
        # Accept either agent session (field) or branch manager session (branch portal)
        branch_manager_id = request.session.get('logged_user_id')
        agent_id = request.session.get('agent_id')
        agent = None

        if not branch_manager_id and not agent_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        if agent_id:
            try:
                agent = Agent.objects.get(agent_id=agent_id)
            except Agent.DoesNotExist:
                return Response({'detail': 'Agent not found.'}, status=status.HTTP_403_FORBIDDEN)
        else:
            # Branch manager flow: ensure manager exists
            try:
                BranchEmployee.objects.get(id=branch_manager_id)
            except BranchEmployee.DoesNotExist:
                return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_403_FORBIDDEN)

        # Validate EMI exists
        try:
            emi = LoanEMISchedule.objects.get(id=emi_id)
        except LoanEMISchedule.DoesNotExist:
            return Response({'detail': 'EMI not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Find the latest rejected collection for this EMI 
        collection = (
            EmiCollectionDetail.objects
            .filter(emi=emi, status='rejected')
            .order_by('-collected_at')
            .first()
        )
        if not collection:
            return Response({'detail': 'No rejected collection found to re-collect for this EMI.'}, status=status.HTTP_404_NOT_FOUND)

        # Optionally update remarks if provided
        remarks = str(request.data.get('remarks', '')).strip()
        if remarks:
            collection.remarks = remarks

        # Persist amounts and payment_mode if provided
        update_fields = ['status', 'remarks']
        amt = request.data.get('amount_received')
        prin = request.data.get('principal_received')
        intr = request.data.get('interest_received')
        pay_mode = request.data.get('payment_mode')

        # Safe decimal parsing to 2 dp
        def parse_money(val):
            if val is None or val == '':
                return None
            try:
                d = Decimal(str(val))
                return d.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
            except (InvalidOperation, ValueError, TypeError):
                return None

        amt_d = parse_money(amt)
        prin_d = parse_money(prin)
        intr_d = parse_money(intr)

        if amt_d is not None:
            collection.amount_received = amt_d
            update_fields.append('amount_received')
        if prin_d is not None:
            collection.principal_received = prin_d
            update_fields.append('principal_received')
        if intr_d is not None:
            collection.interest_received = intr_d
            update_fields.append('interest_received')

        # Validate and set payment mode
        valid_modes = {choice[0] for choice in EmiCollectionDetail.PAYMENT_MODES}
        if isinstance(pay_mode, str) and pay_mode in valid_modes:
            collection.payment_mode = pay_mode
            update_fields.append('payment_mode')

        # Mark who re-collected this
        if branch_manager_id:
            # Assign FK to BranchManager instance and clear agent to satisfy XOR
            try:
                manager = BranchEmployee.objects.get(id=branch_manager_id)
            except BranchEmployee.DoesNotExist:
                return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_403_FORBIDDEN)
            collection.collected_by_branch = manager
            collection.collected_by_agent = None
            update_fields.extend(['collected_by_branch', 'collected_by_agent'])
        elif agent_id and agent:
            # Assign FK to Agent instance and clear branch to satisfy XOR
            collection.collected_by_agent = agent
            collection.collected_by_branch = None
            update_fields.extend(['collected_by_agent', 'collected_by_branch'])

        collection.status = 'collected'
        collection.collected = True
        update_fields.append('collected')
        collection.save(update_fields=list(set(update_fields)))
        # Ensure only this record is marked collected=True for this EMI
        EmiCollectionDetail.objects.filter(emi=emi).exclude(collected_id=collection.collected_id).update(collected=False)

        return Response({
            'success': True,
            'message': f'EMI {emi_id} re-collected successfully.',
            'emi_id': emi_id,
            'status': collection.status,
            'collected_id': collection.collected_id,
            'amount_received': str(collection.amount_received),
            'principal_received': str(collection.principal_received),
            'interest_received': str(collection.interest_received),
            'payment_mode': collection.payment_mode,
        }, status=status.HTTP_200_OK)


# file: loan/views.py
class EmiLateFeeAPIView(APIView):
    def get(self, request, emi_id):
        try:
            emi = LoanEMISchedule.objects.select_related('loan_application').get(id=emi_id)
        except LoanEMISchedule.DoesNotExist:
            return Response({'detail': 'EMI not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            data = {
                'emi_id': emi.id,
                'loan_ref_no': getattr(emi.loan_application, 'loan_ref_no', None),
                'late_fee': float(getattr(emi, 'late_fee', 0) or 0),
                'is_overdue': bool(getattr(emi, 'is_overdue', False)),
                'overdue_days': int(getattr(emi, 'overdue_days', 0) or 0),
                # Model uses 'paid' boolean; expose 'is_paid' for convenience
                'is_paid': bool(getattr(emi, 'paid', False)),
                'installment_amount': float(getattr(emi, 'installment_amount', 0) or 0),
            }
            # Only include status if it actually exists on your model
            if hasattr(emi, 'status'):
                data['status'] = getattr(emi, 'status', None)

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmiRescheduleLateFeeAPIView(APIView):
    """Return late fee / overdue info for a rescheduled EMI.

    Mirrors EmiLateFeeAPIView but uses LoanEMIReschedule instead of LoanEMISchedule.
    """

    def get(self, request, res_emi_id):
        try:
            emi = LoanEMIReschedule.objects.select_related('loan_application').get(id=res_emi_id)
        except LoanEMIReschedule.DoesNotExist:
            return Response({'detail': 'Rescheduled EMI not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            # Some deployments may not have an explicit "is_overdue" boolean
            # field on LoanEMIReschedule. In that case, infer overdue status
            # from overdue_days / late_fee so the frontend can show the
            # penalty section correctly.
            raw_overdue_days = getattr(emi, 'overdue_days', 0) or 0
            overdue_days = int(raw_overdue_days)

            raw_late_fee = getattr(emi, 'late_fee', 0) or 0
            late_fee = float(raw_late_fee)

            if hasattr(emi, 'is_overdue'):
                is_overdue = bool(getattr(emi, 'is_overdue', False))
            else:
                # Fallback: treat as overdue when we have any overdue days
                # or a positive late fee.
                is_overdue = bool(overdue_days > 0 or late_fee > 0)

            data = {
                'reschedule_emi_id': emi.id,
                'loan_ref_no': getattr(emi.loan_application, 'loan_ref_no', None),
                'late_fee': late_fee,
                'is_overdue': is_overdue,
                'overdue_days': overdue_days,
                'installment_amount': float(getattr(emi, 'installment_amount', 0) or 0),
            }
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetEmiCollectionDetailAPI(APIView):
    def get(self, request):
        agent_id = request.session.get('agent_id')
        employee_id = request.session.get('logged_user_id')

        # Branch manager: return collections for all EMIs under this branch (both agent and branch collections)
        if employee_id:
            try:
                employee = BranchEmployee.objects.select_related('branch').get(id=employee_id)
            except BranchEmployee.DoesNotExist:
                return Response({'detail': 'Branch employee not found.'}, status=status.HTTP_403_FORBIDDEN)

            collected_rows = list(
                EmiCollectionDetail.objects
                .filter(
                    loan_application__branch=employee.branch,
                    status__in=['collected', 'verified', 'rejected']
                )
                .values(
                    'assignment__assignment_id',
                    'emi__id',
                    'status',
                    'remarks',
                    'amount_received',
                    'principal_received',
                    'interest_received',
                    'collected_by_agent',
                    'collected_by_branch',
                    'emi__installment_amount',
                    'emi__principal_amount',
                    'emi__interest_amount',
                )
                .distinct()
            )

            # Check permissions
            permissions = {
                'can_view_emis': employee.is_manager or employee.has_perm('view_emis'),
                'can_collect_emi': employee.is_manager or employee.has_perm('collect_emi'),
                'can_receive_emi': employee.is_manager or employee.has_perm('receive_emi'),
                'can_reject_emi': employee.is_manager or employee.has_perm('reject_emi')
            }

        # Agent: return collections for active assignments for this agent
        elif agent_id:
            assignment_ids = list(
                EmiAgentAssign.objects.filter(agent__agent_id=agent_id, is_active=True)
                .values_list('assignment_id', flat=True)
            )

            if not assignment_ids:
                return Response([])

            collected_rows = list(
                EmiCollectionDetail.objects
                # .filter(assignment__assignment_id__in=assignment_ids, status__in=['collected','verified','rejected'])
                .filter(
                Q(assignment__assignment_id__in=assignment_ids) |
                Q(emi__agent_assignments__agent__agent_id=agent_id, emi__agent_assignments__is_active=True),
                status__in=['collected','verified','rejected']
            )
                .values(
                    'assignment__assignment_id',
                    'emi__id',
                    'status',
                    'remarks',
                    'amount_received',
                    'principal_received',
                    'interest_received',
                    'collected_by_agent',
                    'collected_by_branch',
                    'emi__installment_amount',
                    'emi__principal_amount',
                    'emi__interest_amount',
                )
                .distinct()
            )
            permissions = {}
        else:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        response_data = {
            'collections': [
                {
                    'assignment_id': row['assignment__assignment_id'],
                    'emi_id': row['emi__id'],
                    'status': row['status'],
                    'remarks': row['remarks'],
                    'amount_received': row['amount_received'],
                    'principal_received': row['principal_received'],
                    'interest_received': row['interest_received'],
                    'collected_by_agent': row['collected_by_agent'],
                    'collected_by_branch': row['collected_by_branch'],
                    'installment_amount': row.get('emi__installment_amount'),
                    'principal_amount': row.get('emi__principal_amount'),
                    'interest_amount': row.get('emi__interest_amount'),
                }
                for row in collected_rows
            ],
            'permissions': permissions
        }

        return Response(response_data)

class GetEmiCollectionDetailByEmiAPI(APIView):
    def get(self, request, emi_id: int):
        branch_manager_id = request.session.get('logged_user_id')
        agent_id = request.session.get('agent_id')
        if not branch_manager_id and not agent_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            # Latest collection for this EMI
            collection = (
                EmiCollectionDetail.objects
                .select_related(
                    'emi',
                    'emi__loan_application',
                    'emi__loan_application__customer',
                    'assignment',
                    'assignment__agent',
                    'collected_by_agent',
                    'collected_by_branch',
                    'collected_by_branch__branch',
                )
                .filter(emi__id=emi_id)
                .order_by('-collected_at')
                .first()
            )
            if not collection:
                return Response({'detail': 'No collection record found for this EMI.'}, status=status.HTTP_404_NOT_FOUND)

            # print(collection.emi.late_fee)

            loan = collection.emi.loan_application if collection.emi else None
            customer = loan.customer if loan and hasattr(loan, 'customer') else None
            agent = collection.collected_by_agent
            manager = collection.collected_by_branch

            # Build collector details based on which FK is set
            collector_type = 'agent' if agent else 'branch'
            collector_id = None
            collector_name = None
            collector_phone= None
            collector_email= None
            collector_branch = None
            if agent:
                collector_id = getattr(agent, 'agent_id', None)
                collector_name = getattr(agent, 'full_name', None)
                collector_phone= getattr(agent, 'phone', None)
                collector_email= getattr(agent, 'email', None)
            elif manager:
                collector_id = getattr(manager, 'manager_id', None)
                full = f"{getattr(manager, 'first_name', '')} {getattr(manager, 'last_name', '')}".strip()
                collector_name = full or getattr(manager, 'email', None)
                collector_phone= getattr(manager, 'phone_number', None)
                collector_email= getattr(manager, 'email', None)
                collector_branch = getattr(getattr(manager, 'branch', None), 'branch_name', None)


            data = {
                'collected_id': collection.collected_id,
                'emi_id': collection.emi.id if collection.emi else None,
                'loan_ref_no': loan.loan_ref_no if loan else None,
                'customer_name': getattr(customer, 'full_name', None),
                'status': collection.status,
                'remarks': collection.remarks,
                'amount_received': str(collection.amount_received) if hasattr(collection, 'amount_received') else None,
                'principal_received': str(collection.principal_received) if hasattr(collection, 'principal_received') else None,
                'interest_received': str(collection.interest_received) if hasattr(collection, 'interest_received') else None,
                'late_fee': collection.penalty_received,
                'payment_mode': collection.payment_mode,
                'payment_reference': getattr(collection.emi, 'payment_reference', None) if collection.emi else None,
                'collected_at': getattr(collection, 'collected_at', None),
                'verified_at': getattr(collection, 'verified_at', None),
                'collector': {
                    'type': collector_type,
                    'id': collector_id,
                    'name': collector_name,
                    'phone': collector_phone,
                    'email': collector_email,
                    'branch_name': collector_branch,
                }
            }
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class EmiCollectedOnlyDataAPI(APIView):
    def get(self, request, loan_ref_no: str):
        try:
            rows = (
                EmiCollectionDetail.objects
                .filter(
                    loan_application__loan_ref_no=loan_ref_no,
                    collected=True,
                    reschedule_emi__isnull=True
                )
                .order_by('-collected_at')
                .values(
                    'collected_id',
                    'emi_id',
                    'loan_application__loan_ref_no',
                    'amount_received',
                    'principal_received',
                    'interest_received',
                    'payment_mode',
                    'payment_reference',
                    'collected_at',
                    'verified_at',
                    'status',
                    'remarks',
                )
            )

            data = [
                {
                    'collected_id': r['collected_id'],
                    'emi_id': r['emi_id'],
                    'loan_ref_no': r['loan_application__loan_ref_no'],
                    'amount_received': str(r['amount_received']) if r['amount_received'] is not None else None,
                    'principal_received': str(r['principal_received']) if r['principal_received'] is not None else None,
                    'interest_received': str(r['interest_received']) if r['interest_received'] is not None else None,
                    'payment_mode': r['payment_mode'],
                    'payment_reference': r['payment_reference'],
                    'collected_at': r['collected_at'],
                    'verified_at': r['verified_at'],
                    'status': r['status'],
                    'remarks': r['remarks'],
                }
                for r in rows
            ]

            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class LoanNocPDF(View):
    """Download the Loan Close NOC PDF for an approved LoanCloseRequest (class-based)."""

    def get(self, request, request_id):
        lcr = get_object_or_404(LoanCloseRequest, request_id=request_id)
        if lcr.status != 'approved':
            return HttpResponseForbidden('NOC is available only for approved requests.')
        
        # Resolve logo and embed as base64 so Playwright can render it inside PDF
        from django.contrib.staticfiles import finders
        import base64
        import os
        logo_base64 = None
        try:
            candidate_paths = [
                'main/images/company-logo.png',
                'images/company-logo.png',
                'main/images/logo.png',
                'images/logo.png',
                'logo.png',
            ]
            logo_path = None
            for rel in candidate_paths:
                found = finders.find(rel)
                if found:
                    logo_path = found
                    break
            if logo_path and os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_base64 = 'data:image/png;base64,' + base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            print(f"[LoanNocPDF] Logo embedding failed: {e}")

        # Fetch the particular customer's address (OneToOne via customer), not just by loan_application
        address_obj = CustomerAddress.objects.filter(
            customer=lcr.loan_application.customer
        ).first()

        address_text = ''
        pin_code = ''
        po = ''
        ps = ''

        if address_obj:
            parts = [
                getattr(address_obj, 'address_line_1', '') or '',
                getattr(address_obj, 'address_line_2', '') or '',
                getattr(address_obj, 'landmark', '') or '',
                getattr(address_obj, 'city_or_town', '') or '',
                getattr(address_obj, 'district', '') or '',
                getattr(address_obj, 'state', '') or '',
                getattr(address_obj, 'country', '') or 'India',
            ]
            # Build readable address
            address_text = ', '.join([p for p in parts if p])

            # Map fields to template variables
            pin_code = getattr(address_obj, 'post_code', '') or ''
            po = getattr(address_obj, 'post_office', '') or ''
            # No dedicated police station field; best available substitute is city/town
            ps = getattr(address_obj, 'city_or_town', '') or ''
            district = getattr(address_obj, 'district', '') or ''
            state = getattr(address_obj, 'state', '') or ''
            country = getattr(address_obj, 'country', '') or ''

        # Loan details
        loan_detail = CustomerLoanDetail.objects.filter(
            loan_application=lcr.loan_application
        ).first()
        loan_amount = getattr(loan_detail, 'loan_amount', None) if loan_detail else None

        # Choose a sensible loan date; format to dd-mm-YYYY for the template
        loan_date_dt = (
            getattr(lcr.loan_application, 'disbursed_at', None)
            or getattr(lcr.loan_application, 'approved_at', None)
            or getattr(lcr.loan_application, 'submitted_at', None)
        )
        loan_date = loan_date_dt.strftime('%d-%m-%Y') if loan_date_dt else None

        context = {
            'customer_name': getattr(getattr(lcr.loan_application, 'customer', None), 'full_name', ''),
            'loan_ref_no': lcr.loan_application.loan_ref_no,
            'request_id': lcr.request_id,
            'approved_at': lcr.approved_at,
            # 'branch_name': getattr(lcr.branch, 'branch_name', ''),
            'branch_name': getattr(lcr.loan_application.branch, 'branch_name', ''),
            'logo_base64': logo_base64,
            'address': address_text,
            'pin': pin_code,
            'po': po,
            'ps': ps,
            'district': district,
            'state': state,
            'country': country,
            'loan_amount': loan_amount,
            'loan_date': loan_date,
        }

        html = render_to_string('loan-close-pdf/loan-close-pdf.html', context)

        if async_playwright is None:
            return HttpResponse('PDF generation not available (Playwright not installed).', status=500)

        async def _render_pdf(html_content):
            async with async_playwright() as p:
                browser = await p.chromium.launch()
                page = await browser.new_page()
                await page.set_content(html_content, wait_until="networkidle")
                pdf = await page.pdf(format="A4", print_background=True)
                await browser.close()
                return pdf

        pdf_bytes = asyncio.run(_render_pdf(html))
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"Loan_Close_Certificate_{lcr.loan_application.loan_ref_no}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

@method_decorator(csrf_exempt, name='dispatch')
class SaveDraftAPI(APIView):
    """API to save loan application draft data"""

    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            user_id = data.get('user_id')
            user_type = data.get('user_type')  # 'agent' or 'branch'
            draft_data = data.get('draft_data')

            if not user_id or not user_type or not draft_data:
                return Response({
                    'success': False,
                    'message': 'user_id, user_type, and draft_data are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            if user_type not in ['agent', 'branch']:
                return Response({
                    'success': False,
                    'message': 'user_type must be either "agent" or "branch"'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if user exists and is active
            if user_type == 'agent':
                from agent.models import Agent
                try:
                    agent = Agent.objects.get(agent_id=user_id)
                    if agent.status != 'active':
                        return Response({
                            'success': False,
                            'message': 'Agent is not active'
                        }, status=status.HTTP_400_BAD_REQUEST)
                except Agent.DoesNotExist:
                    return Response({
                        'success': False,
                        'message': 'Agent not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:  # branch
                from headquater.models import Branch
                try:
                    branch = Branch.objects.get(branch_id=user_id)
                except Branch.DoesNotExist:
                    return Response({
                        'success': False,
                        'message': 'Branch not found'
                    }, status=status.HTTP_404_NOT_FOUND)

            # Always create a new draft record so that multiple drafts per
            # user are preserved. Do not update/overwrite any existing draft.
            draft = LoanApplicationDraft.objects.create(
                user_id=user_id,
                user_type=user_type,
                draft_data=draft_data,
            )
            draft_id = draft.draft_id
            token = draft.token
            action = 'created'

            return Response({
                'success': True,
                'message': f'Draft {action} successfully',
                'draft_id': draft_id
                # 'token': token
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error saving draft: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class GetDraftAPI(APIView):
    """API to retrieve loan application draft data"""

    def get(self, request, *args, **kwargs):
        try:
            user_id = request.GET.get('user_id')
            user_type = request.GET.get('user_type')
            # Normalize user_type to avoid accidental trailing slashes like 'agent/'
            if user_type:
                user_type = user_type.strip().rstrip('/')
            # token = request.GET.get('token')  # Optional token for specific draft retrieval

            if not user_id or not user_type:
                return Response({
                    'success': False,
                    'message': 'user_id and user_type are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            if user_type not in ['agent', 'branch']:
                return Response({
                    'success': False,
                    'message': 'user_type must be either "agent" or "branch"'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check if user exists and is active
            if user_type == 'agent':
                from agent.models import Agent
                try:
                    agent = Agent.objects.get(agent_id=user_id)
                    if agent.status != 'active':
                        return Response({
                            'success': False,
                            'message': 'Agent is not active'
                        }, status=status.HTTP_400_BAD_REQUEST)
                except Agent.DoesNotExist:
                    return Response({
                        'success': False,
                        'message': 'Agent not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            else:  # branch
                from headquater.models import Branch
                try:
                    branch = Branch.objects.get(branch_id=user_id)
                except Branch.DoesNotExist:
                    return Response({
                        'success': False,
                        'message': 'Branch not found'
                    }, status=status.HTTP_404_NOT_FOUND)

            # Get all drafts for this user (latest first)
            drafts_qs = (
                LoanApplicationDraft.objects
                .filter(user_id=user_id, user_type=user_type)
                .order_by('-created_at')
            )

            valid_drafts = []
            for draft in drafts_qs:
                # Optional safety: if this draft already corresponds to a
                # customer for whom an application exists (identified by the
                # same Aadhaar + PAN), skip it so it is not offered for prefill.
                try:
                    draft_data = draft.draft_data or {}
                    raw_adhar = (draft_data.get('adhar_number') or '').strip()
                    adhar_no = ''.join(ch for ch in raw_adhar if ch.isdigit())

                    raw_pan = (draft_data.get('pan_number') or '').strip()
                    pan_no = raw_pan.upper() if raw_pan else ''

                    if adhar_no and pan_no:
                        if CustomerDetail.objects.filter(
                            adhar_number=adhar_no,
                            pan_number=pan_no,
                        ).exists():
                            # Suppress drafts that correspond to a submitted application
                            continue
                except Exception:
                    # On any error in this check, include the draft so we do
                    # not silently hide potentially valid drafts.
                    pass

                # For the frontend we primarily need the raw draft_data, but
                # also expose the draft_id so specific drafts can be deleted
                # without affecting others.
                draft_data = dict(draft.draft_data or {})
                draft_data['_draft_id'] = draft.draft_id
                valid_drafts.append(draft_data)

            if valid_drafts:
                return Response({
                    'success': True,
                    'draft_data': valid_drafts,
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': True,
                    'message': 'No draft found for this user',
                    'draft_data': None,
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error retrieving draft: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class BankAccountVerificationAPI(APIView):
    """API to verify bank account details using Cashfree"""

    def post(self, request, *args, **kwargs):
        try:
            account_number = request.data.get('account_number', '').strip()
            ifsc_code = request.data.get('ifsc_code', '').strip().upper()
            name = request.data.get('name', '').strip()
            phone = request.data.get('phone', '').strip()

            if not account_number or not ifsc_code:
                return Response({
                    'success': False,
                    'message': 'Account number and IFSC code are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate account number format
            if not account_number.isdigit() or not 9 <= len(account_number) <= 18:
                return Response({
                    'success': False,
                    'message': 'Invalid account number format'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Validate IFSC code format
            import re
            if not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
                return Response({
                    'success': False,
                    'message': 'Invalid IFSC code format'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Call Cashfree verification service
            result = CashfreeService.verify_bank_account(
                account_number=account_number,
                ifsc=ifsc_code,
                phone=phone,
                name=name
            )

            if result.get('status') == 'success':
                return Response({
                    'success': True,
                    'data': result.get('data', {}),
                    'message': 'Bank account verified successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': result.get('message', 'Verification failed')
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error during verification: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@method_decorator(csrf_exempt, name='dispatch')
class DeleteDraftAPI(APIView):
    """API to delete loan application draft data"""

    def delete(self, request, *args, **kwargs):
        try:
            user_id = request.data.get('user_id')
            user_type = request.data.get('user_type')
            draft_id = request.data.get('draft_id')

            if not user_id or not user_type:
                return Response({
                    'success': False,
                    'message': 'user_id and user_type are required'
                }, status=status.HTTP_400_BAD_REQUEST)

            if user_type not in ['agent', 'branch']:
                return Response({
                    'success': False,
                    'message': 'user_type must be either "agent" or "branch"'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Delete either a specific draft (when draft_id is provided) or
            # all drafts for this user (legacy behavior).
            qs = LoanApplicationDraft.objects.filter(
                user_id=user_id,
                user_type=user_type,
            )
            if draft_id:
                qs = qs.filter(draft_id=draft_id)

            deleted_count, _ = qs.delete()

            if deleted_count > 0:
                return Response({
                    'success': True,
                    'message': 'Draft deleted successfully'
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': True,
                    'message': 'No draft found to delete'
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error deleting draft: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class LoanAutoPaySetupAPI(APIView):
    """
    API to setup auto-payment subscription for a loan.
    Fetches customer details and creates subscription.
    """
    def post(self, request, loan_ref_no):
        try:
            # Get loan details
            loan = get_object_or_404(LoanApplication, loan_ref_no=loan_ref_no)

            if not loan.customer:
                return Response({
                    'success': False,
                    'message': 'No customer details found for this loan'
                }, status=status.HTTP_400_BAD_REQUEST)

            customer = loan.customer

            # Check if auto-pay is already active
            # For now, we'll assume it's not active. In production, you'd check a subscription model

            # Get EMI amount from loan details
            loan_detail = loan.loan_details.first()
            if not loan_detail:
                return Response({
                    'success': False,
                    'message': 'No loan details found for this loan'
                }, status=status.HTTP_400_BAD_REQUEST)

            plan_amount = loan_detail.emi_amount

            # Create subscription
            response = AutoPaymentService.create_subscription(
                customer_name=customer.full_name,
                customer_email=customer.email or 'test@example.com',
                customer_phone=customer.contact,
                plan_name=f"Auto EMI for {loan_ref_no}",
                amount=plan_amount,
                return_url=request.build_absolute_uri(reverse('agent:auto_payment_success'))
            )

            if response['status'] == 'success':
                # Here you would save subscription details to database
                # For now, just return success
                return Response({
                    'success': True,
                    'message': 'Auto-payment setup initiated successfully',
                    'subscription_id': response.get('subscription_id'),
                    'checkout_url': response.get('checkout_url')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'success': False,
                    'message': response.get('message', 'Failed to setup auto-payment')
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error setting up auto-payment: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoanAutoPayCancelAPI(APIView):
    """
    API to cancel auto-payment subscription for a loan.
    """
    def post(self, request, loan_ref_no):
        try:
            # Get loan details
            loan = get_object_or_404(LoanApplication, loan_ref_no=loan_ref_no)

            # Here you would:
            # 1. Find the active subscription for this loan
            # 2. Call AutoPaymentService.cancel_subscription(subscription_id)
            # 3. Update database status

            # For now, return success assuming cancellation
            return Response({
                'success': True,
                'message': 'Auto-payment cancelled successfully'
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error cancelling auto-payment: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoanAutoPayStatusAPI(APIView):
    """
    API to check if auto-payment is active for a loan.
    """
    def get(self, request, loan_ref_no):
        try:
            # Get loan details
            loan = get_object_or_404(LoanApplication, loan_ref_no=loan_ref_no)

            # Here you would check database for active subscription
            # For now, return false (not active)
            is_active = False

            return Response({
                'success': True,
                'is_active': is_active
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'success': False,
                'message': f'Error checking auto-payment status: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
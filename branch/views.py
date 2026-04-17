import json
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from django.utils.decorators import method_decorator
from .decorators import branch_permission_required

from django.urls import reverse
from django.contrib.auth.hashers import check_password
from django.utils import timezone

import agent
from .models import BranchEmployee, BranchTransaction, BranchRole, AgentDeposit, AgentDepositDenomination,BranchAccount
from headquater.models import Branch, HeadquartersWallet, HeadquartersTransactions, FundTransfers
# from .decorators import branch_manager_required
from agent.models import Agent
from rest_framework.views import APIView

from rest_framework.response import Response
from rest_framework import status
from django.contrib import messages
from .serializers import AgentSerializer
from loan.models import LoanApplication, CustomerDetail, DocumentReupload, DocumentReview, LoanPeriod, LoanEMISchedule, EmiAgentAssign, EmiCollectionDetail, LoanCloseRequest, ChartOfAccount, LoanRescheduleLog, LoanEMIReschedule, Shop, ShopBankAccount
from loan.services.reschedule import reschedule_loan_for_branch
from loan.serializers import LoanApplicationListSerializer, CustomerLoanDetailSerializer, CustomerAddressSerializer, DocumentRequestSerializer, LoanDisbursedListSerializer, LoanEMIScheduleSerializer, CustomerAccountSerializer
from branch.viewsapi import ChangePassword
from rest_framework.parsers import MultiPartParser, FormParser
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse
from django.template.loader import render_to_string
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from savings.models import SavingsCollection

from django.core.mail import EmailMultiAlternatives, get_connection
from django.conf import settings


# for generated pdf report of fund release#
import asyncio
from playwright.async_api import async_playwright
import subprocess
import sys
from django.core.paginator import Paginator, EmptyPage

from django.db.models.functions import TruncMonth, TruncYear, TruncDay
from django.db.models import Count, Sum, Q

from savings.models import SavingsAccountApplication

# Create your views here.

def branch_home(request):
    """Home view that redirects based on authentication status"""
    logged_user_id = request.session.get('logged_user_id')
    if logged_user_id:
        try:
            logged_user = BranchEmployee.objects.get(
                id=logged_user_id, 
                is_active=True
            )
            return redirect('branch:dashboard')
        except BranchEmployee.DoesNotExist:
            request.session.flush()
    # Redirect to a static login page or frontend login route
    return redirect('/branch/login/')

def branch_login_page(request):
    """Render the branch manager login page (for frontend)"""
    return render(request, 'branch/login.html')

class BranchManagerLoginAPIView(APIView):
    """REST API login for branch managers"""
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')
        if not email or not password:
            return Response({'detail': 'Email and password are required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            logged_user = BranchEmployee.objects.get(email=email, is_active=True)
            if not getattr(logged_user.branch, 'status', True):
                # Branch is inactive; do not allow login
                return Response({'detail': 'Branch is inactive. Please contact headquarters.'}, status=status.HTTP_403_FORBIDDEN)

            if check_password(password, logged_user.password):
                request.session['logged_user_id'] = logged_user.id
                request.session['logged_user_email'] = logged_user.email
                request.session['logged_user_branch_id'] = logged_user.branch.branch_id
                dashboard_url = reverse('branch:dashboard')
                return Response({
                    'detail': 'Login successful',
                    'logged_user_id': logged_user.id,
                    'logged_user_email': logged_user.email,
                    'logged_user_branch_id': logged_user.branch.branch_id,
                    'redirect_url': dashboard_url
                }, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Invalid email or password.'}, status=status.HTTP_401_UNAUTHORIZED)

def branch_logout(request):
    """Logout view for branch managers"""
    request.session.flush()
    return redirect('/branch/login/')

# @method_decorator(branch_manager_required, name='dispatch')
class BranchDashboardView(TemplateView):
    template_name = 'branch/dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")
        try:
            branch_employee = BranchEmployee.objects.get(
                id=logged_user_id,
                is_active=True
            )
        except BranchEmployee.DoesNotExist:
            request.session.flush()
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        # Prevent access if the branch itself is inactive
        branch = getattr(branch_employee, 'branch', None)
        if branch is not None and not getattr(branch, 'status', True):
            request.session.flush()
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        request.branch_employee = branch_employee
        request.branch_manager = branch_employee
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add branch manager info to context
        logged_user_id = self.request.session.get('logged_user_id')
        if logged_user_id:
            try:
                logged_user = BranchEmployee.objects.get(id=logged_user_id)
                context['branch_manager'] = logged_user
                context['branch'] = logged_user.branch
                branch = logged_user.branch
            except BranchEmployee.DoesNotExist:
                branch = None

            if branch:
                context['branch_approve_count'] = LoanApplication.objects.filter(branch=branch, status__in=["branch_approved", "hq_approved"]).count()
                context['branch_pending_count'] = LoanApplication.objects.filter(branch=branch, status="pending").count()
            else:
                context['branch_approve_count'] = 0
                context['branch_pending_count'] = 0
        return context


# @method_decorator(branch_manager_required, name='dispatch')
class BranchProfileView( TemplateView):
    template_name = 'branch/profile.html'
    
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     # Add branch manager info to context
    #     logged_user_id = self.request.session.get('logged_user_id')
    #     if logged_user_id:
    #         try:
    #             logged_user = BranchEmployee.objects.get(id=logged_user_id)
    #             context['branch_manager'] = logged_user
    #             context['branch'] = logged_user.branch
    #         except BranchEmployee.DoesNotExist:
    #             pass
    #     return context

def profile_image_update(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)

    logged_user_id = request.session.get('logged_user_id')
    if not logged_user_id:
        return JsonResponse({'success': False, 'message': 'Not logged in.'}, status=401)

    photo_file = request.FILES.get('photo')
    if not photo_file:
        return JsonResponse({'success': False, 'message': 'No photo provided.'}, status=400)

    try:
        employee = BranchEmployee.objects.get(id=logged_user_id)
    except BranchEmployee.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Agent not found.'}, status=404)

    employee.image = photo_file
    employee.save(update_fields=['image'])

    if getattr(employee, 'image', None):
        try:
            photo_url = employee.image.url
        except ValueError:
            photo_url = None
    else:
        photo_url = None

    return JsonResponse({
        'success': True,
        'message': 'Profile photo updated successfully.',
        'photo_url': photo_url
    })

def change_password(request):
    if request.method == 'POST':
        logged_user_id = request.session.get('logged_user_id')
        
        if not logged_user_id:
            return JsonResponse({'success': False, 'message': 'Not logged in.'}, status=401)

        mutable_post = request.POST.copy()
        new_password = mutable_post.get('new-password')
        confirm_password = mutable_post.get('confirm-password')

        mutable_post['logged_user_id'] = logged_user_id
        if new_password is not None:
            mutable_post['new_password'] = new_password
        if confirm_password is not None:
            mutable_post['confirm_password'] = confirm_password
        request._post = mutable_post

        api_response = ChangePassword.as_view()(request)
        if hasattr(api_response, 'render'):
            api_response.render()

        try:
            payload = json.loads(api_response.content)
        except (TypeError, ValueError):
            payload = {'message': 'Unable to process response from password service.'}

        success = api_response.status_code == 200
        payload.setdefault('success', success)

        return JsonResponse(payload, status=api_response.status_code)

    return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)


@method_decorator(branch_permission_required('add_loan'), name='dispatch')
class NewLaonApplication(TemplateView):
    template_name = 'loan/new_application.html'

    def get(self, request, *args, **kwargs):
        # Initialize context
        context = {
            'is_active': True,
            'error_message': None
        }
        # Get branch manager from session
        logged_user_id = request.session.get('logged_user_id')

        if logged_user_id:
            try:
                branch_manager = BranchEmployee.objects.get(id=logged_user_id)
                # Expose identifiers for draft feature
                context['branch_manager_id'] = branch_manager.id
                context['branch_id'] = getattr(branch_manager.branch, 'branch_id', None)
                # Check branch activity
                if not branch_manager.branch.status:
                    context['is_active'] = False
                    context['error_message'] = 'Cannot create loan application. Branch is currently inactive.'
                # Check branch manager activity
                elif not branch_manager.is_active:
                    context['is_active'] = False
                    context['error_message'] = 'Cannot create loan application. Branch manager is currently inactive.'
            except BranchEmployee.DoesNotExist:
                context['is_active'] = False
                context['error_message'] = 'Branch manager not found.'
        else:
            context['is_active'] = False
            context['error_message'] = 'Authentication required.'
        
        return render(request, self.template_name, context)

### --------- after applied form details edit --------- ###    
# @method_decorator(branch_manager_required, name='dispatch')
class LoanApplicationEdit(APIView):
    def post(self, request, customer_id, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
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
### ------ end after applied form details edit ---------- ###

@method_decorator(branch_permission_required('view_loans'), name='dispatch')
class PendingApplicationView(TemplateView):
    template_name = 'loan/pending_applications.html'

@method_decorator(branch_permission_required('view_loans'), name='dispatch')
class ApplicationDetailView(TemplateView):
    template_name = 'loan/application_detail.html'

@method_decorator(branch_permission_required('reject_loan'), name='dispatch')
class branchApplicationRejectView(TemplateView):
    template_name = 'loan/reject_loanApplication.html'


@method_decorator(branch_permission_required('approve_loan'), name='dispatch')
class branchApplicationApproveView(TemplateView):
    template_name = 'loan/approve_loanApplication.html'

@method_decorator(branch_permission_required('approve_loan'), name='dispatch')
class DocumentRequestHq(TemplateView):
    template_name = 'loan/branch_document_request.html'

@method_decorator(branch_permission_required('view_loans', 'approve_loan', 'reject_loan'), name='dispatch')
class DocumentRequestHqAPI(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        branch = branch_manager.branch
        # Get all document requests for this branch (by HQ or branch)
        from loan.models import DocumentRequest
        requests = (
            DocumentRequest.objects
            .filter(branch=branch, loan_application__isnull=False)
            .select_related('loan_application__customer')
            .order_by('-requested_at')
        )
        serializer = DocumentRequestSerializer(requests, many=True)
        return Response(serializer.data)
    
@method_decorator(branch_permission_required('view_loans'), name='dispatch')
class CompletedLoansView(TemplateView):
    template_name = 'loan/completed_close_loans.html'


class CompletedLoansAPI(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        branch = branch_manager.branch

        # Approved loan close requests for this branch
        close_qs = (
            LoanCloseRequest.objects
            .filter(branch=branch, status='approved')
            .select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent',
                'approved_by'
            )
            .order_by('-approved_at', '-requested_at')
        )

        results = []
        for req in close_qs:
            la = req.loan_application
            customer = getattr(la, 'customer', None)
            agent = getattr(la, 'agent', None)
            # before results.append(...)
            detail = la.loan_details.first() if hasattr(la, 'loan_details') else None
            customer = getattr(la, 'customer', None)
            
            # add these lines
            cat_id = None
            cat_name = None
            cat_display = None
            if detail and detail.loan_category:
                cat_id = getattr(detail.loan_category, 'category_id', None)
                cat_name = getattr(detail.loan_category, 'name', None)
                cat_display = str(detail.loan_category)
            
            # then in results.append
            results.append({
                'loan_ref_no': getattr(la, 'loan_ref_no', ''),
                'customer_name': getattr(customer, 'full_name', ''),
                'agent_name': getattr(agent, 'full_name', ''),
                'loan_amount': float(detail.loan_amount) if detail and detail.loan_amount is not None else None,
                'loan_category': cat_display,           # kept for compatibility
                'loan_category_id': cat_id,             # new
                'loan_category_name': cat_name,         # new
                'status': req.status,
                'closed_at': req.approved_at.isoformat() if req.approved_at else None,
                'customer_id': getattr(customer, 'customer_id', ''),  # ADD THIS
                'request_id': req.request_id,

            })

        return Response({'completed': results}, status=status.HTTP_200_OK)   


class DocumentReuploadBranchAPI(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch
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
            from loan.models import CustomerDetail, DocumentRequest, DocumentReupload
            try:
                customer = CustomerDetail.objects.get(customer_id=data['customer_id'], branch=branch)
                loan_application = customer.loan_application
                document_request = DocumentRequest.objects.get(
                    id=data['document_request_id'],
                    loan_application=loan_application,
                    branch=branch,
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
                uploaded_by=None  # Not an agent, could be set to branch_manager if model allows
            )
            # INSTANTLY update CustomerDocument with the uploaded file (for all types, including residential proof)
            customer_document = getattr(loan_application, 'documents', None)
            field_map = {
                'id_proof': 'id_proof',
                'income_proof': 'income_proof',
                'photo': 'photo',
                'signature': 'signature',
                'collateral': 'collateral',
                'residential_proof': 'residential_proof_file',
            }
            doc_type = data['document_type']
            field_name = field_map.get(doc_type)
            if customer_document and field_name:
                setattr(customer_document, field_name, files['uploaded_file'])
                customer_document.save()
            # Mark document request as resolved
            document_request.mark_as_resolved()

            # Auto-approve the uploaded document since branch uploaded it
            from loan.models import DocumentReview
            DocumentReview.objects.create(
                document_reupload=reupload,
                loan_application=loan_application,
                decision='approved',
                review_comment='Auto-approved after upload by branch',
                reviewed_by=branch_manager,
                branch=branch_manager.branch
            )

            # Check if all document requests for this loan are resolved
            remaining_requests = DocumentRequest.objects.filter(
                loan_application=loan_application,
                is_resolved=False
            ).exists()

            # Update loan application status to resubmitted only if all requests are resolved
            if loan_application and not remaining_requests:
                loan_application.status = 'branch_resubmitted'
                loan_application.save()
            # # Update loan application status to resubmitted
            # if loan_application:
            #     loan_application.status = 'branch_resubmitted'
            #     loan_application.save()
            return Response({
                'success': True,
                'message': 'Document uploaded successfully',
                'reupload_id': reupload.id
            }, status=status.HTTP_201_CREATED)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class PendingApplicationsAPI(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        from branch.models import BranchEmployee
        branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        branch = branch_manager.branch
        # Optional filter by agent (agent_id) when coming from Agent Overview "View Loans" button
        agent_id = request.GET.get('agent')

        # If agent filter is present, show ALL applications for that agent in this branch (any status)
        if agent_id:
            applications = LoanApplication.objects.filter(
                branch=branch,
                agent__agent_id=agent_id,
            ).select_related('customer', 'agent')
        else:
            # Otherwise, fetch pending loan applications for this branch (existing behavior)
            pending_statuses = [
                'pending', 'document_requested', 'resubmitted', 'rejected_by_branch',
                'branch_document_accepted', 'branch_approved', 'branch_resubmitted',
                'hq_resubmitted', 'hq_document_accepted', 'document_requested_by_hq',
                'hq_approved', 'hq_rejected'
            ]
            applications = LoanApplication.objects.filter(
                branch=branch,
                status__in=pending_statuses,
            ).select_related('customer', 'agent').order_by('-submitted_at')

        serializer = LoanApplicationListSerializer(applications, many=True)
        return Response(serializer.data)
    
class DocumentRequestAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            data = request.data
            
            # Validate required fields
            required_fields = ['customer_id', 'document_type', 'reason']
            for field in required_fields:
                if field not in data:
                    return Response({'detail': f'{field} is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get customer
            from loan.models import CustomerDetail, DocumentRequest, LoanApplication
            try:
                customer = CustomerDetail.objects.get(customer_id=data['customer_id'])
            except CustomerDetail.DoesNotExist:
                return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
            # Get loan application for this customer
            try:
                loan_application = LoanApplication.objects.get(customer=customer)
            except LoanApplication.DoesNotExist:
                return Response({'detail': 'Loan application not found for this customer.'}, status=status.HTTP_404_NOT_FOUND)
            # Create document request
            document_request = DocumentRequest.objects.create(
                loan_application=loan_application,
                document_type=data['document_type'],
                reason=data['reason'],
                comment=data.get('comment', ''),
                requested_by=branch_manager,
                branch=branch_manager.branch
            )
            
            # Update loan application status to document_requested
            loan_application.status = 'document_requested'
            loan_application.save()
            
            return Response({
                'success': True,
                'message': 'Document request created successfully',
                'request_id': document_request.id
            }, status=status.HTTP_201_CREATED)
            
        except CustomerDetail.DoesNotExist:
            return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DocumentReviewAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            data = request.data
            
            # Validate required fields
            required_fields = ['reupload_id', 'decision']
            for field in required_fields:
                if field not in data:
                    return Response({'detail': f'{field} is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get document reupload
            from loan.models import DocumentReupload, DocumentReview
            try:
                reupload = DocumentReupload.objects.get(id=data['reupload_id'])
            except DocumentReupload.DoesNotExist:
                return Response({'detail': 'Document reupload not found.'}, status=status.HTTP_404_NOT_FOUND)
            
            # Set status based on decision (since model no longer does this)
            if data['decision'] == 'approved':
                # reupload.loan_application.status = 'branch_document_accepted'
                # Update the corresponding field in CustomerDocument
                customer_document = getattr(reupload.loan_application, 'documents', None)
                field_map = {
                    'id_proof': 'id_proof',
                    'income_proof': 'income_proof',
                    'photo': 'photo',
                    'signature': 'signature',
                    'collateral': 'collateral',
                    'residential_proof': 'residential_proof_file',
                }
                doc_type = reupload.document_type
                field_name = field_map.get(doc_type)
                if customer_document and field_name:
                    setattr(customer_document, field_name, reupload.uploaded_file)
                    customer_document.save()

                # Check if all document reuploads for this loan have been approved
                all_reuploads = DocumentReupload.objects.filter(loan_application=reupload.loan_application)
                all_approved = True
                for r in all_reuploads:
                    if not r.reviews.filter(decision='approved').exists():
                        all_approved = False
                        break

                # Only update status when ALL reuploads are approved
                if all_approved:
                    reupload.loan_application.status = 'branch_document_accepted'
                    reupload.loan_application.save()

            elif data['decision'] in ['rejected', 'request_again']:
                reupload.loan_application.status = 'document_requested'
            elif data['decision'] == 'reject_application':
                reupload.loan_application.status = 'reject'
                reupload.loan_application.save()
            
            # Create document review
            review = DocumentReview.objects.create(
                document_reupload=reupload,
                loan_application=reupload.loan_application,
                decision=data['decision'],
                review_comment=data.get('review_comment', ''),
                reviewed_by=branch_manager,
                branch=branch_manager.branch
            )
            
            # If decision is to request again, create a new document request
            if data['decision'] == 'request_again':
                from loan.models import DocumentRequest
                DocumentRequest.objects.create(
                    loan_application=reupload.loan_application,
                    document_type=reupload.document_type,
                    reason='other',
                    comment=f"Re-requested after review. Previous comment: {data.get('review_comment', '')}",
                    requested_by=branch_manager,
                    branch=branch_manager.branch
                )
            
            return Response({
                'success': True,
                'message': 'Document review completed successfully',
                'review_id': review.id,
                'new_status': reupload.loan_application.status
            }, status=status.HTTP_201_CREATED)
            
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ApproveApplicationAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            data = request.data
            customer_id = data.get('customer_id')
            if not customer_id:
                return Response({'detail': 'customer_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            from loan.models import CustomerDetail, LoanApplication
            try:
                customer = CustomerDetail.objects.get(customer_id=customer_id)
            except CustomerDetail.DoesNotExist:
                return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
            loan_app = LoanApplication.objects.filter(customer=customer).order_by('-submitted_at').first()
            if not loan_app:
                return Response({'detail': 'Loan application not found for this customer.'}, status=status.HTTP_404_NOT_FOUND)

            from loan.models import DocumentRequest
            if loan_app.status in ['document_requested', 'document_requested_by_hq']:
                return Response({'detail': 'Cannot approve while documents are requested.'}, status=status.HTTP_400_BAD_REQUEST)
            if DocumentRequest.objects.filter(loan_application=loan_app, is_resolved=False).exists():
                return Response({'detail': 'Cannot approve while document requests are pending.'}, status=status.HTTP_400_BAD_REQUEST)

            loan_app.status = 'branch_approved'
            loan_app.ever_branch_approved = True
            loan_app.save()
            return Response({'success': True, 'new_status': loan_app.status}, status=status.HTTP_200_OK)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            print('ApproveApplicationAPIView error:', traceback.format_exc())
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RejectApplicationAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            data = request.data
            customer_id = data.get('customer_id')
            reason = data.get('reason', '')
            if not customer_id:
                return Response({'detail': 'customer_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
            from loan.models import CustomerDetail, LoanApplication
            try:
                customer = CustomerDetail.objects.get(customer_id=customer_id)
            except CustomerDetail.DoesNotExist:
                return Response({'detail': 'Customer not found.'}, status=status.HTTP_404_NOT_FOUND)
            loan_app = LoanApplication.objects.filter(customer=customer).order_by('-submitted_at').first()
            if not loan_app:
                return Response({'detail': 'Loan application not found for this customer.'}, status=status.HTTP_404_NOT_FOUND)

            from loan.models import DocumentRequest
            if loan_app.status in ['document_requested', 'document_requested_by_hq']:
                return Response({'detail': 'Cannot reject while documents are requested.'}, status=status.HTTP_400_BAD_REQUEST)
            if DocumentRequest.objects.filter(loan_application=loan_app, is_resolved=False).exists():
                return Response({'detail': 'Cannot reject while document requests are pending.'}, status=status.HTTP_400_BAD_REQUEST)

            loan_app.status = 'rejected_by_branch'
            loan_app.rejection_reason = reason
            loan_app.save()
            # Optionally, store the reason on the customer for legacy display
            customer.branch_rejection_reason = reason
            customer.save()
            return Response({'success': True, 'new_status': loan_app.status}, status=status.HTTP_200_OK)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BranchApplicationDetailAPI(APIView):
    def get(self, request, customer_id, loan_ref_no):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            customer = CustomerDetail.objects.get(customer_id=customer_id)
            print('Fetched customer:', customer)
            loan_app = LoanApplication.objects.filter(loan_ref_no=loan_ref_no, customer=customer).order_by('-submitted_at').first()
            print('Fetched loan_app:', loan_app)
            if not loan_app:
                print('No loan_app found for customer:', customer_id)
                return Response({'detail': 'Not found.'}, status=404)
            address = getattr(customer, 'address', None)
            loans = loan_app.loan_details.select_related('loan_category__main_category').all()
            documents = getattr(loan_app, 'documents', None)
            agent = loan_app.agent
            document_reuploads = loan_app.document_reuploads.all()
            print('reupload document', document_reuploads)
            document_reviews = loan_app.document_reviews.all()
            document_requests = loan_app.document_requests.all()

            first_loan = loans.first()
            is_shop_active = bool(
                first_loan
                and getattr(first_loan, 'loan_category', None)
                and getattr(first_loan.loan_category, 'main_category', None)
                and bool(getattr(first_loan.loan_category.main_category, 'is_shop_active', False))
            )

            # Helper to get latest approved document reupload or original
            from loan.models import DocumentReupload
            # def get_best_document(loan_application, doc_type, original_file):
            #     # Special handling for residential proof: check both possible doc_type values
            #     if doc_type in ['residential_proof', 'residential_proof_file']:
            #         reuploads = (
            #             DocumentReupload.objects
            #             .filter(loan_application=loan_application, document_type__in=['residential_proof', 'residential_proof_file'])
            #             .order_by('-uploaded_at')
            #         )
            #     else:
            #         reuploads = (
            #             DocumentReupload.objects
            #             .filter(loan_application=loan_application, document_type=doc_type)
            #             .order_by('-uploaded_at')
            #         )
            #     # Always show the latest reupload if it exists (regardless of review status)
            #     latest = reuploads.first()
            #     if latest and latest.uploaded_file:
            #         return latest.uploaded_file.url
            #     # Fallback to original
            #     return getattr(original_file, 'url', None) if original_file else None

            def get_best_document(loan_application, doc_type, original_file):
                if doc_type in ['residential_proof', 'residential_proof_file']:
                    reuploads = (
                        DocumentReupload.objects
                        .filter(loan_application=loan_application, document_type__in=['residential_proof', 'residential_proof_file'])
                        .order_by('-uploaded_at')
                    )
                else:
                    reuploads = (
                        DocumentReupload.objects
                        .filter(loan_application=loan_application, document_type=doc_type)
                        .order_by('-uploaded_at')
                    )
                latest = reuploads.first()
                if latest and latest.uploaded_file:
                    approved_review = latest.reviews.filter(decision='approved').exists()
                    if approved_review:
                        return latest.uploaded_file.url
                return getattr(original_file, 'url', None) if original_file else None

            documents_data = None
            if documents:
                documents_data = {
                    'id_proof': get_best_document(loan_app, 'id_proof', documents.id_proof),
                    'pan_card_document': get_best_document(loan_app, 'pan_card_document', getattr(documents, 'pan_card_document', None)),
                    'id_proof_back': get_best_document(loan_app, 'id_proof_back', documents.id_proof_back),
                    'income_proof': get_best_document(loan_app, 'income_proof', documents.income_proof),
                    'photo': get_best_document(loan_app, 'photo', documents.photo),
                    'signature': get_best_document(loan_app, 'signature', documents.signature),
                    'collateral': get_best_document(loan_app, 'collateral', documents.collateral),
                    'residential_proof_file': get_best_document(loan_app, 'residential_proof', documents.residential_proof_file),
                }
            

            
            customer_detail_snapshot = loan_app.customer_snapshot.get('customer_details', {}) if loan_app.customer_snapshot else {}
            customer_address_snapshot = loan_app.customer_snapshot.get('address', {}) if loan_app.customer_snapshot else {}
            customer_documents_snapshot = loan_app.customer_snapshot.get('documents', {}) if loan_app.customer_snapshot else {}
            customer_bank_details_snapshot = loan_app.customer_snapshot.get('bank_details', {}) if loan_app.customer_snapshot else {}
            print(customer_detail_snapshot)
            is_old_loan = customer.loan_application_id != loan_app.loan_ref_no
            print('is_old_loan -> ', is_old_loan)

            data = {
                'loan_ref_no': loan_app.loan_ref_no,
                'customer_id': customer.customer_id,
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
                'branch_rejection_reason': customer.branch_rejection_reason,
                'agent': AgentSerializer(agent).data if agent else None,
                'loans': CustomerLoanDetailSerializer(loans, many=True).data,
                'shop': {
                    'shop_id': loan_app.shop.shop_id,
                    'name': loan_app.shop.name
                } if loan_app.shop else None,
                'is_shop_active': is_shop_active,
                'address': customer_address_snapshot if is_old_loan else CustomerAddressSerializer(address).data if address else None,
                'customer_account': (
                    customer_bank_details_snapshot if is_old_loan else 
                    CustomerAccountSerializer(customer.account).data
                    if hasattr(customer, 'account') and customer.account else None
                ),
                'documents': documents_data,
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
                ],
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
                ]
            }
            print(data['address'])
            return Response(data)
        except Exception as e:
            import traceback
            print('BranchApplicationDetailAPI error:', traceback.format_exc())
            return Response({'detail': f'Internal server error: {str(e)}'}, status=500)
        
    
    def _get_customer_details(self, customer:CustomerDetail, isOld:bool, customer_detail_snapshot, field_name):
        return getattr(customer, field_name, '') if not isOld else customer_detail_snapshot.get(field_name, '')



class BranchApplicationRejectedViewByHQAPI(APIView):
    def get(self, request):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail':'Authentication required.'},
            status=status.HTTP_403_FORBIDDEN)
        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch
            # Get all loan applications for this branch rejected by branch or HQ
            applications = LoanApplication.objects.filter(branch=branch, status__in=['rejected_by_branch', 'hq_rejected']).select_related('customer', 'agent')
            serializer = LoanApplicationListSerializer(applications, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BranchApplicationApprovedViewByHQAPI(APIView):
    def get(self, request):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'details':'Authentication required.'},
            status=status.HTTP_403_FORBIDDEN)
        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch
            applications = LoanApplication.objects.filter(branch=branch, status='hq_approved').select_related('customer', 'agent')
            serializer = LoanApplicationListSerializer(applications, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except BranchEmployee.DoesNotExist:
            return Response({'details':'Branch manager not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status.HTTP_500_INTERNAL_SERVER_ERROR)

def branch_manager_info_api(request):
    logged_user_id = request.session.get('logged_user_id')
    if logged_user_id:
        try:
            manager = BranchEmployee.objects.select_related('branch').get(id=logged_user_id)
            full_name = f"{(manager.first_name or '').strip()} {(manager.last_name or '').strip()}".strip()
            if getattr(manager, 'image', None):
                try:
                    photo_url = str(manager.image.url)
                except ValueError:
                    photo_url = '/static/images/placeholder/user.webp'
            else:
                photo_url = '/static/images/placeholder/user.webp'
            
            if manager.is_manager:
                # For managers, set static branch manager role with all permissions
                role_data = {
                    'role_id': None,  # No specific role ID for static manager role
                    'role_name': 'Branch Manager',
                    'permissions': ['all'],  # Indicates all permissions are available
                }

                manager_data ={
                    'id': manager.id,
                    'name': full_name,
                    'email': manager.email,
                    'phone': manager.phone_number,
                }

            elif manager.role_id:
                # For non-managers, fetch role details from database
                role = BranchRole.objects.get(id=manager.role_id)
                role_data = {
                    'role_id': role.id,
                    'role_name': role.name,
                    'permissions': [perm.name for perm in role.permissions.all()],
                }

                manager_raw = BranchEmployee.objects.filter(
                    is_manager=True, 
                    branch_id=manager.branch_id
                ).values('id', 'first_name', 'last_name', 'email', 'phone_number').first()
                
                manager_data = {
                    'id': manager_raw['id'],
                    'name': f"{manager_raw['first_name']} {manager_raw['last_name']}",
                    'email': manager_raw['email'],
                    'phone': manager_raw['phone_number'],
                } if manager_raw else None
            else:
                # No role assigned and not a manager
                role_data = None
                manager_data = None

            branch = manager.branch if hasattr(manager, 'branch') else None
            branch_data = None
            if branch:
                branch_data = {
                    'branch_id': branch.branch_id,
                    'branch_name': branch.branch_name,
                    'email': branch.email,
                    'contact_number': branch.contact_number,
                    'status': branch.status,
                    'wallet_balance': str(branch.wallet_balance) if hasattr(branch, 'wallet_balance') else None,
                    'address_line_1': branch.address_line_1,
                    'address_line_2': branch.address_line_2,
                    'city': branch.city,
                    'state': branch.state,
                    'postal_code': branch.postal_code,
                    'country': branch.country,
                    'district': branch.district,
                    'created_at': branch.created_at,
                    'updated_at': branch.updated_at,
                }

            return JsonResponse({
                'success': True,
                'manager': {
                    'id': manager.id,
                    'role': role_data,
                    'manager': manager_data,
                    'email': manager.email,
                    'full_name': full_name or None,
                    'first_name': manager.first_name or None,
                    'last_name': manager.last_name or None,
                    'phone_number': manager.phone_number,
                    'address': manager.address,
                    'date_of_birth': manager.date_of_birth.strftime('%d-%m-%Y') if manager.date_of_birth else None,
                    'gender': manager.gender,
                    'is_active': manager.is_active,
                    'gov_id_type': manager.gov_id_type,
                    'gov_id_number': manager.gov_id_number,
                    'created_at': manager.created_at.strftime('%d-%m-%Y') if manager.created_at else None,
                    'updated_at': manager.updated_at.strftime('%d-%m-%Y') if manager.updated_at else None,
                    'created_by': manager.created_by,
                    'profile_img': photo_url,
                    'branch': branch_data,
                }
            })
        except BranchEmployee.DoesNotExist:
            pass
    return JsonResponse({'success': False, 'error': 'Not logged in'}, status=401)


########### disbursement by HQ ############
@method_decorator(branch_permission_required('view_loans', 'approve_loan', 'disburse_loan'), name='dispatch')
class DisbursedByHQView(TemplateView):
    template_name = 'loan-disbursed/loan-disbursedList.html'

@method_decorator(branch_permission_required('view_loans', 'approve_loan', 'disburse_loan'), name='dispatch')
class DisbursedDetailByHQView(TemplateView):
    template_name = 'loan-disbursed/loan-disbursedDetails.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        logged_user_id = self.request.session.get('logged_user_id')

        if logged_user_id:
            try:
                branch_manager = BranchEmployee.objects.get(id=logged_user_id)
                branch = branch_manager.branch
                context['bank_account'] = BranchAccount.objects.filter(branch=branch)
            except BranchEmployee.DoesNotExist:
                context['bank_account'] = BranchAccount.objects.none()
        else:
            context['bank_account'] = BranchAccount.objects.none()
        return context


class DisbursedByHQAPI(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        # from branch.models import BranchEmployee
        branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        branch = branch_manager.branch
        # Fetch pending loan applications for this branch
        pending_statuses = ['disbursed']
        applications = LoanApplication.objects.filter(branch=branch, status__in=pending_statuses).select_related('customer', 'agent')
        serializer = LoanDisbursedListSerializer(applications, many=True)
        return Response(serializer.data)


class DisbursedDetailByHQAPI(APIView):
    def get(self, request, loan_ref_no, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'details': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        branch = branch_manager.branch
        pending_statuses = ['disbursed']
        applications = (
            LoanApplication.objects
            .filter(branch=branch, status__in=pending_statuses, loan_ref_no=loan_ref_no)
            .select_related('customer', 'agent', 'shop')
        )
        serializer = LoanDisbursedListSerializer(applications, many=True)
        return Response(serializer.data)


class DisbursementSubmitAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch
            
            # Note: Branch.wallet_balance removed; using account-based balances only.
            data = request.data
            
            # Validate required fields
            required_fields = ['loan_ref_no', 'account_id', 'disbursed_amount', 'net_amount', 'disbursement_date']
            for field in required_fields:
                if field not in data:
                    return Response({'detail': f'{field} is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse disbursed amount
            try:
                disbursed_amount = Decimal(str(data['disbursed_amount']))
                net_amount = Decimal(str(data['net_amount']))
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'Invalid amount format.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate disbursement date
            from datetime import datetime
            try:
                disbursement_date = datetime.strptime(data['disbursement_date'], '%Y-%m-%d').date()
                if disbursement_date > timezone.now().date():
                    return Response({'detail': 'Disbursement date cannot be in the future.'}, status=status.HTTP_400_BAD_REQUEST)
            except ValueError:
                return Response({'detail': 'Invalid disbursement date format.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get BranchAccount (source of funds for disbursement)
            try:
                from branch.models import BranchAccount
                account_id = data.get('account_id') or data.get('chart_of_accounts')
                branch_account = BranchAccount.objects.get(id=account_id, branch=branch)
                disbursement_mode =  branch_account.type
            except BranchAccount.DoesNotExist:
                return Response({'detail': 'Invalid source account selected.'}, status=status.HTTP_400_BAD_REQUEST)

            # Get loan application
            from loan.models import LoanApplication, DisbursementLog
            try:
                loan_application = LoanApplication.objects.get(loan_ref_no=data['loan_ref_no'])
            except LoanApplication.DoesNotExist:
                return Response({'detail': 'Loan application not found.'}, status=status.HTTP_404_NOT_FOUND)
            
            # Check if loan is already disbursed
            if loan_application.status == 'disbursed_fund_released':
                return Response({'detail': 'Loan is already disbursed.'}, status=status.HTTP_400_BAD_REQUEST)
            

            # Calculate tax charges (deductions retained by branch)
            tax_charges = disbursed_amount - net_amount

            # Debit the selected BranchAccount and create BranchTransaction(s) for the disbursement
            from .models import BranchTransaction
            with transaction.atomic():
                # Resolve disbursement destination (customer vs shop)
                shop_bank_account_id = data.get('shop_bank_account_id')
                destination_bank_name = (data.get('bank_name') or '')
                destination_account_number = (data.get('account_upi') or '')
                destination_name = (loan_application.customer.full_name if loan_application.customer else None)
                shop_bank_account = None

                if loan_application.shop:
                    from loan.models import ShopBankAccount
                    shop_has_accounts = ShopBankAccount.objects.filter(shop=loan_application.shop).exists()

                    # If loan has shop, shop bank account is always mandatory
                    if not shop_has_accounts:
                        return Response({'detail': 'Please add bank account for this shop before disbursement.'}, status=status.HTTP_400_BAD_REQUEST)

                    if not shop_bank_account_id:
                        return Response({'detail': 'Please select shop bank account.'}, status=status.HTTP_400_BAD_REQUEST)

                    # Validate it belongs to this shop and route disbursement to it
                    try:
                        shop_bank_account = ShopBankAccount.objects.select_for_update().get(
                            bank_account_id=shop_bank_account_id,
                            shop=loan_application.shop,
                        )
                    except ShopBankAccount.DoesNotExist:
                        return Response({'detail': 'Invalid shop bank account selected.'}, status=status.HTTP_400_BAD_REQUEST)

                    destination_bank_name = shop_bank_account.bank_name
                    destination_account_number = shop_bank_account.account_number
                    destination_name = loan_application.shop.name

                # Create disbursement log
                disbursement_log = DisbursementLog.objects.create(
                    loan_id=loan_application,
                    amount=disbursed_amount,
                    disb_mode=disbursement_mode,
                    bank_name=destination_bank_name,
                    account_number=destination_account_number,
                    net_amount_cust=net_amount,
                    tax_charges=tax_charges,
                    disburse_proof=data.get('proof_of_disbursement', ''),
                    remarks=data.get('disbursement_remarks', ''),
                    disbursed_by=branch_manager.branch,
                    disbursed_to=loan_application
                )

                # Validate sufficient balance in selected account for the full disbursed amount
                if branch_account.current_balance < disbursed_amount:
                    return Response({
                        'detail': f'Insufficient balance in {branch_account.bank_name} ({branch_account.account_number}). Available: ₹{branch_account.current_balance:.2f}'
                    }, status=status.HTTP_400_BAD_REQUEST)

                # Update account balance: first debit full disbursed amount, then credit deductions
                # Net impact remains equal to net_amount
                new_balance = Decimal(branch_account.current_balance) - disbursed_amount
                if tax_charges > 0:
                    new_balance += tax_charges
                branch_account.current_balance = new_balance.quantize(Decimal('0.01'))
                branch_account.save(update_fields=['current_balance', 'updated_at'])

                # Determine ChartOfAccount (COA) based on loan EMI frequency
                from loan.models import LoanEMISchedule, ChartOfAccount
                first_emi = (
                    LoanEMISchedule.objects
                    .filter(loan_application=loan_application)
                    .order_by('installment_date')
                    .first()
                )
                freq = (first_emi.frequency if first_emi else '').lower()
                # Map: daily -> 120, weekly (group) -> 121; default to daily if unknown
                coa_code = '120' if freq == 'daily' else ('121' if freq == 'weekly' else '120')
                coa = ChartOfAccount.objects.filter(code=coa_code).first()
                coa_head = coa.head_of_account if coa else 'Loan disbursement'
                coa_desc = (coa.description if coa and coa.description else f"Loan disbursement for {freq or 'daily'} collection")
                coa_code_val = coa.code if coa else None

                # 1) DEBIT transaction for full disbursed amount
                BranchTransaction.objects.create(
                    branch=branch_manager.branch,
                    branch_account=branch_account,
                    disbursement_log=disbursement_log,
                    transaction_type='DEBIT',
                    purpose=coa_head,
                    code=coa_code_val,
                    mode=disbursement_mode,
                    bank_payment_method=data.get('bank_payment_method'),
                    amount=disbursed_amount,
                    transfer_to_from=destination_name,
                    description=f"{coa_head} - {coa_desc}",
                    created_by=branch_manager,
                    transaction_date=timezone.now()
                )

                # 2) CREDIT transaction for deduction amount (if any) back to the same account
                if tax_charges > 0:
                    BranchTransaction.objects.create(
                        branch=branch_manager.branch,
                        branch_account=branch_account,
                        disbursement_log=disbursement_log,
                        transaction_type='CREDIT',
                        purpose=f"{coa_head} - Deductions",
                        code=coa_code_val,
                        mode=disbursement_mode,
                        bank_payment_method=data.get('bank_payment_method'),
                        amount=tax_charges,
                        transfer_to_from=destination_name,
                        description=f"Deductions retained on loan disbursement for {freq or 'daily'} collection",
                        created_by=branch_manager,
                        transaction_date=timezone.now()
                    )
            
                # Shop-side internal balance tracking (credit net_amount to selected shop account)
                if shop_bank_account:
                    shop_bank_account.current_balance = (shop_bank_account.current_balance + net_amount).quantize(Decimal('0.01'))
                    shop_bank_account.save(update_fields=['current_balance', 'updated_at'])

                    # Persist selected shop bank account for this loan
                    loan_application.shop_bank_account = shop_bank_account

                # Update loan application status to "disbursed - fund release"
                loan_application.status = 'disbursed_fund_released'
                loan_application.disbursed_at = timezone.now()
                loan_application.save()

            # Get the LoanPeriod for this specific loan application
            loan_period = LoanPeriod.objects.filter(loan_application=loan_application).first()
            if not loan_period:
                raise Exception('Loan period details not found for this loan application')

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Processing EMI schedule for loan application: {loan_application.loan_ref_no}")

            principal = Decimal(str(loan_period.loan_amount))
            emi = Decimal(str(loan_period.installment_size))
            total_repayment = Decimal(str(loan_period.realizable_amount))
            total_interest = total_repayment - principal

            loan_detail = loan_application.loan_details.first()
            unit = 'months'
            frequency = 'monthly'
            num_installments = int(loan_period.number_of_installments)
            if loan_detail and hasattr(loan_detail, 'tenure') and loan_detail.tenure:
                unit = loan_detail.tenure.unit.lower()
                tenure_value = int(loan_detail.tenure.value)
                if unit in ['days', 'day']:
                    frequency = 'daily'
                    num_installments = tenure_value
                elif unit in ['weeks', 'week']:
                    frequency = 'weekly'
                    num_installments = tenure_value
                elif unit in ['months', 'month']:
                    frequency = 'monthly'
                    num_installments = tenure_value
                elif unit in ['years', 'year']:
                    frequency = 'monthly'
                    num_installments = tenure_value * 12
                else:
                    frequency = 'monthly'
                    num_installments = int(loan_period.number_of_installments)
            else:
                frequency = 'monthly'
                num_installments = int(loan_period.number_of_installments)

            try:
                from dateutil.relativedelta import relativedelta
            except ImportError:
                raise Exception('dateutil.relativedelta is required for EMI schedule calculation')

            def get_next_due_date(start_date, n):
                if frequency == 'daily':
                    return start_date + timedelta(days=n)
                elif frequency == 'weekly':
                    return start_date + timedelta(weeks=n)
                elif frequency == 'monthly':
                    return start_date + relativedelta(months=+n)
                else:
                    return start_date + relativedelta(months=+n)

            LoanEMISchedule.objects.filter(loan_application=loan_application).delete()

            with transaction.atomic():
                current_date = timezone.now().date()
                for i in range(1, num_installments + 1):
                    due_date = get_next_due_date(current_date, i)
                    principal_portion = (principal / num_installments).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    interest_portion = (total_interest / num_installments).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    if i == num_installments:
                        principal_portion = principal - (principal_portion * (num_installments - 1))
                        interest_portion = total_interest - (interest_portion * (num_installments - 1))
                        principal_portion = principal_portion.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                        interest_portion = interest_portion.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    emi_schedule = LoanEMISchedule.objects.create(
                        loan_application=loan_application,
                        installment_date=due_date,
                        frequency=frequency,
                        installment_amount=emi.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                        principal_amount=principal_portion,
                        interest_amount=interest_portion,
                        paid=False,
                        is_overdue=False,
                        overdue_days=0,
                        late_fee=Decimal('0.00')
                    )
                    logger.info(f"Created EMI schedule: {emi_schedule}")

                # Assign agent to EMIs if loan has agent
                if loan_application.created_by_agent:
                    from loan.models import EmiAgentAssign
                    for emi in LoanEMISchedule.objects.filter(loan_application=loan_application):
                        if not EmiAgentAssign.objects.filter(emi=emi, is_active=True).exists():
                            EmiAgentAssign.objects.create(agent=loan_application.agent, emi=emi, assigned_by=branch_manager)

            #--- Email Notification: Loan Disbursed ---
            try:
                import logging
                
                # Set up logging
                logger = logging.getLogger(__name__)
                
                # Debug email settings
                print("\n[Email Debug] Checking email configuration:")
                print(f"EMAIL_BACKEND: {getattr(settings, 'EMAIL_BACKEND', 'Not set')}")
                print(f"EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'Not set')}")
                print(f"EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'Not set')}")
                print(f"EMAIL_USE_TLS: {getattr(settings, 'EMAIL_USE_TLS', 'Not set')}")
                print(f"DEFAULT_FROM_EMAIL: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not set')}")
                print(f"HQ_NOTIFICATION_EMAIL: {getattr(settings, 'HQ_NOTIFICATION_EMAIL', 'Not set')}\n")
                
                # Collect recipients
                recipient_list = []
                
                # 1. Customer email
                try:
                    if hasattr(loan_application, 'customer') and getattr(loan_application.customer, 'email', None):
                        customer_email = loan_application.customer.email.strip()
                        if customer_email:
                            recipient_list.append(customer_email)
                            print(f"[Email] Added customer email: {customer_email}")
                        else:
                            print("[Email] Customer email is empty")
                    else:
                        print("[Email] No customer email found in loan application")
                except Exception as e:
                    print(f"[Email Error] Error getting customer email: {str(e)}")
                
                # 2. Agent email
                try:
                    if hasattr(loan_application, 'agent') and loan_application.agent:
                        agent_email = getattr(loan_application.agent, 'email', '').strip()
                        if agent_email and agent_email not in recipient_list:
                            recipient_list.append(agent_email)
                            print(f"[Email] Added agent email: {agent_email}")
                        else:
                            print("[Email] No agent email found or already in list")
                    else:
                        print("[Email] No agent associated with this loan")
                except Exception as e:
                    print(f"[Email Error] Error getting agent email: {str(e)}")
                
                # 3. Branch email
                try:
                    branch_email = getattr(branch, 'email', '').strip()
                    if branch_email and branch_email not in recipient_list:
                        recipient_list.append(branch_email)
                        print(f"[Email] Added branch email: {branch_email}")
                    else:
                        print("[Email] No branch email found or already in list")
                except Exception as e:
                    print(f"[Email Error] Error getting branch email: {str(e)}")
                
                # 4. HQ email from settings
                try:
                    hq_email = getattr(settings, 'HQ_NOTIFICATION_EMAIL', '').strip()
                    if hq_email and hq_email not in recipient_list:
                        recipient_list.append(hq_email)
                        print(f"[Email] Added HQ email: {hq_email}")
                    else:
                        print("[Email] No HQ email configured or already in list")
                except Exception as e:
                    print(f"[Email Error] Error getting HQ email: {str(e)}")
                
                print(f"\n[Email] Final recipient list: {', '.join(recipient_list) if recipient_list else 'No recipients'}")
                
                if not recipient_list:
                    print("[Email] No recipients to send email to")
                    return
                
                # Prepare email content
                subject = f"Loan Disbursed - Ref: {loan_application.loan_ref_no}"
                
                # Get loan details
                try:
                    period = getattr(loan_application, 'periods', None)
                    if period and hasattr(period, 'first') and period.first():
                        actual_percentage = period.first().rate_of_interest
                    else:
                        loan_detail = getattr(loan_application, 'loan_details', None)
                        if loan_detail and hasattr(loan_detail, 'first') and loan_detail.first() and getattr(loan_detail.first(), 'interest_rate', None):
                            actual_percentage = loan_detail.first().interest_rate.rate_of_interest
                        else:
                            actual_percentage = None
                except Exception as e:
                    print(f"[Email Error] Error getting interest rate: {str(e)}")
                    actual_percentage = None
                
                # Get loan detail for other fields
                loan_detail = loan_application.loan_details.first() if loan_application.loan_details.exists() else None
                
                # Prepare context for email template
                context = {
                    'loan_ref_no': loan_application.loan_ref_no,
                    'customer_name': loan_application.customer.full_name if hasattr(loan_application, 'customer') and loan_application.customer else 'N/A',
                    'customer_contact': loan_application.customer.contact if hasattr(loan_application, 'customer') and loan_application.customer else 'N/A',
                    'loan_amount': str(disbursed_amount) if disbursed_amount else 'N/A',
                    'net_amount_cust': str(net_amount) if net_amount else 'N/A',
                    'emi': loan_detail.emi if loan_detail and hasattr(loan_detail, 'emi') else 'N/A',
                    'tenure': loan_detail.tenure if loan_detail and hasattr(loan_detail, 'tenure') else 'N/A',
                    'disb_mode': data.get('disbursement_mode', 'N/A'),
                    'percentage': actual_percentage or 'N/A',
                    'bank_name': destination_bank_name or 'N/A',
                    'account_number': destination_account_number or 'N/A',
                    'tax_charges': str(tax_charges) if tax_charges is not None else 'N/A',
                    'sub_header': 'Loan Disbursed and Fund Released Successfully',
                    'purpose_flag': 'loan_disbursed',
                }
                
                # Create plain text version
                message_text = (
                    "SUNDARAM FINANCE\n"
                    "==================\n\n"
                    "Loan Disbursement Notification\n\n"
                    f"Reference No: {context['loan_ref_no']}\n"
                    f"Customer Name: {context['customer_name']}\n"
                    f"Contact Number: {context['customer_contact']}\n"
                    f"Loan Amount Disbursed: {context['loan_amount']}\n"
                    f"Disbursement Mode: {context['disb_mode']}\n"
                    f"Bank Name: {context['bank_name']}\n"
                    f"Account/UPI: {context['account_number']}\n\n"
                    "Thank you for choosing Sundaram Finance.\n"
                )
                
                # Create HTML version
                try:
                    message_html = render_to_string('loan/loan_application_email.html', context)
                    print("[Email] Successfully rendered HTML template")
                except Exception as template_error:
                    message_html = None
                    print(f"[Email Error] Error rendering HTML template: {str(template_error)}")
                
                # Create email
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sundaramfinance.com')
                print(f"[Email] Sending from: {from_email}")
                
                # Test connection before sending
                try:
                    connection = get_connection()
                    connection.open()
                    print("[Email] Successfully connected to email server")
                    connection.close()
                except Exception as e:
                    print(f"[Email Error] Failed to connect to email server: {str(e)}")
                
                # Generate PDF for customer email attachment
                pdf_content = None
                customer_email = None
                try:
                    if hasattr(loan_application, 'customer') and getattr(loan_application.customer, 'email', None):
                        customer_email = loan_application.customer.email.strip()
                        if customer_email:
                            print("[Email] Generating PDF for customer email attachment...")
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
                            
                            # Prepare context for PDF
                            pdf_context = {
                                'loan_application': loan_application,
                                'customer': loan_application.customer,
                                'agent': loan_application.agent,
                                'loan': loan_application.loan_details.first() if loan_application.loan_details.exists() else None,
                                'generated_date': timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).strftime('%B %d, %Y at %I:%M %p'),
                                'logo_base64': logo_base64,
                            }
                            # Generate HTML content for PDF
                            html_content = render_to_string('loan-disbursed/loan_disbursed_fund_pdf.html', pdf_context)
                            # Generate PDF using the same method as GenerateLoanPDFAPI
                            pdf_content = self._generate_pdf_for_email(html_content)
                            print("[Email] PDF generated successfully for email attachment")
                except Exception as pdf_error:
                    print(f"[Email Error] Failed to generate PDF for email: {str(pdf_error)}")
                    pdf_content = None

                # Send individual emails to each recipient to avoid exposing addresses
                success_count = 0
                for recipient in recipient_list:
                    try:
                        print(f"[Email] Sending to: {recipient}")
                        email = EmailMultiAlternatives(
                            subject=subject,
                            body=message_text,
                            from_email=from_email,
                            to=[recipient],
                            reply_to=[from_email]
                        )
                        if message_html:
                            email.attach_alternative(message_html, "text/html")
                        
                        # Attach PDF only to customer email
                        if recipient == customer_email and pdf_content:
                            filename = f"loan_disbursement_{loan_application.loan_ref_no}.pdf"
                            email.attach(filename, pdf_content, 'application/pdf')
                            print(f"[Email] PDF attached to customer email: {filename}")
                        
                        email.send(fail_silently=False)
                        success_count += 1
                        print(f"[Email] Successfully sent email to: {recipient}")
                    except Exception as send_error:
                        print(f"[Email Error] Failed to send email to {recipient}: {str(send_error)}")
                        import traceback
                        print(traceback.format_exc())
                print(f"[Email] Email send complete. Success: {success_count}/{len(recipient_list)}")
                
            except Exception as e:
                print(f"[Email Error] Unexpected error in email notification: {str(e)}")
                import traceback
                print(traceback.format_exc())
            #--- End Email Notification ---

            # Account-based balances are already updated above via BranchAccount; no wallet_balance field to update
            return Response({
                'success': True,
                'message': 'Loan disbursed successfully - Fund Released',
                'disbursement_id': disbursement_log.dis_id,
                'new_status': loan_application.status
            }, status=status.HTTP_201_CREATED)
            
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            import traceback
            print('DisbursementSubmitAPIView error:', traceback.format_exc())
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _generate_pdf_for_email(self, html_content):
        """Generate PDF for email attachment using the same logic as GenerateLoanPDFAPI"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self._generate_pdf_async(html_content))
            return result
        except Exception as e:
            print(f"Error in _generate_pdf_for_email: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
        finally:
            loop.close()
    
    async def _generate_pdf_async(self, html_content):
        """Generate PDF from HTML content using Playwright"""
        # print("Initializing Playwright...")
        async with async_playwright() as p:
            try:
                browser = None
                # Try launching; if browsers are missing (after Playwright update), install and retry once
                for attempt in (1, 2):
                    try:
                        browser = await p.chromium.launch(headless=True)
                        break
                    except Exception as launch_err:
                        msg = str(launch_err)
                        if attempt == 1 and ("Executable doesn't exist" in msg or 'Playwright was just installed or updated' in msg or 'was just installed or updated' in msg):
                            await self._install_playwright_chromium_for_email()
                            continue
                        raise
                page = await browser.new_page()
                
                # print("Setting HTML content...")
                # Set content and generate PDF
                await page.set_content(html_content)
                
                # print("Waiting for content to load...")
                # Wait for content to load
                await page.wait_for_load_state('networkidle')
                
                # print("Generating PDF...")
                # Generate PDF with proper settings
                pdf_bytes = await page.pdf(
                    format='A4',
                    print_background=True,
                    margin={
                        'top': '20mm',
                        'right': '20mm',
                        'bottom': '20mm',
                        'left': '20mm'
                    }
                )
                
                # print("Closing browser...")
                await browser.close()
                # print(f"PDF generated successfully. Size: {len(pdf_bytes)} bytes")
                return pdf_bytes
            except Exception as e:
                # print(f'PDF generation error: {str(e)}')
                if 'browser' in locals() and browser:
                    # print("Closing browser due to error...")
                    await browser.close()
                raise e 

    async def _install_playwright_chromium_for_email(self):
        """Install Playwright Chromium browser if missing. Runs once when needed."""
        cmd = [sys.executable, '-m', 'playwright', 'install', 'chromium']
        def _run():
            return subprocess.run(cmd, check=True, capture_output=True)
        # Execute in a worker thread to avoid blocking the event loop
        await asyncio.to_thread(_run)


@method_decorator(branch_permission_required('view_loans', 'disburse_loan'), name='dispatch')
class DisbursedFundRelease(TemplateView):
    template_name = 'loan-disbursed/disbursed-fundRelease.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')
        if not logged_user_id:
            context['disbursed_page'] = None
            context['page_links'] = []
            context['query_string'] = ''
            context['disbursed_items'] = []
            return context

        branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        branch = branch_manager.branch

        q = (self.request.GET.get('q') or '').strip()
        agent_id = (self.request.GET.get('agent_id') or '').strip()
        disbursed_from = (self.request.GET.get('disbursed_from') or '').strip()
        disbursed_to = (self.request.GET.get('disbursed_to') or '').strip()

        applications_qs = (
            LoanApplication.objects
            .filter(branch=branch, status='disbursed_fund_released')
            .select_related('customer', 'agent')
            .order_by('-disbursed_at', '-submitted_at')
        )

        if q:
            applications_qs = applications_qs.filter(
                Q(loan_ref_no__icontains=q)
                | Q(customer__customer_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__contact__icontains=q)
                | Q(agent__agent_id__icontains=q)
                | Q(agent__full_name__icontains=q)
            )

        if agent_id:
            applications_qs = applications_qs.filter(agent_id=agent_id)

        if disbursed_from:
            applications_qs = applications_qs.filter(disbursed_at__date__gte=disbursed_from)
        if disbursed_to:
            applications_qs = applications_qs.filter(disbursed_at__date__lte=disbursed_to)

        paginator = Paginator(applications_qs, 10)
        disbursed_page = paginator.get_page(self.request.GET.get('page') or 1)
        try:
            page_links = list(
                paginator.get_elided_page_range(disbursed_page.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            page_links = list(paginator.page_range)

        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        query_string = query_params.urlencode()

        serializer = LoanDisbursedListSerializer(disbursed_page.object_list, many=True)

        context['disbursed_page'] = disbursed_page
        context['page_links'] = page_links
        context['query_string'] = query_string
        context['disbursed_items'] = serializer.data

        context['q'] = q
        context['agents'] = Agent.objects.filter(branch=branch).order_by('full_name')
        context['selected_agent_id'] = agent_id
        context['disbursed_from'] = disbursed_from
        context['disbursed_to'] = disbursed_to
        return context

class DisbursedFundReleaseAPI(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch
            # Fetch loans with status 'disbursed_fund_released' for this branch
            applications = LoanApplication.objects.filter(
                branch=branch, 
                status='disbursed_fund_released'
            ).select_related('customer', 'agent')
            serializer = LoanDisbursedListSerializer(applications, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

########################################################################
#                            Wallet View                               #
########################################################################
@method_decorator(branch_permission_required('view_fund', 'add_fund_record'), name='dispatch')
class WalletView(TemplateView):
    template_name = 'branch-wallet/wallet.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        branch_id = self.request.session.get('logged_user_branch_id')

        date_from = (self.request.GET.get('date_from') or '').strip()
        date_to = (self.request.GET.get('date_to') or '').strip()
        context['date_from'] = date_from
        context['date_to'] = date_to

        filter_type = (self.request.GET.get('type') or '').strip()
        filter_mode = (self.request.GET.get('mode') or '').strip()
        filter_code = (self.request.GET.get('code') or '').strip()
        filter_purpose = (self.request.GET.get('purpose') or '').strip()
        context['filter_type'] = filter_type
        context['filter_mode'] = filter_mode
        context['filter_code'] = filter_code
        context['filter_purpose'] = filter_purpose

        logged_user_id = self.request.session.get('logged_user_id')

        # Get the branch employee
        branch_employee = BranchEmployee.objects.get(
            id=logged_user_id,
            is_active=True
        )

        # Set can_transect based on permissions
        context['can_transect'] = (
            branch_employee.is_manager or 
            branch_employee.has_perm('add_fund_record')
        )

        # Get branch wallet details
        context['wallet'] = Branch.objects.get(branch_id=branch_id)
        
        # Get all transactions (both debit and credit), including those without a disbursement_log
        tx_qs = BranchTransaction.objects.filter(
            branch_id=branch_id
        ).select_related('disbursement_log', 'branch_account').order_by('-transaction_date')

        if date_from:
            tx_qs = tx_qs.filter(transaction_date__date__gte=date_from)
        if date_to:
            tx_qs = tx_qs.filter(transaction_date__date__lte=date_to)

        if filter_type:
            tx_qs = tx_qs.filter(transaction_type__iexact=filter_type)
        if filter_mode:
            tx_qs = tx_qs.filter(mode__iexact=filter_mode)
        if filter_code:
            tx_qs = tx_qs.filter(code=filter_code)
        if filter_purpose:
            tx_qs = tx_qs.filter(purpose=filter_purpose)
        
        context['transactions'] = tx_qs
        context['transactions_debit'] = tx_qs.filter(transaction_type='DEBIT')
        context['transactions_credit'] = tx_qs.filter(transaction_type='CREDIT')
        context['transactions_without_disbursement'] = tx_qs.filter(disbursement_log__isnull=True)
        
        # Fund transfers received by this branch (matched by transfer_to = branch_id)
        # transfer_to is a CharField, so compare using string version of branch_id
        fund_transfers_in = FundTransfers.objects.filter(
            transfer_to=str(branch_id)
        ).order_by('-transfer_date')

        if date_from:
            fund_transfers_in = fund_transfers_in.filter(transfer_date__date__gte=date_from)
        if date_to:
            fund_transfers_in = fund_transfers_in.filter(transfer_date__date__lte=date_to)

        if filter_type and filter_type.upper() == 'DEBIT':
            fund_transfers_in = fund_transfers_in.none()
        if filter_mode:
            fund_transfers_in = fund_transfers_in.filter(payment_mode__iexact=filter_mode)
        if filter_code:
            fund_transfers_in = fund_transfers_in.filter(
                Q(hq_transaction__code=filter_code) | Q(branch_transaction__code=filter_code)
            )
        if filter_purpose:
            if filter_purpose == 'Fund Transfer from HQ':
                fund_transfers_in = fund_transfers_in.filter(Q(purpose__isnull=True) | Q(purpose=''))
            else:
                fund_transfers_in = fund_transfers_in.filter(purpose=filter_purpose)
        
        context['fund_transfers_in'] = fund_transfers_in
        
        # Create a combined list of all transactions sorted by date (most recent first)
        all_combined_transactions = []
        
        # Add branch transactions
        for tx in tx_qs:
            # Get account details from branch_account relationship
            account_name = ""
            account_number = ""
            bank_name = ""
            
            if tx.branch_account:
                account_name = tx.branch_account.name
                account_number = tx.branch_account.account_number
                bank_name = tx.branch_account.bank_name

            all_combined_transactions.append({
                'type': 'branch_transaction',
                'object': tx,
                'date': tx.transaction_date,
                'transaction_type': tx.transaction_type,
                'amount': tx.amount,
                'purpose': tx.purpose,
                'code': tx.code,
                'description': tx.description,
                'id': tx.transaction_id,
                'account_name': account_name,
                'account_number': account_number,
                'bank_name': bank_name,
                'payment_mode': tx.mode,
            })
        
        # Add fund transfers
        for ft in fund_transfers_in:
            # Try to get linked branch account details (if the HQ->Branch transfer created a BranchTransaction)
            ft_account_name = ""
            ft_account_number = ""
            ft_bank_name = ""
            try:
                if ft.branch_transaction and ft.branch_transaction.branch_account:
                    acc = ft.branch_transaction.branch_account
                    ft_account_name = acc.name or ""
                    ft_account_number = acc.account_number or ""
                    ft_bank_name = acc.bank_name or ""
                elif getattr(ft, 'branch_account', None):
                    acc = ft.branch_account
                    ft_account_name = getattr(acc, 'name', "") or ""
                    ft_account_number = getattr(acc, 'account_number', "") or ""
                    ft_bank_name = getattr(acc, 'bank_name', "") or ""
            except Exception:
                # Be defensive: if relationships are missing, leave fields blank
                pass

            all_combined_transactions.append({
                'type': 'fund_transfer',
                'object': ft,
                'date': ft.transfer_date,
                'transaction_type': 'CREDIT',  # Fund transfers are always credits
                'amount': ft.amount,
                'purpose': ft.purpose or 'Fund Transfer from HQ',
                'code': ft.hq_transaction.code if ft.hq_transaction and ft.hq_transaction.code else '',
                'payment_mode': ft.payment_mode if ft.payment_mode else '',
                'description': ft.hq_transaction.description if ft.hq_transaction else ft.branch_transaction.description if ft.branch_transaction else '',
                'id': ft.transfer_id,
                'account_name': ft_account_name,
                'account_number': ft_account_number,
                'bank_name': ft_bank_name,
            })
        
        # Sort all transactions by date (most recent first)
        all_combined_transactions.sort(key=lambda x: x['date'], reverse=True)
        page_number = self.request.GET.get('page', 1)
        paginator = Paginator(all_combined_transactions, 15)
        try:
            page_obj = paginator.get_page(page_number)
        except EmptyPage:
            page_obj = paginator.get_page(1)

        querydict = self.request.GET.copy()
        querydict.pop('page', None)

        context['all_combined_transactions'] = all_combined_transactions
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['is_paginated'] = paginator.num_pages > 1
        context['querystring'] = querydict.urlencode()

        total_pages = paginator.num_pages
        current_page = page_obj.number
        pagination_links = []
        if total_pages >= 1:
            pagination_links.extend([1])
        if total_pages >= 2:
            pagination_links.extend([2])
        if total_pages >= 3:
            pagination_links.extend([3])

        window_start = max(4, current_page - 1)
        window_end = min(total_pages - 1, current_page + 1)

        if window_start > 4:
            pagination_links.append(None)
        if window_start <= window_end:
            pagination_links.extend(list(range(window_start, window_end + 1)))
        if window_end < total_pages - 1:
            pagination_links.append(None)

        if total_pages > 3:
            pagination_links.append(total_pages)

        seen = set()
        compact_links = []
        for p in pagination_links:
            if p is None:
                if not compact_links or compact_links[-1] is None:
                    continue
                compact_links.append(None)
            else:
                if p < 1 or p > total_pages or p in seen:
                    continue
                seen.add(p)
                compact_links.append(p)

        context['pagination_links'] = compact_links
        
        # Get all disbursement logs for the branch with related loan and transaction info
        from loan.models import DisbursementLog
        context['disbursement_logs'] = DisbursementLog.objects.filter(
            disbursed_by_id=branch_id
        ).select_related(
            'loan_id__customer',  # Get customer details
            'loan_id__agent'      # Get agent details
        ).prefetch_related(
            'branch_transactions'  # Get related transactions using the correct related_name
        ).order_by('-created_at')    # Latest first
        
        # Calculate monthly expenses (debits) from disbursement logs
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        monthly_disbursements = DisbursementLog.objects.filter(
            disbursed_by_id=branch_id,
            created_at__gte=first_day_of_month
        )
        context['monthly_expenses'] = sum(
            log.net_amount_cust for log in monthly_disbursements
        )
        
        # Get Chart of Accounts for the purpose dropdown
        from loan.models import ChartOfAccount
        context['chart_of_accounts'] = ChartOfAccount.objects.all().order_by('main_type', 'sl_no', 'head_of_account')
        context['hq_wallets'] = HeadquartersWallet.objects.all().order_by('type', 'bank_name', 'account_number')
        context['accounts'] = BranchAccount.objects.filter(branch_id=branch_id, type='BANK').order_by('account_number', 'bank_name')
        context['branch_employees'] = BranchEmployee.objects.filter(branch_id=branch_id).order_by('employee_id')
        context['total_cash'] = BranchAccount.objects.filter(branch_id=branch_id, type='CASH').aggregate(total_cash=Sum('current_balance'))['total_cash'] or Decimal('0.00')
        context['total_bank'] = BranchAccount.objects.filter(branch_id=branch_id, type='BANK').aggregate(total_bank=Sum('current_balance'))['total_bank'] or Decimal('0.00')
        context['total_balance'] = context['total_cash'] + context['total_bank']

        return context

class MoneyTransferToHQAPI(APIView):
    def post(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            # Fetch branch and inputs
            branch_employee = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_employee.branch
            
            data = request.data if hasattr(request, 'data') else request.POST
            # Expect amount, mode, reference, note
            amount_raw = data.get('amount')
            payment_mode = data.get('payment_mode')
            bank_payment_method = data.get('bank_payment_method')
            account_number = data.get('account_number')
            account_id = data.get('account_id')
            purpose_id = data.get('purpose')
            note = (data.get('note') or '').strip()

            if amount_raw is None or str(amount_raw).strip() == '':
                return Response({'detail': 'Amount is required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                amount = Decimal(str(amount_raw)).quantize(Decimal('0.01'))
            except Exception:
                return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)
            if amount <= Decimal('0.00'):
                return Response({'detail': 'Amount must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate purpose (Chart of Account)
            if not purpose_id:
                return Response({'detail': 'Purpose is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if not payment_mode:
                return Response({'detail': 'Payment mode is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if payment_mode == 'bank':
                if not bank_payment_method or not account_number or not account_id:
                    return Response({'detail': 'Bank payment method is required.'}, status=status.HTTP_400_BAD_REQUEST)

            if payment_mode == 'bank':
                if not account_number:
                    return Response({'detail': 'Account number is required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                from loan.models import ChartOfAccount
                purpose_account = ChartOfAccount.objects.get(id=purpose_id)
            except ChartOfAccount.DoesNotExist:
                return Response({'detail': 'Invalid purpose selected.'}, status=status.HTTP_400_BAD_REQUEST)

            # Balance check and create transaction atomically
            with transaction.atomic():
                branch.refresh_from_db()

                if payment_mode == 'cash':
                    # Check cash account balance
                    try:
                        cash_account = BranchAccount.objects.get(branch=branch, type='CASH')
                        if cash_account.current_balance < amount:
                            return Response({
                                'detail': f'Insufficient cash balance. Available: ₹{cash_account.current_balance:.2f}'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Deduct from cash account
                        cash_account.current_balance = (Decimal(cash_account.current_balance) - amount).quantize(Decimal('0.01'))
                        cash_account.save(update_fields=['current_balance', 'updated_at'])
                        # Track selected account for transaction linking
                        selected_account = cash_account
                        
                    except BranchAccount.DoesNotExist:
                        return Response({'detail': 'Cash account not found for this branch.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                elif payment_mode == 'bank':
                    if not bank_payment_method or not account_number or not account_id:
                        return Response({'detail': 'Bank payment method, account number, and account ID are required.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Check specific bank account balance
                    try:
                        bank_account = BranchAccount.objects.get(id=account_id, branch=branch, type='BANK', account_number=account_number)
                        if bank_account.current_balance < amount:
                            return Response({
                                'detail': f'Insufficient bank balance in {bank_account.bank_name} ({bank_account.account_number}). Available: ₹{bank_account.current_balance:.2f}'
                            }, status=status.HTTP_400_BAD_REQUEST)
                        
                        # Deduct from bank account
                        bank_account.current_balance = (Decimal(bank_account.current_balance) - amount).quantize(Decimal('0.01'))
                        bank_account.save(update_fields=['current_balance', 'updated_at'])
                        # Track selected account for transaction linking
                        selected_account = bank_account
                        
                    except BranchAccount.DoesNotExist:
                        return Response({'detail': 'Bank account not found or does not belong to this branch.'}, status=status.HTTP_404_NOT_FOUND)
                else:
                    return Response({'detail': 'Invalid payment mode.'}, status=status.HTTP_400_BAD_REQUEST)

                # Create BranchTransaction as DEBIT with purpose OTHER and description
                bt = BranchTransaction.objects.create(
                    branch=branch,
                    branch_account=selected_account if 'selected_account' in locals() else None,
                    disbursement_log=None,
                    mode=payment_mode,
                    bank_payment_method=bank_payment_method,
                    transaction_type='DEBIT',
                    purpose=purpose_account.head_of_account,
                    code=purpose_account.code,
                    amount=amount,
                    description=f"{purpose_account.head_of_account} - " + (note or 'Transfer to Headquarters'),
                    transfer_to_from='Headquarters',
                    created_by=branch_employee,
                )

                # Note: Branch.wallet_balance field removed. Using account-based balances only.
                account_balance_after = selected_account.current_balance

                # Credit HQ wallet and create HQ transaction
                hq_wallet = HeadquartersWallet.objects.first()
                if not hq_wallet:
                    hq_wallet = HeadquartersWallet.objects.create()

                source_map = {
                    'Bank Transfer': 'bank_transfer',
                    'UPI': 'upi',
                    'Cheque': 'cheque',
                    'Cash': 'cash',
                }
                hq_tx = HeadquartersTransactions.objects.create(
                    wallet=hq_wallet,
                    transaction_type='credit',
                    amount=amount,
                    description=f"Transfer from {branch.branch_name}: {purpose_account.head_of_account} - " + (note or ''),
                    purpose=purpose_account.head_of_account,
                    code=purpose_account.code,
                    # source=source_map.get(payment_mode, 'other'),
                    reference_number=None,
                    created_by=None,
                )

                # Update HQ wallet balance
                hq_wallet.balance = (Decimal(hq_wallet.balance) + amount).quantize(Decimal('0.01'))
                hq_wallet.save(update_fields=['balance', 'last_updated'])

                # Link both via FundTransfers
                ft = FundTransfers.objects.create(
                    hq_transaction=hq_tx,
                    branch_transaction=bt,
                    # transfer_to= 
                    amount=amount,
                    purpose=f'{purpose_account.head_of_account} - Transfer to HQ from {branch.branch_name}',
                    created_by=branch_employee,
                )

            return Response({
                'success': True,
                'message': 'Money transferred to HQ successfully.',
                'transaction_id': bt.transaction_id,
                'hq_transaction_id': hq_tx.transaction_id,
                'transfer_id': ft.transfer_id,
                'account_balance': str(account_balance_after),
            }, status=status.HTTP_200_OK)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class MoneyTransfer(APIView):
    def post(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_employee.branch
            
            data = request.data if hasattr(request, 'data') else request.POST

            transaction_type = data.get('transaction_type')
            amount = data.get('amount')
            purpose = data.get('purpose')
            transfer_to_from = data.get('transfer_to_from')
            note = data.get('note')
            payment_mode = data.get('paymentMode')
            bank_payment_method = data.get('bankPaymentMethod')
            account_id = data.get('account_id')
            
            if amount is None or str(amount).strip() == '':
                return Response({'detail': 'Amount is required.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                amount = Decimal(str(amount)).quantize(Decimal('0.01'))
            except Exception:
                return Response({'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)
            if amount <= Decimal('0.00'):
                return Response({'detail': 'Amount must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if purpose is None or str(purpose).strip() == '':
                return Response({'detail': 'Purpose is required.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                purpose_account = ChartOfAccount.objects.get(id=purpose)
            except ChartOfAccount.DoesNotExist:
                return Response({'detail': 'Invalid purpose selected.'}, status=status.HTTP_400_BAD_REQUEST)

            if transfer_to_from is None or str(transfer_to_from).strip() == '':
                return Response({'detail': 'Transfer to/from is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if transaction_type is None or str(transaction_type).strip() == '':
                return Response({'detail': 'Transaction type is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            if transaction_type not in ['debit', 'credit']:
                return Response({'detail': 'Invalid transaction type.'}, status=status.HTTP_400_BAD_REQUEST)

            if not payment_mode:
                return Response({'detail': 'Payment mode is required.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Only require bank_payment_method for bank transactions
            if payment_mode.lower() == 'bank' and not bank_payment_method:
                return Response({'detail': 'Bank payment method is required for bank transactions.'}, status=status.HTTP_400_BAD_REQUEST)
            
            with transaction.atomic():
                # --- Handle Cash or Bank Transactions with Account-based Validation ---
                if payment_mode.lower() == 'cash':
                    # Use existing cash account only; do not auto-create a new one
                    try:
                        cash_account = BranchAccount.objects.get(
                            branch=branch,
                            type='CASH',
                            # account_number='CASH',
                        )
                    except BranchAccount.DoesNotExist:
                        return Response(
                            {
                                'detail': 'Cash account not found for this branch. Please create a cash account before recording cash transactions.'
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    branch_account = cash_account

                    # Validate cash account balance for debit transactions
                    if transaction_type == 'debit' and cash_account.current_balance < amount:
                        return Response({
                            'detail': f'Insufficient cash balance. Available: ₹{cash_account.current_balance:.2f}'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # Update cash account balance
                    if transaction_type == 'credit':
                        cash_account.current_balance = (cash_account.current_balance + amount).quantize(Decimal('0.01'))
                    elif transaction_type == 'debit':
                        cash_account.current_balance = (cash_account.current_balance - amount).quantize(Decimal('0.01'))
                    
                    cash_account.updated_by = branch_employee
                    cash_account.save(update_fields=['current_balance', 'updated_at', 'updated_by'])

                elif payment_mode.lower() == 'bank':
                    if not account_id:
                        return Response({'detail': 'Account ID required for bank transaction.'}, status=status.HTTP_400_BAD_REQUEST)
                    
                    try:
                        bank_account = BranchAccount.objects.get(id=account_id, type='BANK', branch=branch)
                    except BranchAccount.DoesNotExist:
                        return Response({'detail': 'Bank account not found.'}, status=status.HTTP_404_NOT_FOUND)

                    branch_account = bank_account

                    # Validate bank account balance for debit transactions
                    if transaction_type == 'debit' and bank_account.current_balance < amount:
                        return Response({
                            'detail': f'Insufficient bank balance in {bank_account.bank_name} ({bank_account.account_number}). Available: ₹{bank_account.current_balance:.2f}'
                        }, status=status.HTTP_400_BAD_REQUEST)

                    # Update bank account balance
                    if transaction_type == 'debit':
                        bank_account.current_balance = (bank_account.current_balance - amount).quantize(Decimal('0.01'))
                    elif transaction_type == 'credit':
                        bank_account.current_balance = (bank_account.current_balance + amount).quantize(Decimal('0.01'))

                    bank_account.updated_by = branch_employee
                    bank_account.save(update_fields=['current_balance', 'updated_at', 'updated_by'])

                    # If this is a Cash in Hand (code 140) debit from bank,
                    # also credit the logged-in branch's cash account.
                    if (
                        transaction_type == 'debit'
                        and str(getattr(purpose_account, 'code', '')) == '140'
                    ):
                        try:
                            cash_account = BranchAccount.objects.get(
                                branch=branch,
                                type='CASH',
                            )
                        except BranchAccount.DoesNotExist:
                            return Response(
                                {
                                    'detail': 'Cash account not found for this branch. Please create a cash account before using Cash in Hand (code 140).'
                                },
                                status=status.HTTP_400_BAD_REQUEST,
                            )

                        cash_account.current_balance = (
                            cash_account.current_balance + amount
                        ).quantize(Decimal('0.01'))
                        cash_account.updated_by = branch_employee
                        cash_account.save(update_fields=['current_balance', 'updated_at', 'updated_by'])

                        # Create a separate BranchTransaction entry for the cash side
                        BranchTransaction.objects.create(
                            branch=branch,
                            branch_account=cash_account,
                            transaction_type='CREDIT',
                            amount=amount,
                            purpose=purpose_account.head_of_account,
                            code=purpose_account.code,
                            mode='cash',
                            bank_payment_method=None,
                            transfer_to_from=transfer_to_from,
                            description=f"{purpose_account.head_of_account} - Cash received from bank (internal transfer)",
                            created_by=branch_employee,
                        )

                else:
                    return Response({'detail': 'Invalid payment mode.'}, status=status.HTTP_400_BAD_REQUEST)

                # Create BranchTransaction record
                branch_transaction = BranchTransaction.objects.create(
                    branch=branch,
                    branch_account=branch_account,
                    transaction_type=transaction_type.upper(),  # Convert to uppercase for consistency
                    amount=amount,
                    purpose=purpose_account.head_of_account,
                    code=purpose_account.code,
                    mode=payment_mode,
                    bank_payment_method=bank_payment_method,
                    transfer_to_from=transfer_to_from,
                    description=f"{purpose_account.head_of_account} - " + (note or ''),
                    created_by=branch_employee,
                )
                
                # Note: Branch.wallet_balance removed; balances are account-based.
                account_balance_after = branch_account.current_balance

            return Response({
                'success': True,
                'message': 'Transaction successful.',
                'account_balance': str(account_balance_after),

                'transaction_id': branch_transaction.transaction_id,
            }, status=status.HTTP_200_OK)
            
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                

########################################################################
#               for generated pdf report of fund release               #
########################################################################
class GenerateLoanPDFAPI(APIView):
    """Generate PDF for loan disbursement report using Playwright"""
    
    def post(self, request, *args, **kwargs):
        try:
            # Get loan data from request
            loan_ref_no = request.data.get('loan_ref_no')
            if not loan_ref_no:
                return Response({'error': 'Loan reference number is required'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Fetch loan data
            try:
                loan_application = LoanApplication.objects.get(loan_ref_no=loan_ref_no)
            except LoanApplication.DoesNotExist:
                return Response({'error': 'Loan application not found'}, status=status.HTTP_404_NOT_FOUND)
            
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
            
            # Prepare context data for PDF
            context = {
                'loan_application': loan_application,
                'customer': loan_application.customer,
                'agent': loan_application.agent,
                'loan': loan_application.loan_details.first() if loan_application.loan_details.exists() else None,
                'generated_date': timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).strftime('%B %d, %Y at %I:%M %p'),
                'logo_base64': logo_base64,
            }
            
            # Generate HTML content
            # html_content = render_to_string('branch/loan_pdf_template.html', context)
            html_content = render_to_string('loan-disbursed/loan_disbursed_fund_pdf.html', context)
            
            # Generate PDF using Playwright in a separate thread
            pdf_content = self._generate_pdf_sync(html_content)
            
            # Return PDF as response
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="loan_report_{loan_ref_no}.pdf"'
            return response
            
        except Exception as e:
            # print(f'GenerateLoanPDFAPI error: {str(e)}')
            import traceback
            traceback.print_exc()
            return Response({'error': 'Failed to generate PDF'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _generate_pdf_sync(self, html_content):
        """Synchronous wrapper for PDF generation"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # print("Starting PDF generation...")
            result = loop.run_until_complete(self._generate_pdf(html_content))
            # print(f"PDF generation completed. Size: {len(result)} bytes")
            return result
        except Exception as e:
            # print(f"Error in _generate_pdf_sync: {str(e)}")
            import traceback
            traceback.print_exc()
            raise e
        finally:
            loop.close()
    
    async def _generate_pdf(self, html_content):
        """Generate PDF from HTML content using Playwright"""
        # print("Initializing Playwright...")
        async with async_playwright() as p:
            try:
                # print("Launching Chromium browser...")
                # Launch browser with headless mode
                browser = None
                # Try launching; if browsers are missing (after Playwright update), install and retry once
                for attempt in (1, 2):
                    try:
                        browser = await p.chromium.launch(headless=True)
                        break
                    except Exception as launch_err:
                        msg = str(launch_err)
                        if attempt == 1 and ("Executable doesn't exist" in msg or 'Playwright was just installed or updated' in msg or 'was just installed or updated' in msg):
                            await self._install_playwright_chromium()
                            continue
                        raise
                page = await browser.new_page()
                
                # print("Setting HTML content...")
                # Set content and generate PDF
                await page.set_content(html_content)
                
                # print("Waiting for content to load...")
                # Wait for content to load
                await page.wait_for_load_state('networkidle')
                
                # print("Generating PDF...")
                # Generate PDF with proper settings
                pdf_bytes = await page.pdf(
                    format='A4',
                    print_background=True,
                    margin={
                        'top': '20mm',
                        'right': '20mm',
                        'bottom': '20mm',
                        'left': '20mm'
                    }
                )
                
                # print("Closing browser...")
                await browser.close()
                # print(f"PDF generated successfully. Size: {len(pdf_bytes)} bytes")
                return pdf_bytes
            except Exception as e:
                # print(f'PDF generation error: {str(e)}')
                if 'browser' in locals() and browser:
                    # print("Closing browser due to error...")
                    await browser.close()
                raise e 

    async def _install_playwright_chromium(self):
        """Install Playwright Chromium browser if missing. Runs once when needed."""
        cmd = [sys.executable, '-m', 'playwright', 'install', 'chromium']
        def _run():
            return subprocess.run(cmd, check=True, capture_output=True)
        # Execute in a worker thread to avoid blocking the event loop
        await asyncio.to_thread(_run)


# for repayment #
@method_decorator(branch_permission_required('view_emis'), name='dispatch')
class RepaymentView(TemplateView):
    template_name = 'loanPaymentAndCollection/emi-payment.html'

    def _build_emi_payment_loan_list(self, branch):
        applications = (
            LoanApplication.objects
            .filter(branch=branch, status='disbursed_fund_released')
            .select_related('customer', 'agent')
            .prefetch_related('loan_details')
            .order_by('-disbursed_at', '-submitted_at')
        )

        unpaid_refs = set(
            LoanEMISchedule.objects
            .filter(loan_application__in=applications, paid=False)
            .values_list('loan_application__loan_ref_no', flat=True)
            .distinct()
        )

        approved_close_refs = set(
            LoanCloseRequest.objects
            .filter(loan_application__in=applications, status='approved')
            .values_list('loan_application__loan_ref_no', flat=True)
            .distinct()
        )

        loan_list = []
        for app in applications:
            base_has_unpaid = app.loan_ref_no in unpaid_refs

            latest_reschedule_log = (
                LoanRescheduleLog.objects
                .filter(loan_application=app)
                .order_by('-created_at')
                .first()
            )
            if latest_reschedule_log is not None:
                res_qs = LoanEMIReschedule.objects.filter(reschedule_log=latest_reschedule_log)
                if res_qs.exists():
                    has_unpaid = res_qs.filter(paid=False).exists()
                else:
                    has_unpaid = base_has_unpaid
            else:
                has_unpaid = base_has_unpaid

            has_approved_close = app.loan_ref_no in approved_close_refs
            if (not has_unpaid) and has_approved_close:
                continue

            loan_detail = app.loan_details.first() if hasattr(app, 'loan_details') else None
            loan_list.append({
                'loan_ref_no': app.loan_ref_no,
                'customer_name': app.customer.full_name if app.customer else 'N/A',
                'disbursed_date': app.disbursed_at.strftime('%Y-%m-%d') if getattr(app, 'disbursed_at', None) else 'N/A',
                'loan_amount': str(getattr(loan_detail, 'loan_amount', '0.00')) if loan_detail else '0.00',
                'all_emi_paid': not has_unpaid,
            })

        return loan_list

    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return redirect('/branch/login/?next=' + request.path)

        try:
            employee = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            request.session.flush()
            return redirect('/branch/login/?next=' + request.path)

        loan_list = self._build_emi_payment_loan_list(employee.branch)
        paginator = Paginator(loan_list, 10)
        try:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages) if paginator.num_pages else []

        context = self.get_context_data(**kwargs)
        context['loans_page'] = page_obj
        context['has_next'] = bool(getattr(page_obj, 'has_next', lambda: False)())
        return self.render_to_response(context)


@method_decorator(branch_permission_required('view_emis'), name='dispatch')
class EmiPaymentRowsView(TemplateView):
    template_name = 'loanPaymentAndCollection/partials/_emi-payment-rows.html'

    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return HttpResponse('', status=403)

        try:
            employee = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            return HttpResponse('', status=403)

        page = request.GET.get('page', '1')
        try:
            page_num = int(page)
        except (TypeError, ValueError):
            page_num = 1

        loan_list = RepaymentView()._build_emi_payment_loan_list(employee.branch)
        paginator = Paginator(loan_list, 10)
        try:
            page_obj = paginator.page(page_num)
        except EmptyPage:
            return HttpResponse('')

        html = render_to_string(self.template_name, {'loans': page_obj.object_list}, request=request)
        return HttpResponse(html)


@method_decorator(branch_permission_required('view_emis', 'collect_emi', 'receive_emi', 'reject_emi'), name='dispatch')
class EmiScheduleView(TemplateView):
    template_name = 'loanPaymentAndCollection/emi-scedule.html'


class EmiStatementAPIView(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        loan_ref_no = request.query_params.get('loan_ref_no')
        
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            employee = BranchEmployee.objects.get(id=logged_user_id)
            branch = employee.branch
            
            # Check permissions
            permissions = {
                'can_view_emis': employee.is_manager or employee.has_perm('view_emis'),
                'can_collect_emi': employee.is_manager or employee.has_perm('collect_emi'),
                'can_receive_emi': employee.is_manager or employee.has_perm('receive_emi'),
                'can_reject_emi': employee.is_manager or employee.has_perm('reject_emi')
            }

            # If loan_ref_no is provided, return EMI schedules for that loan
            if loan_ref_no:
                try:
                    loan = LoanApplication.objects.get(
                        loan_ref_no=loan_ref_no,
                        branch=branch,
                        status='disbursed_fund_released'
                    )
                    agent_list = Agent.objects.filter(branch=branch)
                    agent_list = AgentSerializer(agent_list, many=True).data
                    emi_schedules = LoanEMISchedule.objects.filter(
                        loan_application=loan
                    ).order_by('installment_date')
                    serializer = LoanEMIScheduleSerializer(emi_schedules, many=True)

                    # Attach per-EMI latest collected amount (agent or branch)
                    # Uses EmiCollectionDetail.collected=True as the authoritative latest collection per EMI.
                    collected_rows = (
                        EmiCollectionDetail.objects
                        .filter(emi__in=emi_schedules, collected=True)
                        .values('emi_id', 'amount_received', 'collected_by_agent_id', 'collected_by_branch_id')
                    )
                    collected_map = {
                        str(r['emi_id']): {
                            'amount_received': r.get('amount_received'),
                            'collected_by_agent_id': r.get('collected_by_agent_id'),
                            'collected_by_branch_id': r.get('collected_by_branch_id'),
                        }
                        for r in collected_rows
                    }

                    schedules_data = list(serializer.data)
                    for row in schedules_data:
                        emi_id = str(row.get('id'))
                        coll = collected_map.get(emi_id)
                        if coll and coll.get('amount_received') is not None:
                            row['collected_amount'] = str(coll.get('amount_received'))
                            row['collected_by'] = 'agent' if coll.get('collected_by_agent_id') else 'branch'
                        else:
                            row['collected_amount'] = None
                            row['collected_by'] = None
                    
                    # Add agent details if loan was created by an agent
                    agent_details = None
                    if loan.agent:
                        agent_details = AgentSerializer(loan.agent).data

                    # Flag: all EMIs paid for this loan
                    all_paid = not LoanEMISchedule.objects.filter(loan_application=loan, paid=False).exists()

                    # Extra metadata for reschedule logic
                    first_emi = emi_schedules.first()
                    last_emi = emi_schedules.last()
                    frequency = first_emi.frequency if first_emi else None

                    latest_period = LoanPeriod.objects.filter(loan_application=loan).order_by('-created_at').first()
                    reschedule_count = latest_period.reschedule_count if latest_period else 0

                    # Outstanding = unpaid EMI + unpaid late fee
                    unpaid_qs = emi_schedules.filter(paid=False)
                    outstanding = unpaid_qs.aggregate(
                        total=Sum('installment_amount') + Sum('late_fee')
                    )['total'] or Decimal('0.00')

                    remaining_balance = (
                        latest_period.remaining_balance
                        if latest_period and latest_period.remaining_balance is not None
                        else outstanding
                    )

                    return Response({
                        'loan_ref_no': loan_ref_no,
                        'customer_name': (getattr(getattr(loan, 'customer', None), 'full_name', None) or ''),
                        'schedules': schedules_data,
                        'agent_list': agent_list,
                        'agent_details': agent_details,
                        'all_emi_paid': all_paid,
                        'frequency': frequency,
                        'last_installment_date': last_emi.installment_date if last_emi else None,
                        'remaining_balance': str(remaining_balance),
                        'reschedule_count': reschedule_count,
                        'permissions': permissions
                    }, status=status.HTTP_200_OK)
                    
                except LoanApplication.DoesNotExist:
                    return Response(
                        {'detail': 'Loan not found or not eligible for EMI.'}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
            
            # If no loan_ref_no, return loans eligible for EMI with related data
            applications = (
                LoanApplication.objects
                .filter(branch=branch, status='disbursed_fund_released')
                .select_related('customer', 'agent')
                .prefetch_related('loan_details')
            )

            # Build a set of loans that still have unpaid EMIs
            unpaid_refs = set(
                LoanEMISchedule.objects
                .filter(loan_application__in=applications, paid=False)
                .values_list('loan_application__loan_ref_no', flat=True)
                .distinct()
            )

            # Build a set of loans that have an approved close request
            approved_close_refs = set(
                LoanCloseRequest.objects
                .filter(loan_application__in=applications, status='approved')
                .values_list('loan_application__loan_ref_no', flat=True)
                .distinct()
            )
            
            # Prepare loan list with all required details
            loan_list = []
            for app in applications:
                # Default unpaid flag from original EMI schedule
                base_has_unpaid = app.loan_ref_no in unpaid_refs

                # If there is a reschedule plan with snapshot EMIs,
                # determine unpaid status from the latest reschedule set instead.
                latest_reschedule_log = (
                    LoanRescheduleLog.objects
                    .filter(loan_application=app)
                    .order_by('-created_at')
                    .first()
                )
                if latest_reschedule_log is not None:
                    res_qs = LoanEMIReschedule.objects.filter(reschedule_log=latest_reschedule_log)
                    if res_qs.exists():
                        has_unpaid_reschedule = res_qs.filter(paid=False).exists()
                        has_unpaid = has_unpaid_reschedule
                    else:
                        has_unpaid = base_has_unpaid
                else:
                    has_unpaid = base_has_unpaid

                has_approved_close = app.loan_ref_no in approved_close_refs

                # Exclude loans whose EMIs (original or rescheduled) are fully paid
                # AND have an approved close request
                if (not has_unpaid) and has_approved_close:
                    continue

                loan_detail = app.loan_details.first() if hasattr(app, 'loan_details') else None
                loan_data = {
                    'loan_ref_no': app.loan_ref_no,
                    'customer_name': app.customer.full_name if app.customer else 'N/A',
                    'disbursed_date': app.disbursed_at.strftime('%Y-%m-%d') if getattr(app, 'disbursed_at', None) else 'N/A',
                    'loan_amount': str(getattr(loan_detail, 'loan_amount', '0.00')) if loan_detail else '0.00',
                    # True only when all EMIs (original or rescheduled) are paid
                    # and there is NO approved close request
                    'all_emi_paid': not has_unpaid,
                }
                
                # Add agent details if application was created by an agent
                if app.agent:
                    loan_data['agent_details'] = AgentSerializer(app.agent).data
                    
                loan_list.append(loan_data)
            
            return Response(loan_list, status=status.HTTP_200_OK)
            
        except BranchEmployee.DoesNotExist:
            return Response(
                {'detail': 'Branch manager not found.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'detail': 'An error occurred while processing your request.', 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class RescheduleEmiCollectedAPIView(APIView):
    """Branch-side collection API for RESCHEDULED EMIs.

    Creates EmiCollectionDetail rows linked to LoanEMIReschedule via reschedule_emi
    without touching the existing EmiCollectedAPIView logic for original EMIs.
    """

    def post(self, request, *args, **kwargs):
        branch_manager_id = request.session.get('logged_user_id')
        if not branch_manager_id:
            return Response({'success': False, 'message': 'Branch manager authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data or {}
        reschedule_emi_id = data.get('reschedule_emi_id')
        loan_ref_no = data.get('loan_ref_no')

        if not reschedule_emi_id or not loan_ref_no:
            return Response({'success': False, 'message': 'reschedule_emi_id and loan_ref_no are required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            branch_manager = BranchEmployee.objects.select_related('branch').get(id=branch_manager_id)
        except BranchEmployee.DoesNotExist:
            return Response({'success': False, 'message': 'Branch manager not found in session'}, status=status.HTTP_403_FORBIDDEN)

        # Resolve the rescheduled EMI and ensure it belongs to this branch and loan
        try:
            res_emi = (
                LoanEMIReschedule.objects
                .select_related('loan_application__branch')
                .get(id=reschedule_emi_id, loan_application__loan_ref_no=loan_ref_no)
            )
        except LoanEMIReschedule.DoesNotExist:
            return Response({'success': False, 'message': 'Rescheduled EMI not found for this loan.'}, status=status.HTTP_404_NOT_FOUND)

        if getattr(res_emi.loan_application, 'branch', None) != branch_manager.branch:
            return Response({'success': False, 'message': 'Rescheduled EMI does not belong to your branch.'}, status=status.HTTP_403_FORBIDDEN)

        # Amounts: keep it simple and rely on client-sent values, defaulting to schedule amounts
        def d2(val, default):
            if val in (None, '', 'null'):
                val = default
            try:
                d = Decimal(str(val))
            except Exception:
                d = Decimal(str(default or 0))
            return d.quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

        default_amount = getattr(res_emi, 'installment_amount', Decimal('0'))
        default_principal = getattr(res_emi, 'principal_amount', Decimal('0'))
        default_interest = getattr(res_emi, 'interest_amount', Decimal('0'))

        amount_received = d2(data.get('amount_received'), default_amount)
        principal_received = d2(data.get('principal_received'), default_principal)
        interest_received = d2(data.get('interest_received'), default_interest)
        penalty_received = d2(data.get('penalty_received'), 0)
        payment_mode = data.get('payment_mode') or 'Cash'
        payment_reference = data.get('payment_reference')
        remarks = data.get('remarks')

        try:
            with transaction.atomic():
                collected = EmiCollectionDetail(
                    assignment=None,
                    emi=None,
                    reschedule_emi=res_emi,
                    loan_application=res_emi.loan_application,
                    amount_received=amount_received,
                    principal_received=principal_received,
                    interest_received=interest_received,
                    penalty_received=penalty_received,
                    payment_mode=payment_mode,
                    payment_reference=payment_reference,
                    remarks=remarks,
                    status='collected',
                    collected=True,
                    collected_by_branch=branch_manager,
                )
                collected.save()

                # Ensure only this record is marked collected=True for this rescheduled EMI
                EmiCollectionDetail.objects.filter(reschedule_emi=res_emi).exclude(collected_id=collected.collected_id).update(collected=False)

        except Exception as e:
            return Response({'success': False, 'message': f'Failed to save rescheduled EMI collection: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': True,
            'collected_id': collected.collected_id,
            'reschedule_emi_id': res_emi.id,
            'status': collected.status,
        }, status=status.HTTP_201_CREATED)


class LoanRescheduleAPIView(APIView):
    """Reschedule a loan from branch EMI schedule page.

    Uses session.logged_user_id to identify the BranchEmployee and
    delegates to loan.services.reschedule.reschedule_loan_for_branch.
    """

    def post(self, request, loan_ref_no, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = request.data or {}
        penalty_rate = data.get('penalty_rate')
        reschedule_length = data.get('reschedule_length')
        remarks = data.get('remarks', '')

        try:
            result = reschedule_loan_for_branch(
                loan_ref_no=loan_ref_no,
                branch_employee=branch_employee,
                penalty_rate=penalty_rate,
                reschedule_length=reschedule_length,
                remarks=remarks,
            )
            return Response(result, status=status.HTTP_200_OK)
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Loan not found.'}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'detail': 'Unexpected error while rescheduling loan.', 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoanRescheduleEmiListAPIView(APIView):
    """Return the latest rescheduled EMI list for a loan.

    Used by branch EMI schedule page to display the new reschedule EMI table
    without affecting the existing LoanEMISchedule-based logic.
    """

    def get(self, request, loan_ref_no, *args, **kwargs):
        try:
            loan = LoanApplication.objects.get(loan_ref_no=loan_ref_no)
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Loan not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Find the most recent reschedule log that actually has snapshot EMIs
        logs_qs = LoanRescheduleLog.objects.filter(loan_application=loan).order_by('-created_at')
        log = None
        emis = LoanEMIReschedule.objects.none()

        for candidate in logs_qs:
            qs = LoanEMIReschedule.objects.filter(reschedule_log=candidate).order_by('installment_date')
            if qs.exists():
                log = candidate
                emis = qs
                break

        if log is None or not emis.exists():
            return Response({'detail': 'No reschedule data found for this loan.'}, status=status.HTTP_404_NOT_FOUND)

        # Build full history of all reschedules that have snapshot EMIs so the
        # frontend can display previous reschedule plans (Reschedule #1, #2, ...)
        history = []
        all_logs = LoanRescheduleLog.objects.filter(loan_application=loan).order_by('created_at')
        for hlog in all_logs:
            h_emis_qs = LoanEMIReschedule.objects.filter(reschedule_log=hlog).order_by('installment_date')
            if not h_emis_qs.exists():
                continue

            h_rows = []
            for hemi in h_emis_qs:
                h_last_collection = (
                    EmiCollectionDetail.objects
                    .filter(reschedule_emi=hemi)
                    .order_by('-collected_at')
                    .first()
                )
                h_collection_status = getattr(h_last_collection, 'status', None) if h_last_collection else None

                h_active_assignment = (
                    EmiAgentAssign.objects.select_related('agent')
                    .filter(reschedule_emi=hemi, is_active=True)
                    .first()
                )
                h_assigned_agent_name = (
                    h_active_assignment.agent.full_name
                    if h_active_assignment is not None and getattr(h_active_assignment, 'agent', None) is not None
                    else None
                )

                h_rows.append({
                    'id': hemi.id,
                    'installment_date': hemi.installment_date,
                    'frequency': hemi.frequency,
                    'installment_amount': str(hemi.installment_amount),
                    'principal_amount': str(hemi.principal_amount),
                    'interest_amount': str(hemi.interest_amount),
                    'paid': bool(getattr(hemi, 'paid', False)),
                    'paid_date': getattr(hemi, 'paid_date', None),
                    'is_overdue': bool(getattr(hemi, 'is_overdue', False)),
                    'overdue_days': getattr(hemi, 'overdue_days', 0),
                    'late_fee': str(getattr(hemi, 'late_fee', 0) or 0),
                    'collection_status': h_collection_status,
                    'assigned_agent_name': h_assigned_agent_name,
                })

            h_totals = h_emis_qs.aggregate(
                total_installment_amount=Sum('installment_amount'),
                total_principal_amount=Sum('principal_amount'),
                total_interest_amount=Sum('interest_amount'),
            )

            h_total_installment_amount = h_totals.get('total_installment_amount') or Decimal('0.00')
            h_total_principal_amount = h_totals.get('total_principal_amount') or Decimal('0.00')
            h_total_interest_amount = h_totals.get('total_interest_amount') or Decimal('0.00')

            h_unpaid_res = h_emis_qs.filter(paid=False)
            h_outstanding = h_unpaid_res.aggregate(
                total=Sum('installment_amount') + Sum('late_fee')
            )['total'] or Decimal('0.00')

            h_period = getattr(hlog, 'period', None)
            h_remaining_balance = getattr(h_period, 'remaining_balance', None) or Decimal('0.00')
            h_remaining_principal = getattr(h_period, 'remaining_principal', None) or Decimal('0.00')
            h_remaining_interest = getattr(h_period, 'remaining_interest', None) or Decimal('0.00')

            history.append({
                'reschedule_no': hlog.reschedule_no,
                'old_outstanding': str(hlog.old_outstanding),
                'penalty_rate': str(hlog.penalty_rate),
                'penalty_amount': str(hlog.penalty_amount),
                'new_total_balance': str(hlog.new_total_balance),
                'new_installment_amount': str(hlog.new_installment_amount),
                'new_number_of_installments': hlog.new_number_of_installments,
                'reschedule_unit': hlog.reschedule_unit,
                'reschedule_length': hlog.reschedule_length,
                'remaining_balance': str(h_remaining_balance),
                'remaining_principal': str(h_remaining_principal),
                'remaining_interest': str(h_remaining_interest),
                'totals': {
                    'total_installment_amount': str(h_total_installment_amount),
                    'total_principal_amount': str(h_total_principal_amount),
                    'total_interest_amount': str(h_total_interest_amount),
                },
                'outstanding': str(h_outstanding),
                'emis': h_rows,
            })

        # Build per-EMI rows (include id, status fields, and assigned agent for frontend)
        results = []
        for emi in emis:
            # Latest collection status for this rescheduled EMI (if any)
            last_collection = (
                EmiCollectionDetail.objects
                .filter(reschedule_emi=emi)
                .order_by('-collected_at')
                .first()
            )
            collection_status = getattr(last_collection, 'status', None) if last_collection else None

            # Currently assigned agent for this rescheduled EMI (if any)
            active_assignment = (
                EmiAgentAssign.objects.select_related('agent')
                .filter(reschedule_emi=emi, is_active=True)
                .first()
            )
            assigned_agent_id = (
                active_assignment.agent.agent_id
                if active_assignment is not None and getattr(active_assignment, 'agent', None) is not None
                else None
            )
            assigned_agent_name = (
                active_assignment.agent.full_name
                if active_assignment is not None and getattr(active_assignment, 'agent', None) is not None
                else None
            )

            results.append({
                'id': emi.id,
                'installment_date': emi.installment_date,
                'frequency': emi.frequency,
                'installment_amount': str(emi.installment_amount),
                'principal_amount': str(emi.principal_amount),
                'interest_amount': str(emi.interest_amount),
                'paid': bool(getattr(emi, 'paid', False)),
                'paid_date': getattr(emi, 'paid_date', None),
                'is_overdue': bool(getattr(emi, 'is_overdue', False)),
                'overdue_days': getattr(emi, 'overdue_days', 0),
                'late_fee': str(getattr(emi, 'late_fee', 0) or 0),
                'collection_status': collection_status,
                'assigned_agent_id': assigned_agent_id,
                'assigned_agent_name': assigned_agent_name,
            })

        # Aggregated totals for header
        totals = emis.aggregate(
            total_installment_amount=Sum('installment_amount'),
            total_principal_amount=Sum('principal_amount'),
            total_interest_amount=Sum('interest_amount'),
        )

        total_installment_amount = totals.get('total_installment_amount') or Decimal('0.00')
        total_principal_amount = totals.get('total_principal_amount') or Decimal('0.00')
        total_interest_amount = totals.get('total_interest_amount') or Decimal('0.00')

        # Outstanding for potential repeat reschedule: sum of unpaid rescheduled EMIs + late fee
        unpaid_res = emis.filter(paid=False)
        outstanding = unpaid_res.aggregate(
            total=Sum('installment_amount') + Sum('late_fee')
        )['total'] or Decimal('0.00')

        # Remaining amounts snapshot from the LoanPeriod linked to this log (if any)
        period = getattr(log, 'period', None)
        remaining_balance = getattr(period, 'remaining_balance', None) or Decimal('0.00')
        remaining_principal = getattr(period, 'remaining_principal', None) or Decimal('0.00')
        remaining_interest = getattr(period, 'remaining_interest', None) or Decimal('0.00')

        return Response({
            'loan_ref_no': loan.loan_ref_no,
            'reschedule_no': log.reschedule_no,
            # Snapshot summary from LoanRescheduleLog
            'old_outstanding': str(log.old_outstanding),
            'penalty_rate': str(log.penalty_rate),
            'penalty_amount': str(log.penalty_amount),
            'new_total_balance': str(log.new_total_balance),
            'new_installment_amount': str(log.new_installment_amount),
            'new_number_of_installments': log.new_number_of_installments,
            'reschedule_unit': log.reschedule_unit,
            'reschedule_length': log.reschedule_length,
            # Remaining amounts for header "Excess" display
            'remaining_balance': str(remaining_balance),
            'remaining_principal': str(remaining_principal),
            'remaining_interest': str(remaining_interest),
            # Aggregated totals from LoanEMIReschedule
            'totals': {
                'total_installment_amount': str(total_installment_amount),
                'total_principal_amount': str(total_principal_amount),
                'total_interest_amount': str(total_interest_amount),
            },
            # Outstanding snapshot for this latest reschedule plan (used as base for next reschedule)
            'outstanding': str(outstanding),
            # Full history of reschedules for this loan (including the latest one)
            'history': history,
            'emis': results,
        }, status=status.HTTP_200_OK)


@method_decorator(branch_permission_required('view_emis'), name='dispatch')
class upcomingEMIView(TemplateView):
    template_name = 'loanPaymentAndCollection/upcomingEMI.html'

    def _build_upcoming_emi_data(self, branch):
        from datetime import timedelta
        from django.utils import timezone
        from zoneinfo import ZoneInfo

        today = timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).date()
        next_day = today + timedelta(days=1)
        week_end = today + timedelta(days=7)
        next_month_start = (today.replace(day=1) + timedelta(days=32)).replace(day=1)

        branch_agents = list(
            Agent.objects
            .filter(branch=branch, status='active')
            .order_by('full_name')
            .values('agent_id', 'full_name', 'phone')
        )

        daily_emis = LoanEMISchedule.objects.select_related(
            'loan_application',
            'loan_application__customer',
            'loan_application__agent'
        ).filter(
            loan_application__branch=branch,
            paid=False,
            reschedule=0,
            frequency='daily',
            installment_date=next_day
        ).order_by('installment_date')

        weekly_emis = LoanEMISchedule.objects.select_related(
            'loan_application',
            'loan_application__customer',
            'loan_application__agent'
        ).filter(
            loan_application__branch=branch,
            paid=False,
            reschedule=0,
            frequency='weekly',
            installment_date__gt=next_day,
            installment_date__lte=week_end
        ).order_by('installment_date')

        monthly_emis = LoanEMISchedule.objects.select_related(
            'loan_application',
            'loan_application__customer',
            'loan_application__agent'
        ).filter(
            loan_application__branch=branch,
            paid=False,
            reschedule=0,
            frequency='monthly',
            installment_date__gt=week_end,
            installment_date__lt=next_month_start
        ).order_by('installment_date')

        res_daily_emis = LoanEMIReschedule.objects.select_related(
            'loan_application',
            'loan_application__customer',
            'loan_application__agent',
        ).filter(
            loan_application__branch=branch,
            paid=False,
            frequency='daily',
            installment_date=next_day,
        ).order_by('installment_date')

        res_weekly_emis = LoanEMIReschedule.objects.select_related(
            'loan_application',
            'loan_application__customer',
            'loan_application__agent',
        ).filter(
            loan_application__branch=branch,
            paid=False,
            frequency='weekly',
            installment_date__gt=next_day,
            installment_date__lte=week_end,
        ).order_by('installment_date')

        res_monthly_emis = LoanEMIReschedule.objects.select_related(
            'loan_application',
            'loan_application__customer',
            'loan_application__agent',
        ).filter(
            loan_application__branch=branch,
            paid=False,
            frequency='monthly',
            installment_date__gt=week_end,
            installment_date__lt=next_month_start,
        ).order_by('installment_date')

        all_emis = (
            list(daily_emis)
            + list(weekly_emis)
            + list(monthly_emis)
            + list(res_daily_emis)
            + list(res_weekly_emis)
            + list(res_monthly_emis)
        )
        all_emis.sort(key=lambda x: x.installment_date)

        emi_data = []
        for emi in all_emis:
            installment_date = emi.installment_date
            date_str = installment_date.strftime('%Y-%m-%d')
            days_remaining = (installment_date - today).days
            status_val = 'Upcoming' if installment_date > today else 'Due'

            if isinstance(emi, LoanEMISchedule):
                active_assignment = (
                    EmiAgentAssign.objects.select_related('agent')
                    .filter(emi=emi, is_active=True)
                    .first()
                )
            else:
                active_assignment = (
                    EmiAgentAssign.objects.select_related('agent')
                    .filter(reschedule_emi=emi, is_active=True)
                    .first()
                )

            assigned_agent_id = active_assignment.agent.agent_id if active_assignment and active_assignment.agent else None
            assigned_agent_name = active_assignment.agent.full_name if active_assignment and active_assignment.agent else None

            emi_data.append({
                'id': emi.id,
                'loan_ref_no': emi.loan_application.loan_ref_no,
                'customer_name': emi.loan_application.customer.full_name if emi.loan_application.customer else 'N/A',
                'installment_date': date_str,
                'installment_amount': emi.installment_amount,
                'principal_amount': emi.principal_amount,
                'interest_amount': emi.interest_amount,
                'frequency': emi.frequency,
                'days_remaining': days_remaining,
                'is_overdue': emi.is_overdue,
                'overdue_days': emi.overdue_days,
                'status': status_val,
                'assigned_agent': branch_agents,
                'assigned_agent_id': assigned_agent_id,
                'assigned_agent_name': assigned_agent_name,
                'late_fee': float(emi.late_fee) if hasattr(emi, 'late_fee') and emi.late_fee is not None else 0.0,
                'paid_date': emi.paid_date.strftime('%Y-%m-%d') if emi.paid_date else None,
            })

        return emi_data, branch_agents

    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return redirect('/branch/login/?next=' + request.path)

        try:
            employee = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            request.session.flush()
            return redirect('/branch/login/?next=' + request.path)

        page = request.GET.get('page', '1')
        try:
            page_num = int(page)
        except (TypeError, ValueError):
            page_num = 1

        emi_list, branch_agents = self._build_upcoming_emi_data(employee.branch)
        paginator = Paginator(emi_list, 10)
        try:
            page_obj = paginator.page(page_num)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages) if paginator.num_pages else []

        context = self.get_context_data(**kwargs)
        context['upcoming_emis_page'] = page_obj
        try:
            context['upcoming_page_links'] = list(
                paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            context['upcoming_page_links'] = list(paginator.page_range)
        context['branch_agents'] = branch_agents
        return self.render_to_response(context)

class upcomingEMIAPIView(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            
        try:
            from datetime import timedelta
            from django.utils import timezone
            from django.db.models import Q
            from zoneinfo import ZoneInfo
            
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch
            
            # Calculate date ranges based on frequency
            today = timezone.now().astimezone(ZoneInfo('Asia/Kolkata'))
            
            # Calculate date ranges based on frequency
            today = timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).date()
            next_day = today + timedelta(days=1)
            week_end = today + timedelta(days=7)
            # First day of next month (acts as an exclusive upper bound)
            next_month_start = (today.replace(day=1) + timedelta(days=32)).replace(day=1)
            
            # Get all ACTIVE agents for the branch, ordered by name
            branch_agents = list(
                Agent.objects
                .filter(branch=branch, status='active')
                .order_by('full_name')
                .values('agent_id', 'full_name', 'phone')
            )
            
            # Build upcoming EMIs for each frequency independently
            # Note: LoanEMISchedule.installment_date is a DateField, so compare with dates only
            daily_emis = LoanEMISchedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            ).filter(
                loan_application__branch=branch,
                paid=False,
                reschedule=0,
                frequency='daily',
                installment_date=next_day
            ).order_by('installment_date')
            
            weekly_emis = LoanEMISchedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            ).filter(
                loan_application__branch=branch,
                paid=False,
                reschedule=0,
                frequency='weekly',
                installment_date__gt=next_day,
                installment_date__lte=week_end
            ).order_by('installment_date')
            
            monthly_emis = LoanEMISchedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            ).filter (
                loan_application__branch=branch,
                paid=False,
                reschedule=0,
                frequency='monthly',
                installment_date__gt=week_end,
                installment_date__lt=next_month_start
            ).order_by('installment_date')
            
            # Also include upcoming RESCHEDULED EMIs for loans that have been rescheduled
            res_daily_emis = LoanEMIReschedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent',
            ).filter(
                loan_application__branch=branch,
                paid=False,
                frequency='daily',
                installment_date=next_day,
            ).order_by('installment_date')

            res_weekly_emis = LoanEMIReschedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent',
            ).filter(
                loan_application__branch=branch,
                paid=False,
                frequency='weekly',
                installment_date__gt=next_day,
                installment_date__lte=week_end,
            ).order_by('installment_date')

            res_monthly_emis = LoanEMIReschedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent',
            ).filter(
                loan_application__branch=branch,
                paid=False,
                frequency='monthly',
                installment_date__gt=week_end,
                installment_date__lt=next_month_start,
            ).order_by('installment_date')

            # Combine all EMIs (original + rescheduled) and sort by installment date
            all_emis = (
                list(daily_emis)
                + list(weekly_emis)
                + list(monthly_emis)
                + list(res_daily_emis)
                + list(res_weekly_emis)
                + list(res_monthly_emis)
            )
            all_emis.sort(key=lambda x: x.installment_date)
            
            # Prepare response data
            emi_data = []
            for emi in all_emis:
                installment_date = emi.installment_date  # DateField
                date_str = installment_date.strftime('%Y-%m-%d')
                time_str = '00:00'
                days_remaining = (installment_date - today).days
                status_val = 'Upcoming' if installment_date > today else 'Due'
                
                # Find active agent assignment (if any) for this EMI schedule
                if isinstance(emi, LoanEMISchedule):
                    active_assignment = (
                        EmiAgentAssign.objects.select_related('agent')
                        .filter(emi=emi, is_active=True)
                        .first()
                    )
                else:
                    active_assignment = (
                        EmiAgentAssign.objects.select_related('agent')
                        .filter(reschedule_emi=emi, is_active=True)
                        .first()
                    )
                assigned_agent_id = active_assignment.agent.agent_id if active_assignment and active_assignment.agent else None
                assigned_agent_name = active_assignment.agent.full_name if active_assignment and active_assignment.agent else None

                emi_data.append({
                    'id': emi.id,
                    'loan_ref_no': emi.loan_application.loan_ref_no,
                    'customer_name': emi.loan_application.customer.full_name if emi.loan_application.customer else 'N/A',
                    'installment_date': date_str,
                    'installment_time': time_str,
                    'installment_amount': emi.installment_amount,
                    'principal_amount': emi.principal_amount,
                    'interest_amount': emi.interest_amount,
                    'frequency': emi.frequency,
                    'days_remaining': days_remaining,
                    'is_overdue': emi.is_overdue,
                    'overdue_days': emi.overdue_days,
                    'status': status_val,
                    # All branch agents to populate the dropdown
                    'assigned_agent': branch_agents,
                    # Currently assigned agent for this EMI (if any)
                    'assigned_agent_id': assigned_agent_id,
                    'assigned_agent_name': assigned_agent_name,
                    'late_fee': float(emi.late_fee) if hasattr(emi, 'late_fee') and emi.late_fee is not None else 0.0,
                    'paid_date': emi.paid_date.strftime('%Y-%m-%d') if emi.paid_date else None
                })
            
            if emi_data:
                return Response(emi_data, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'No upcoming EMIs found.'}, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AssignAgentToEMI(APIView):
    def post(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        loan_ref_no = request.data.get('loan_ref_no')
        schedule_id = request.data.get('schedule_id')
        agent_id = request.data.get('agent_id')
        
        if not all([logged_user_id, loan_ref_no, schedule_id, agent_id]):
            return Response(
                {'detail': 'Missing required parameters'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Get branch manager
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch
            
            # Validate schedule_id is numeric
            try:
                schedule_pk = int(schedule_id)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'Invalid schedule_id. It must be a numeric ID.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Step 1: Ensure schedule exists by ID
            try:
                emi_schedule = LoanEMISchedule.objects.select_related('loan_application').get(id=schedule_pk)
            except LoanEMISchedule.DoesNotExist:
                return Response(
                    {'detail': 'Invalid EMI schedule ID'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Step 2: Verify this schedule belongs to the provided loan_ref_no
            if getattr(emi_schedule.loan_application, 'loan_ref_no', None) != loan_ref_no:
                return Response(
                    {'detail': 'EMI schedule does not belong to the specified loan'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Step 3: Verify the schedule is in the same branch as the manager
            if getattr(emi_schedule.loan_application, 'branch', None) != branch:
                return Response(
                    {'detail': 'EMI schedule is not in your branch'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Step 4: If the loan has been rescheduled, block assigning agents on ORIGINAL EMIs.
            # Agent assignment for rescheduled loans should be done against the new reschedule plan only.
            if is_loan_rescheduled(emi_schedule.loan_application):
                return Response(
                    {
                        'detail': 'This loan has been rescheduled. Agent assignment on original EMIs is not allowed.'
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Optional guard: do not allow assignment on a paid EMI
            if getattr(emi_schedule, 'paid', False):
                return Response({'detail': 'Cannot assign agent to a paid EMI schedule.'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Get agent
            agent = Agent.objects.get(agent_id=agent_id, branch=branch)

            # Handle the unique constraint properly for EMI assignments
            # First, deactivate any existing active assignment for this EMI
            EmiAgentAssign.objects.filter(
                emi=emi_schedule,
                is_active=True
            ).update(is_active=False)

            # Now create the new assignment
            assignment, created = EmiAgentAssign.objects.get_or_create(
                emi=emi_schedule,
                defaults={
                    'agent': agent,
                    'assigned_by': branch_manager,
                    'is_active': True
                }
            )

            # If assignment already exists, update it
            if not created:
                assignment.agent = agent
                assignment.assigned_by = branch_manager
                assignment.is_active = True
                assignment.save()
            
            return Response({
                'status': 'success',
                'message': 'Agent assigned successfully',
                'assigned_agent_name': agent.full_name
            }, status=status.HTTP_200_OK)
            
        except BranchEmployee.DoesNotExist:
            return Response(
                {'detail': 'Branch manager not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except LoanEMISchedule.DoesNotExist:
            return Response(
                {'detail': 'EMI schedule not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Agent.DoesNotExist:
            return Response(
                {'detail': 'Agent not found in your branch'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class AssignAgentToRescheduleEMI(APIView):
    def post(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        loan_ref_no = request.data.get('loan_ref_no')
        reschedule_emi_id = request.data.get('reschedule_emi_id')
        agent_id = request.data.get('agent_id')

        if not all([logged_user_id, loan_ref_no, reschedule_emi_id, agent_id]):
            return Response(
                {'detail': 'Missing required parameters'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch

            try:
                res_emi_pk = int(reschedule_emi_id)
            except (TypeError, ValueError):
                return Response(
                    {'detail': 'Invalid reschedule_emi_id. It must be a numeric ID.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                res_emi = LoanEMIReschedule.objects.select_related('loan_application').get(id=res_emi_pk)
            except LoanEMIReschedule.DoesNotExist:
                return Response(
                    {'detail': 'Invalid rescheduled EMI ID'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if getattr(res_emi.loan_application, 'loan_ref_no', None) != loan_ref_no:
                return Response(
                    {'detail': 'Rescheduled EMI does not belong to the specified loan'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            if getattr(res_emi.loan_application, 'branch', None) != branch:
                return Response(
                    {'detail': 'Rescheduled EMI is not in your branch'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Optional guard: do not allow assignment on a paid rescheduled EMI
            if getattr(res_emi, 'paid', False):
                return Response(
                    {'detail': 'Cannot assign agent to a paid rescheduled EMI.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            agent = Agent.objects.get(agent_id=agent_id, branch=branch)

            # Deactivate any existing active assignment for this rescheduled EMI
            EmiAgentAssign.objects.filter(
                reschedule_emi=res_emi,
                is_active=True,
            ).update(is_active=False)

            # Create or update assignment
            assignment, created = EmiAgentAssign.objects.get_or_create(
                reschedule_emi=res_emi,
                defaults={
                    'agent': agent,
                    'assigned_by': branch_manager,
                    'is_active': True,
                },
            )

            if not created:
                assignment.agent = agent
                assignment.assigned_by = branch_manager
                assignment.is_active = True
                assignment.save()

            return Response(
                {
                    'status': 'success',
                    'message': 'Agent assigned successfully to rescheduled EMI',
                    'assigned_agent_name': agent.full_name,
                },
                status=status.HTTP_200_OK,
            )

        except BranchEmployee.DoesNotExist:
            return Response(
                {'detail': 'Branch manager not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except LoanEMIReschedule.DoesNotExist:
            return Response(
                {'detail': 'Rescheduled EMI not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Agent.DoesNotExist:
            return Response(
                {'detail': 'Agent not found in your branch'},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )



class UnassignAgentFromEMI(APIView):
    def post(self, request, emi_id, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not emi_id:
            return Response({'detail': 'emi_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emi_schedule = LoanEMISchedule.objects.get(id=emi_id)
        except LoanEMISchedule.DoesNotExist:
            return Response({'detail': 'EMI schedule not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure EMI belongs to manager's branch
        if getattr(emi_schedule.loan_application, 'branch', None) != branch_manager.branch:
            return Response({'detail': 'EMI schedule does not belong to your branch.'}, status=status.HTTP_404_NOT_FOUND)

        # Optional guard: do not allow unassignment on a paid EMI
        if getattr(emi_schedule, 'paid', False):
            return Response({'detail': 'Cannot unassign agent from a paid EMI schedule.'}, status=status.HTTP_400_BAD_REQUEST)

        # Delete all assignment records for this EMI
        from django.db import transaction
        with transaction.atomic():
            deleted_count, _ = EmiAgentAssign.objects.filter(emi=emi_schedule).delete()
            if deleted_count == 0:
                return Response({'detail': 'No assignment found for this EMI.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'status': 'success', 'message': 'Agent unassigned and assignments deleted successfully.'}, status=status.HTTP_200_OK)


## for emi data detail update after received ##

def is_loan_rescheduled(loan):
    logs_qs = LoanRescheduleLog.objects.filter(loan_application=loan)
    return LoanEMIReschedule.objects.filter(reschedule_log__in=logs_qs).exists()

class receiveEmiDetailAPI(APIView):
    def post(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        emi_id = kwargs.get('emi_id') or request.data.get('emi_id')
        if not emi_id:
            return Response({'detail': 'emi_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emi = LoanEMISchedule.objects.select_related('loan_application__branch').get(id=emi_id)
        except LoanEMISchedule.DoesNotExist:
            return Response({'detail': 'EMI not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure EMI belongs to manager's branch
        if getattr(emi.loan_application, 'branch', None) != branch_manager.branch:
            return Response({'detail': 'EMI does not belong to your branch.'}, status=status.HTTP_403_FORBIDDEN)

        # Block receiving on original EMIs once the loan has been rescheduled
        if is_loan_rescheduled(emi.loan_application):
            return Response(
                {'detail': 'This loan has been rescheduled. Original EMIs are inactive.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the latest collection for this EMI
        collection = (
            EmiCollectionDetail.objects
            .filter(emi=emi)
            .order_by('-collected_at')
            .first()
        )
        if not collection:
            return Response({'detail': 'No collection record found for this EMI.'}, status=status.HTTP_404_NOT_FOUND)

        period = (
            LoanPeriod.objects
            .filter(loan_application=emi.loan_application)
            .order_by('-created_at', '-id')
            .first()
        )
        # Try to persist remaining values on the LoanApplication if provided
        # We always attach to the EMI's loan_application to avoid cross-branch issues
        try:
            remaining_updates = {}
            rb = request.data.get('remaining_balance', None)
            rp = request.data.get('remaining_principal', None)
            ri = request.data.get('remaining_interest', None)
            # Parse and validate if provided (allow "0" / 0)
            if rb is not None and rb != '':
                remaining_updates['remaining_balance'] = Decimal(str(rb))
            if rp is not None and rp != '':
                remaining_updates['remaining_principal'] = Decimal(str(rp))
            if ri is not None and ri != '':
                remaining_updates['remaining_interest'] = Decimal(str(ri))
            if remaining_updates:
                # loan_app = emi.loan_application
                # for k, v in remaining_updates.items():
                #     setattr(loan_app, k, v)
                # # Persist only the updated fields
                # loan_app.save(update_fields=list(remaining_updates.keys()))
                if period:
                    for k, v in remaining_updates.items():
                        setattr(period, k, v)
                    period.save(update_fields=list(remaining_updates.keys()))
        except Exception as _remain_err:
            # Don't fail the main flow if remaining values are malformed; report as 400 only if they were provided
            return Response({'detail': f'Invalid remaining values: {_remain_err}'}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency: if already verified and EMI marked paid, return success (after any remaining-values update above)
        if collection.status == 'verified' and emi.paid:
            return Response({
                'success': True,
                'message': 'EMI already verified.',
                'emi_id': emi.id,
                'paid': emi.paid,
                'paid_date': emi.paid_date,
                'collection_id': collection.collected_id,
                'verified_by': branch_manager.id,
                'verified_at': collection.verified_at,
                'status': collection.status,
                'remaining_balance': getattr(emi.loan_application, 'remaining_balance', None),
                'remaining_principal': getattr(emi.loan_application, 'remaining_principal', None),
                'remaining_interest': getattr(emi.loan_application, 'remaining_interest', None),
            }, status=status.HTTP_200_OK)

        try:
            with transaction.atomic():
                # Mark EMI as paid (if not already)
                emi.paid = True
                if not emi.paid_date:
                    emi.paid_date = timezone.now().date()
                
                # Update late fee if not already set and it's decided during collection 
                if not emi.late_fee or emi.late_fee == 0:
                    emi.late_fee = collection.penalty_received

                # Fill payment_reference from collection if available and not already set
                if not emi.payment_reference and collection.payment_reference:
                    emi.payment_reference = collection.payment_reference
                emi.save()

                # Verify the collection
                collection.verified_by = branch_manager
                collection.verified_at = timezone.now()
                collection.status = 'verified'
                collection.save()

                HOA = None
                if emi.frequency == 'daily':
                    HOA = ChartOfAccount.objects.filter(code='122').first()
                elif emi.frequency == 'weekly':
                    HOA = ChartOfAccount.objects.filter(code='123').first()

                branch_account = BranchAccount.objects.select_for_update().get(branch=branch_manager.branch, type='CASH')
                if branch_account:
                    branch_account.current_balance += (collection.amount_received + collection.penalty_received)
                    branch_account.updated_at = timezone.now().date()
                    branch_account.save()

                total_amount = (collection.amount_received or Decimal('0')) + (collection.penalty_received or Decimal('0'))

                # Decide purpose/code based on HOA and frequency
                if HOA is not None:
                    purpose = HOA.head_of_account
                    code = HOA.code
                else:
                    freq = (emi.frequency or '').lower()

                    if freq in ('days', 'daily', 'day'):
                        purpose = 'Installment collection daily'
                        code = '122'
                    elif freq in ('weekly', 'week'):
                        purpose = 'Installment collection group'
                        code = '123'
                    else:
                        purpose = 'EMI Collection'
                        code = None
                
                BranchTransaction.objects.create(
                    branch=branch_manager.branch,
                    disbursement_log=None,
                    mode=getattr(collection, 'payment_mode', None),
                    transaction_type='CREDIT',
                    purpose=purpose,
                    code=code,
                    amount=total_amount,
                    description=f"EMI received for {HOA.description} {emi.loan_application.loan_ref_no} (Collection ID: {collection.collected_id})",
                    created_by=branch_manager,
                    branch_account=branch_account,
                )
                
                # Compute next upcoming unpaid EMI for the same loan
                try:
                    today = timezone.now().date()
                    next_emi = (
                        LoanEMISchedule.objects
                        .filter(loan_application=emi.loan_application, paid=False, installment_date__gte=today)
                        .exclude(id=emi.id)
                        .order_by('installment_date', 'id')
                        .first()
                    )
                    next_emi_amount = getattr(next_emi, 'installment_amount', None) if next_emi else None
                    next_emi_due_date = getattr(next_emi, 'installment_date', None) if next_emi else None
                except Exception as _next_err:
                    next_emi = None
                    next_emi_amount = None
                    next_emi_due_date = None
                    print(f"[Email] Could not compute next EMI: {_next_err}")

                # Gather all unpaid EMIs before and including the next EMI's due date
                unpaid_emis_to_next = []
                unpaid_emis_total = None
                if next_emi:
                    unpaid_qs = (
                        LoanEMISchedule.objects
                        .filter(
                            loan_application=emi.loan_application,
                            paid=False,
                            installment_date__lte=next_emi.installment_date,
                        )
                        .order_by('installment_date', 'id')
                    )
                    # Build a simple serializable list for the template
                    total = Decimal('0')
                    for s in unpaid_qs:
                        amt = s.installment_amount or Decimal('0')
                        total += amt
                        unpaid_emis_to_next.append({
                            'id': s.id,
                            'amount': amt,
                            'due_date': s.installment_date,
                            'is_overdue': bool(s.installment_date and s.installment_date < today),
                        })
                    unpaid_emis_total = total
                else:
                    unpaid_emis_to_next = []
                    unpaid_emis_total = Decimal('0')

                #--- Email Notification: EMI Payment Received ---
                try:
                    loan_application = emi.loan_application
                    customer = getattr(loan_application, 'customer', None)
                    customer_email = getattr(customer, 'email', '') or ''
                    customer_email = customer_email.strip() if isinstance(customer_email, str) else ''

                    if customer_email:
                        subject = f"EMI Payment Received - Ref: {loan_application.loan_ref_no}"

                        message_text = (
                            "SUNDARAM FINANCE\n"
                            "==================\n\n"
                            "EMI Payment Receipt\n\n"
                            f"Reference No: {loan_application.loan_ref_no}\n"
                            f"EMI ID: {emi.id}\n"
                            f"Installment Amount: {collection.amount_received}\n"
                            f"Paid Date: {emi.paid_date}\n"
                            f"Payment Ref: {emi.payment_reference or collection.payment_reference or 'N/A'}\n"
                            f"Next EMI Amount: {next_emi_amount if next_emi_amount is not None else 'N/A'}\n"
                            f"Next EMI Date: {next_emi_due_date if next_emi_due_date else 'N/A'}\n\n"
                            "Thank you for your payment."
                        )

                        # Prepare HTML using the shared template
                        try:
                            context = {
                                'purpose_flag': 'emi_received',
                                'sub_header': 'EMI Payment Received',
                                'loan_ref_no': loan_application.loan_ref_no,
                                'emi_id': emi.id,
                                'installment_amount': collection.amount_received,
                                'paid_date': emi.paid_date,
                                'payment_reference': emi.payment_reference or collection.payment_reference or 'N/A',
                                'next_emi_amount': next_emi_amount if next_emi_amount is not None else 'N/A',
                                'next_emi_due_date': next_emi_due_date if next_emi_due_date else 'N/A',
                                'unpaid_emis_to_next': unpaid_emis_to_next,
                                'unpaid_emis_total': unpaid_emis_total,
                            }
                            message_html = render_to_string('loan/loan_application_email.html', context)
                        except Exception as _tmpl_err:
                            message_html = None
                            print(f"[Email] Could not render EMI HTML template: {_tmpl_err}")

                        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@sundaramfinance.com')
                        email = EmailMultiAlternatives(
                            subject=subject,
                            body=message_text,
                            from_email=from_email,
                            to=[customer_email],
                            reply_to=[from_email]
                        )
                        if message_html:
                            email.attach_alternative(message_html, "text/html")
                        # Send silently to avoid failing the main flow if email fails
                        email.send(fail_silently=True)
                        print(f"[Email] EMI receipt sent to customer: {customer_email}")
                    else:
                        print("[Email] Skipped sending EMI receipt: customer email not available")
                except Exception as e:
                    print(f"[Email Error] EMI receipt send failed: {str(e)}")
                #--- End Email Notification ---

                return Response({
                    'success': True,
                    'message': 'EMI collection verified and marked as paid.',
                    'emi_id': emi.id,
                    'paid': emi.paid,
                    'paid_date': emi.paid_date,
                    'payment_reference': emi.payment_reference,
                    'collection_id': collection.collected_id,
                    'verified_by': branch_manager.id,
                    'verified_at': collection.verified_at,
                    'status': collection.status,
                    'next_emi_amount': next_emi_amount,
                    'next_emi_due_date': next_emi_due_date,
                    'unpaid_emis_to_next': unpaid_emis_to_next,
                    # 'unpaid_emis_total': unpaid_emis_total,
                    # 'remaining_balance': getattr(emi.loan_application, 'remaining_balance', None),
                    # 'remaining_principal': getattr(emi.loan_application, 'remaining_principal', None),
                    # 'remaining_interest': getattr(emi.loan_application, 'remaining_interest', None),
                    'remaining_balance': getattr(period, 'remaining_balance', None) if period else None,
                    'remaining_principal': getattr(period, 'remaining_principal', None) if period else None,
                    'remaining_interest': getattr(period, 'remaining_interest', None) if period else None,
                }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({'detail': f'Failed to verify collection: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class receiveRescheduleEmiDetailAPI(APIView):
    def post(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        reschedule_emi_id = kwargs.get('reschedule_emi_id') or request.data.get('reschedule_emi_id')
        if not reschedule_emi_id:
            return Response({'detail': 'reschedule_emi_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            res_emi = LoanEMIReschedule.objects.select_related('loan_application__branch').get(id=reschedule_emi_id)
        except LoanEMIReschedule.DoesNotExist:
            return Response({'detail': 'Rescheduled EMI not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Ensure EMI belongs to manager's branch
        if getattr(res_emi.loan_application, 'branch', None) != branch_manager.branch:
            return Response({'detail': 'EMI does not belong to your branch.'}, status=status.HTTP_403_FORBIDDEN)

        # Get the latest collection for this rescheduled EMI
        collection = (
            EmiCollectionDetail.objects
            .filter(reschedule_emi=res_emi)
            .order_by('-collected_at')
            .first()
        )
        if not collection:
            return Response({'detail': 'No collection record found for this rescheduled EMI.'}, status=status.HTTP_404_NOT_FOUND)

        period = (
            LoanPeriod.objects
            .filter(loan_application=res_emi.loan_application)
            .order_by('-created_at', '-id')
            .first()
        )

        try:
            remaining_updates = {}
            rb = request.data.get('remaining_balance', None)
            rp = request.data.get('remaining_principal', None)
            ri = request.data.get('remaining_interest', None)
            if rb is not None and rb != '':
                remaining_updates['remaining_balance'] = Decimal(str(rb))
            if rp is not None and rp != '':
                remaining_updates['remaining_principal'] = Decimal(str(rp))
            if ri is not None and ri != '':
                remaining_updates['remaining_interest'] = Decimal(str(ri))

            if period:
                # Existing carry-forward amounts before this EMI. If the client
                # sent an explicit remaining_balance (from the main EMI page),
                # treat that as the starting "excess"; otherwise use the
                # persisted LoanPeriod remaining_balance.
                base_rb = remaining_updates.get('remaining_balance', None)
                if base_rb is None:
                    prev_rb = period.remaining_balance or Decimal('0.00')
                else:
                    prev_rb = base_rb

                prev_rp = period.remaining_principal or Decimal('0.00')
                prev_ri = period.remaining_interest or Decimal('0.00')

                # Scheduled amounts for this rescheduled EMI
                sched_inst = getattr(res_emi, 'installment_amount', Decimal('0.00')) or Decimal('0.00')
                sched_prin = getattr(res_emi, 'principal_amount', Decimal('0.00')) or Decimal('0.00')
                sched_int = getattr(res_emi, 'interest_amount', Decimal('0.00')) or Decimal('0.00')

                # Total available to pay this EMI = existing remaining (excess)
                # + newly collected amount for this reschedule EMI.
                amt_rcv = collection.amount_received or Decimal('0.00')
                total_available = prev_rb + amt_rcv

                # Use total_available to cover as many full EMIs as possible;
                # only the true remainder is carried forward as remaining_*.
                if sched_inst > 0:
                    full_emi_count = (total_available // sched_inst)
                    remainder = total_available - (full_emi_count * sched_inst)
                else:
                    full_emi_count = 0
                    remainder = total_available

                if remainder > 0:
                    # Split remainder into principal/interest using the EMI ratio
                    if sched_inst > 0:
                        prin_ratio = (sched_prin / sched_inst) if sched_inst != 0 else Decimal('0.00')
                    else:
                        prin_ratio = Decimal('0.00')

                    extra_prin = (remainder * prin_ratio).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)
                    extra_int = (remainder - extra_prin).quantize(Decimal('0.00'), rounding=ROUND_HALF_UP)

                    current_rb = remainder
                    current_rp = extra_prin
                    current_ri = extra_int
                else:
                    # Not enough to create new excess; previous remaining is fully consumed
                    current_rb = Decimal('0.00')
                    current_rp = Decimal('0.00')
                    current_ri = Decimal('0.00')

                # If client sends explicit remaining_principal/interest values,
                # they take precedence, but remaining_balance is driven by the
                # server-side recomputation so that existing excess + collected
                # is always used to pay as many EMIs as possible and only the
                # true leftover is carried forward.
                if 'remaining_principal' in remaining_updates:
                    current_rp = remaining_updates['remaining_principal']
                if 'remaining_interest' in remaining_updates:
                    current_ri = remaining_updates['remaining_interest']

                period.remaining_balance = current_rb
                period.remaining_principal = current_rp
                period.remaining_interest = current_ri

                period.save(update_fields=['remaining_balance', 'remaining_principal', 'remaining_interest'])
        except Exception as _remain_err:
            return Response({'detail': f'Invalid remaining values: {_remain_err}'}, status=status.HTTP_400_BAD_REQUEST)

        # Idempotency: if already verified and EMI marked paid, return success
        if collection.status == 'verified' and res_emi.paid:
            return Response({
                'success': True,
                'message': 'Rescheduled EMI already verified.',
                'reschedule_emi_id': res_emi.id,
                'paid': res_emi.paid,
                'paid_date': res_emi.paid_date,
                'collection_id': collection.collected_id,
                'verified_by': branch_manager.id,
                'verified_at': collection.verified_at,
                'status': collection.status,
                'remaining_balance': getattr(period, 'remaining_balance', None) if period else None,
                'remaining_principal': getattr(period, 'remaining_principal', None) if period else None,
                'remaining_interest': getattr(period, 'remaining_interest', None) if period else None,
            }, status=status.HTTP_200_OK)

        try:
            with transaction.atomic():
                # Mark rescheduled EMIs as paid.
                #
                # Existing behaviour always marked only the current res_emi as paid.
                # We now extend this so that, when total_available can cover multiple
                # full EMIs (full_emi_count > 0), we also mark the next unpaid
                # rescheduled EMIs in the same reschedule log as paid, starting
                # from the current EMI. This uses the already computed
                # full_emi_count / remainder above and does NOT alter any
                # cash-deposit modal logic or accounting entries.
                # ------------------------------------------------------------------

                # Helper to mark a single rescheduled EMI as paid while preserving
                # the existing late_fee and payment_reference logic for the
                # primary EMI tied to this collection.
                def _mark_single_res_emi_paid(target_emi, apply_late_fee_and_ref=False):
                    target_emi.paid = True
                    if not target_emi.paid_date:
                        target_emi.paid_date = timezone.now().date()

                    if apply_late_fee_and_ref:
                        # Update late fee if not already set and it's decided during collection
                        if not target_emi.late_fee or target_emi.late_fee == 0:
                            target_emi.late_fee = collection.penalty_received

                        # Fill payment_reference from collection if available and not already set
                        if not target_emi.payment_reference and collection.payment_reference:
                            target_emi.payment_reference = collection.payment_reference

                    target_emi.save()

                # Always mark the current res_emi as paid with full existing logic
                _mark_single_res_emi_paid(res_emi, apply_late_fee_and_ref=True)

                # If we computed full_emi_count and it indicates that multiple
                # EMIs can be covered, also mark subsequent unpaid EMIs from the
                # same reschedule snapshot as paid. This is limited strictly to
                # the rescheduled EMIs table and does not touch original EMIs or
                # any agent deposit flows.
                extra_to_mark = 0
                if 'full_emi_count' in locals() and isinstance(full_emi_count, Decimal):
                    try:
                        extra_to_mark = int(full_emi_count)
                    except Exception:
                        extra_to_mark = 0
                elif 'full_emi_count' in locals():
                    try:
                        extra_to_mark = int(full_emi_count)
                    except Exception:
                        extra_to_mark = 0

                # We have already marked the current res_emi as paid; reduce the
                # remaining count accordingly but never below zero.
                if extra_to_mark > 0:
                    extra_to_mark = max(0, extra_to_mark - 1)

                if extra_to_mark > 0:
                    # Fetch all rescheduled EMIs in this snapshot ordered by
                    # installment_date so we can walk forward from the current EMI.
                    sibling_emis_qs = (
                        LoanEMIReschedule.objects
                        .filter(reschedule_log=res_emi.reschedule_log)
                        .order_by('installment_date', 'id')
                    )

                    # Build a simple in-memory list so we can find the current
                    # index and then walk through upcoming unpaid EMIs.
                    sibling_emis = list(sibling_emis_qs)
                    try:
                        current_index = next(
                            idx for idx, emi_obj in enumerate(sibling_emis)
                            if emi_obj.id == res_emi.id
                        )
                    except StopIteration:
                        current_index = -1

                    if current_index != -1:
                        remaining_slots = extra_to_mark
                        for emi_obj in sibling_emis[current_index + 1:]:
                            if remaining_slots <= 0:
                                break

                            # Only mark EMIs that are not already paid
                            if emi_obj.paid:
                                continue

                            _mark_single_res_emi_paid(emi_obj, apply_late_fee_and_ref=False)
                            remaining_slots -= 1

                # If this operation results in all rescheduled EMIs for this
                # loan being fully paid, then there should be no remaining
                # excess carried on the LoanPeriod. Force all remaining_* to
                # zero so the loan looks completely closed from the schedule
                # page.
                if period is not None:
                    has_unpaid_res_emi = LoanEMIReschedule.objects.filter(
                        loan_application=res_emi.loan_application,
                        paid=False,
                    ).exists()
                    if not has_unpaid_res_emi:
                        period.remaining_balance = Decimal('0.00')
                        period.remaining_principal = Decimal('0.00')
                        period.remaining_interest = Decimal('0.00')
                        period.save(update_fields=[
                            'remaining_balance',
                            'remaining_principal',
                            'remaining_interest',
                        ])

                # Verify the collection
                collection.verified_by = branch_manager
                collection.verified_at = timezone.now()
                collection.status = 'verified'
                collection.save()

                HOA = None
                if res_emi.frequency == 'daily':
                    HOA = ChartOfAccount.objects.filter(code='122').first()
                elif res_emi.frequency == 'weekly':
                    HOA = ChartOfAccount.objects.filter(code='123').first()

                branch_account = BranchAccount.objects.select_for_update().get(branch=branch_manager.branch, type='CASH')
                if branch_account:
                    branch_account.current_balance += (collection.amount_received + collection.penalty_received)
                    branch_account.updated_at = timezone.now().date()
                    branch_account.save()

                total_amount = (collection.amount_received or Decimal('0')) + (collection.penalty_received or Decimal('0'))

                if HOA is not None:
                    purpose = HOA.head_of_account
                    code = HOA.code
                else:
                    freq = (res_emi.frequency or '').lower()

                    if freq in ('days', 'daily', 'day'):
                        purpose = 'Installment collection daily'
                        code = '122'
                    elif freq in ('weekly', 'week'):
                        purpose = 'Installment collection group'
                        code = '123'
                    else:
                        purpose = 'EMI Collection'
                        code = None

                BranchTransaction.objects.create(
                    branch=branch_manager.branch,
                    disbursement_log=None,
                    mode=getattr(collection, 'payment_mode', None),
                    transaction_type='CREDIT',
                    purpose=purpose,
                    code=code,
                    amount=total_amount,
                    description=f"Rescheduled EMI received for {HOA.description if HOA else ''} {res_emi.loan_application.loan_ref_no} (Collection ID: {collection.collected_id})",
                    created_by=branch_manager,
                    branch_account=branch_account,
                )

                return Response({
                    'success': True,
                    'message': 'Rescheduled EMI collection verified and marked as paid.',
                    'reschedule_emi_id': res_emi.id,
                    'paid': res_emi.paid,
                    'paid_date': res_emi.paid_date,
                    'payment_reference': res_emi.payment_reference,
                    'collection_id': collection.collected_id,
                    'verified_by': branch_manager.id,
                    'verified_at': collection.verified_at,
                    'status': collection.status,
                    'remaining_balance': getattr(period, 'remaining_balance', None) if period else None,
                    'remaining_principal': getattr(period, 'remaining_principal', None) if period else None,
                    'remaining_interest': getattr(period, 'remaining_interest', None) if period else None,
                }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'detail': f'Failed to verify rescheduled EMI collection: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
## get Emi scedule data ##
class GetEmiScedulePaidDataAPI(APIView):
    def get(self, request):

        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch   
            # Fetch all paid EMI schedules for this branch
            paid_emis = (
                LoanEMISchedule.objects
                .select_related('loan_application')
                .filter(loan_application__branch=branch, paid=True)
                .order_by('-paid_date', '-installment_date')
            )
            data = [
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
        
            return Response({'count': len(data), 'results': data}, status=status.HTTP_200_OK)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Failed to fetch paid EMI schedules: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


##### loan paid emi collected API #####
class loanPaidEmiCollectedAPI(APIView):
    def get(self, request, loan_ref_no, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
            branch = branch_manager.branch

            # Ensure the loan exists in this branch
            try:
                loan_app = LoanApplication.objects.get(loan_ref_no=loan_ref_no, branch=branch)
            except LoanApplication.DoesNotExist:
                return Response({'detail': 'Loan not found.'}, status=status.HTTP_404_NOT_FOUND)

            # Fetch all paid EMIs for this loan
            paid_emis = (
                LoanEMISchedule.objects
                .select_related('loan_application')
                .filter(loan_application=loan_app, paid=True)
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
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

########### Loan remaining API ################
class LoanRemainingAPI(APIView):
    def get(self, request, loan_ref_no, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            manager = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            loan_app = LoanApplication.objects.get(loan_ref_no=loan_ref_no, branch=manager.branch)
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Loan not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Get latest LoanPeriod for this loan application
        period = LoanPeriod.objects.filter(loan_application=loan_app).order_by('-created_at').first()
        if not period:
            return Response({'detail': 'Loan period not found for this loan.'}, status=status.HTTP_404_NOT_FOUND)

        data = {
            'loan_ref_no': loan_app.loan_ref_no,
            'remaining_balance': getattr(period, 'remaining_balance', None),
            'remaining_principal': getattr(period, 'remaining_principal', None),
            'remaining_interest': getattr(period, 'remaining_interest', None),
        }
        return Response(data, status=status.HTTP_200_OK)
##########

@method_decorator(branch_permission_required('view_emis'), name='dispatch')
class DueEmiView(TemplateView):
    template_name='loanPaymentAndCollection/due-emi.html'

    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        try:
            logged_user = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            request.session.flush()
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        branch = logged_user.branch
        now = timezone.now().astimezone(ZoneInfo('Asia/Kolkata'))
        today = now.date()

        branch_agents = list(
            Agent.objects
            .filter(branch=branch, status='active')
            .order_by('full_name')
            .values('agent_id', 'full_name', 'phone')
        )

        all_emis = (
            LoanEMISchedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            )
            .filter(
                loan_application__branch=branch,
                paid=False,
                reschedule=0,
                installment_date=today,
            )
            .exclude(collections__status__in=['collected', 'verified'])
            .order_by('installment_date')
            .distinct()
        )

        res_all_emis = (
            LoanEMIReschedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            )
            .filter(
                loan_application__branch=branch,
                paid=False,
                installment_date=today,
            )
            .order_by('installment_date')
        )

        combined_emis = list(all_emis) + list(res_all_emis)

        emi_data = []
        for emi in combined_emis:
            installment_date = getattr(emi, 'installment_date', None)
            date_str = installment_date.strftime('%Y-%m-%d') if installment_date else None
            time_str = '00:00'
            days_remaining = (installment_date - today).days if installment_date else 0
            status_val = 'Upcoming' if installment_date and installment_date > today else 'Due'

            active_assignment = (
                EmiAgentAssign.objects.select_related('agent')
                .filter(emi=emi, is_active=True)
                .first()
            )
            assigned_agent_id = active_assignment.agent.agent_id if active_assignment and active_assignment.agent else None
            assigned_agent_name = active_assignment.agent.full_name if active_assignment and active_assignment.agent else None

            emi_data.append({
                'id': getattr(emi, 'id', None),
                'loan_ref_no': getattr(getattr(emi, 'loan_application', None), 'loan_ref_no', None),
                'customer_name': (
                    getattr(getattr(getattr(emi, 'loan_application', None), 'customer', None), 'full_name', None)
                    or 'N/A'
                ),
                'installment_date': date_str,
                'installment_time': time_str,
                'installment_amount': getattr(emi, 'installment_amount', None),
                'principal_amount': getattr(emi, 'principal_amount', None),
                'interest_amount': getattr(emi, 'interest_amount', None),
                'frequency': getattr(emi, 'frequency', None),
                'days_remaining': days_remaining,
                'is_overdue': getattr(emi, 'is_overdue', False),
                'overdue_days': getattr(emi, 'overdue_days', 0),
                'status': status_val,
                'assigned_agent_id': assigned_agent_id,
                'assigned_agent_name': assigned_agent_name,
                'late_fee': float(getattr(emi, 'late_fee', 0) or 0) if hasattr(emi, 'late_fee') else 0.0,
                'paid_date': getattr(emi, 'paid_date', None),
            })

        paginator = Paginator(emi_data, 10)
        due_emis_page = paginator.get_page(request.GET.get('page') or 1)

        context = self.get_context_data(**kwargs)
        context['due_emis_page'] = due_emis_page
        try:
            context['due_page_links'] = list(
                paginator.get_elided_page_range(due_emis_page.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            context['due_page_links'] = list(paginator.page_range)
        context['branch_agents'] = branch_agents
        return self.render_to_response(context)

class DueEmiAPIView(APIView):
    def get(self, request):
        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from datetime import timedelta
            from django.utils import timezone
            from django.db.models import Q
            from zoneinfo import ZoneInfo
            
            logged_user = BranchEmployee.objects.get(id=logged_user_id)
            branch = logged_user.branch
            now = timezone.now().astimezone(ZoneInfo('Asia/Kolkata'))
            
            # Get today's date for filtering due EMIs
            today = now.date()
            
            # Get all ACTIVE agents for the branch, ordered by name
            branch_agents = list(
                Agent.objects
                .filter(branch=branch, status='active')
                .order_by('full_name')
                .values('agent_id', 'full_name', 'phone')
            )
            
            # Get all unpaid EMIs that are due today (installment_date == today)
            # Only include original schedules (reschedule=0) for LoanEMISchedule.
            all_emis = LoanEMISchedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            ).filter(
                loan_application__branch=branch,
                paid=False,
                reschedule=0,
                # Only today's EMIs
                installment_date=today
            ).exclude(
                # Exclude EMIs that have already been collected or verified
                collections__status__in=['collected', 'verified']
            ).order_by('installment_date').distinct()
            
            # Also include RESCHEDULED EMIs that are due today for rescheduled loans
            res_all_emis = LoanEMIReschedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            ).filter(
                loan_application__branch=branch,
                paid=False,
                installment_date=today,
            ).order_by('installment_date')

            # Combine original + rescheduled
            all_emis = list(all_emis) + list(res_all_emis)
            
            # Prepare response data
            emi_data = []
            for emi in all_emis:
                installment_date = emi.installment_date  # DateField
                date_str = installment_date.strftime('%Y-%m-%d')
                time_str = '00:00'
                days_remaining = (installment_date - today).days
                status_val = 'Upcoming' if installment_date > today else 'Due'
                
                # Find active agent assignment (if any) for this EMI schedule
                active_assignment = (
                    EmiAgentAssign.objects.select_related('agent')
                    .filter(emi=emi, is_active=True)
                    .first()
                )
                assigned_agent_id = active_assignment.agent.agent_id if active_assignment and active_assignment.agent else None
                assigned_agent_name = active_assignment.agent.full_name if active_assignment and active_assignment.agent else None

                emi_data.append({
                    'id': emi.id,
                    'loan_ref_no': emi.loan_application.loan_ref_no,
                    'customer_name': emi.loan_application.customer.full_name if emi.loan_application.customer else 'N/A',
                    'installment_date': date_str,
                    'installment_time': time_str,
                    'installment_amount': emi.installment_amount,
                    'principal_amount': emi.principal_amount,
                    'interest_amount': emi.interest_amount,
                    'frequency': emi.frequency,
                    'days_remaining': days_remaining,
                    'is_overdue': emi.is_overdue,
                    'overdue_days': emi.overdue_days,
                    'status': status_val,
                    # All branch agents to populate the dropdown
                    'assigned_agent': branch_agents,
                    # Currently assigned agent for this EMI (if any)
                    'assigned_agent_id': assigned_agent_id,
                    'assigned_agent_name': assigned_agent_name,
                    'late_fee': float(emi.late_fee) if hasattr(emi, 'late_fee') and emi.late_fee is not None else 0.0,
                    'paid_date': emi.paid_date.strftime('%Y-%m-%d') if emi.paid_date else None
                })
            
            if emi_data:
                return Response(emi_data, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'No due EMIs found.'}, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@method_decorator(branch_permission_required('view_emis'), name='dispatch')
class OverDueEmiView(TemplateView):
    template_name = 'loanPaymentAndCollection/overdue-emi.html'

    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        try:
            logged_user = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            request.session.flush()
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        branch = logged_user.branch
        now = timezone.now().astimezone(ZoneInfo('Asia/Kolkata'))
        today = now.date()

        branch_agents = list(
            Agent.objects
            .filter(branch=branch, status='active')
            .order_by('full_name')
            .values('agent_id', 'full_name', 'phone')
        )

        all_emis = (
            LoanEMISchedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            )
            .filter(
                loan_application__branch=branch,
                paid=False,
                reschedule=0,
                installment_date__lt=today,
            )
            .exclude(collections__status__in=['collected', 'verified'])
            .order_by('installment_date')
            .distinct()
        )

        res_all_emis = (
            LoanEMIReschedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            )
            .filter(
                loan_application__branch=branch,
                paid=False,
                installment_date__lt=today,
            )
            .order_by('installment_date')
        )

        combined_emis = list(all_emis) + list(res_all_emis)

        emi_data = []
        for emi in combined_emis:
            installment_date = getattr(emi, 'installment_date', None)
            date_str = installment_date.strftime('%Y-%m-%d') if installment_date else None
            time_str = '00:00'
            days_remaining = (installment_date - today).days if installment_date else 0
            status_val = 'Overdue'

            active_assignment = (
                EmiAgentAssign.objects.select_related('agent')
                .filter(emi=emi, is_active=True)
                .first()
            )
            assigned_agent_id = active_assignment.agent.agent_id if active_assignment and active_assignment.agent else None
            assigned_agent_name = active_assignment.agent.full_name if active_assignment and active_assignment.agent else None

            emi_data.append({
                'id': getattr(emi, 'id', None),
                'loan_ref_no': getattr(getattr(emi, 'loan_application', None), 'loan_ref_no', None),
                'customer_name': (
                    getattr(getattr(getattr(emi, 'loan_application', None), 'customer', None), 'full_name', None)
                    or 'N/A'
                ),
                'installment_date': date_str,
                'installment_time': time_str,
                'installment_amount': getattr(emi, 'installment_amount', None),
                'principal_amount': getattr(emi, 'principal_amount', None),
                'interest_amount': getattr(emi, 'interest_amount', None),
                'frequency': getattr(emi, 'frequency', None),
                'days_remaining': days_remaining,
                'is_overdue': getattr(emi, 'is_overdue', True),
                'overdue_days': getattr(emi, 'overdue_days', 0),
                'status': status_val,
                'assigned_agent_id': assigned_agent_id,
                'assigned_agent_name': assigned_agent_name,
                'late_fee': float(getattr(emi, 'late_fee', 0) or 0) if hasattr(emi, 'late_fee') else 0.0,
                'paid_date': getattr(emi, 'paid_date', None),
            })

        paginator = Paginator(emi_data, 10)
        overdue_emis_page = paginator.get_page(request.GET.get('page') or 1)

        context = self.get_context_data(**kwargs)
        context['overdue_emis_page'] = overdue_emis_page
        try:
            context['overdue_page_links'] = list(
                paginator.get_elided_page_range(overdue_emis_page.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            context['overdue_page_links'] = list(paginator.page_range)
        context['branch_agents'] = branch_agents
        return self.render_to_response(context)


class OverDueEmiAPIView(APIView):
    def get(self, request):
        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from datetime import timedelta
            from django.utils import timezone
            from django.db.models import Q
            from zoneinfo import ZoneInfo
            
            logged_user = BranchEmployee.objects.get(id=logged_user_id)
            branch = logged_user.branch
            now = timezone.now().astimezone(ZoneInfo('Asia/Kolkata'))
            
            # Get today's date for filtering due EMIs
            today = now.date()

            # Get all ACTIVE agents for the branch, ordered by name
            branch_agents = list(
                Agent.objects
                .filter(branch=branch, status='active')
                .order_by('full_name')
                .values('agent_id', 'full_name', 'phone')
            )
            
            # Get all unpaid EMIs that are overdue (installment_date < today)
            # Only include original schedules (reschedule=0) for LoanEMISchedule.
            all_emis = LoanEMISchedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            ).filter(
                loan_application__branch=branch,
                paid=False,
                reschedule=0,
                installment_date__lt=today
            ).exclude(
                # Exclude EMIs that have already been collected or verified
                collections__status__in=['collected', 'verified']
            ).order_by('installment_date').distinct()

            # Also include RESCHEDULED EMIs that are overdue for rescheduled loans
            res_all_emis = LoanEMIReschedule.objects.select_related(
                'loan_application',
                'loan_application__customer',
                'loan_application__agent'
            ).filter(
                loan_application__branch=branch,
                paid=False,
                installment_date__lt=today,
            ).order_by('installment_date')

            # Combine original + rescheduled
            all_emis = list(all_emis) + list(res_all_emis)
            
            # Prepare response data
            emi_data = []
            for emi in all_emis:
                installment_date = emi.installment_date  # DateField
                date_str = installment_date.strftime('%Y-%m-%d')
                time_str = '00:00'
                days_remaining = (installment_date - today).days
                status_val = 'Overdue'
                
                # Find active agent assignment (if any) for this EMI schedule
                active_assignment = (
                    EmiAgentAssign.objects.select_related('agent')
                    .filter(emi=emi, is_active=True)
                    .first()
                )
                assigned_agent_id = active_assignment.agent.agent_id if active_assignment and active_assignment.agent else None
                assigned_agent_name = active_assignment.agent.full_name if active_assignment and active_assignment.agent else None

                emi_data.append({
                    'id': emi.id,
                    'loan_ref_no': emi.loan_application.loan_ref_no,
                    'customer_name': emi.loan_application.customer.full_name if emi.loan_application.customer else 'N/A',
                    'installment_date': date_str,
                    'installment_time': time_str,
                    'installment_amount': emi.installment_amount,
                    'principal_amount': emi.principal_amount,
                    'interest_amount': emi.interest_amount,
                    'frequency': emi.frequency,
                    'days_remaining': days_remaining,
                    'is_overdue': emi.is_overdue,
                    'overdue_days': emi.overdue_days,
                    'status': status_val,
                    # All branch agents to populate the dropdown
                    'assigned_agent': branch_agents,
                    # Currently assigned agent for this EMI (if any)
                    'assigned_agent_id': assigned_agent_id,
                    'assigned_agent_name': assigned_agent_name,
                    'late_fee': float(emi.late_fee) if hasattr(emi, 'late_fee') and emi.late_fee is not None else 0.0,
                    'paid_date': emi.paid_date.strftime('%Y-%m-%d') if emi.paid_date else None
                })
            
            if emi_data:
                return Response(emi_data, status=status.HTTP_200_OK)
            else:
                return Response({'detail': 'No overdue EMIs found.'}, status=status.HTTP_404_NOT_FOUND)
                
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoanCloseRequestAPI(APIView):
    def get(self, request, loan_ref_no=None, *args, **kwargs):
        # Require session auth
        branch_manager_id = request.session.get('logged_user_id')
        if not branch_manager_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        # Validate manager and scope
        try:
            branch_manager = BranchEmployee.objects.select_related('branch').get(id=branch_manager_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not loan_ref_no:
            return Response({'detail': 'loan_ref_no is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Find loan for this branch
        try:
            loan = LoanApplication.objects.select_related('branch').get(
                loan_ref_no=loan_ref_no,
                branch=branch_manager.branch
            )
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Loan not found for this branch.'}, status=status.HTTP_404_NOT_FOUND)

        # Look for a pending request
        existing = LoanCloseRequest.objects.filter(
            loan_application=loan,
            status='pending'
        ).first()

        if existing:
            return Response({
                'pending': True,
                'request_id': existing.request_id,
                'status': existing.status,
                'loan_ref_no': loan.loan_ref_no,
                'requested_at': existing.requested_at,
            }, status=status.HTTP_200_OK)

        # Optionally include last (latest) request for display
        last_req = LoanCloseRequest.objects.filter(loan_application=loan).order_by('-requested_at').first()
        payload = {'pending': False}
        if last_req:
            payload['last_request'] = {
                'request_id': last_req.request_id,
                'status': last_req.status,
                'requested_at': last_req.requested_at,
            }
        return Response(payload, status=status.HTTP_200_OK)

    def post(self, request, loan_ref_no=None, *args, **kwargs):
        # Require session auth
        branch_manager_id = request.session.get('logged_user_id')
        if not branch_manager_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        # Validate manager and scope
        try:
            branch_manager = BranchEmployee.objects.select_related('branch').get(id=branch_manager_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)

        if not loan_ref_no:
            return Response({'detail': 'loan_ref_no is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Find the loan for this manager's branch
        try:
            loan = LoanApplication.objects.select_related('branch').get(
                loan_ref_no=loan_ref_no,
                branch=branch_manager.branch
            )
        except LoanApplication.DoesNotExist:
            return Response({'detail': 'Loan not found for this branch.'}, status=status.HTTP_404_NOT_FOUND)

        # Optional remarks from body
        remarks = (request.data or {}).get('remarks', '')

        # De-dupe: if a pending request already exists, return it
        existing = LoanCloseRequest.objects.filter(
            loan_application=loan,
            status='pending'
        ).first()
        if existing:
            return Response({
                'message': 'A pending close request already exists.',
                'request_id': existing.request_id,
                'status': existing.status,
                'loan_ref_no': loan.loan_ref_no,
            }, status=status.HTTP_200_OK)

        # Create a new request
        req = LoanCloseRequest.objects.create(
            loan_application=loan,
            branch=branch_manager.branch,
            requested_by=branch_manager,
            status='pending',
            remarks=remarks or None,
        )

        return Response({
            'message': 'Loan close (NOC) request submitted to HQ.',
            'request_id': req.request_id,
            'status': req.status,
            'loan_ref_no': loan.loan_ref_no,
        }, status=status.HTTP_201_CREATED)
        


class DisburLoadPDF(TemplateView):
    template_name='loan-disbursed/loan_disbursed_fund_pdf.html'

# @method_decorator(branch_manager_required, name='dispatch')
class BranchDashboardStatsAPI(APIView):
    def get(self, request, *args, **kwargs):
        # Auth via session
        branch_manager_id = request.session.get('logged_user_id')
        if not branch_manager_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            branch_manager = BranchEmployee.objects.get(id=branch_manager_id)
        except BranchEmployee.DoesNotExist:
            return Response({'detail': 'Branch manager not found.'}, status=status.HTTP_404_NOT_FOUND)
        branch = branch_manager.branch

        # Enforce branch scoping (default to session branch if branch_id is not provided)
        req_branch_id = request.GET.get('branch_id')
        if req_branch_id and str(req_branch_id) != str(branch.branch_id):
            return Response({'detail': 'Forbidden: branch mismatch.'}, status=status.HTTP_403_FORBIDDEN)

        # Query params
        time_range = request.GET.get('range', 'month')  # day | month | year
        try:
            year = int(request.GET.get('year', datetime.now().year))
            month = int(request.GET.get('month', datetime.now().month))
            day = int(request.GET.get('day', datetime.now().day))
        except (TypeError, ValueError):
            return Response({'detail': 'Invalid date parameters.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate day for the selected month when range=day
        if time_range == 'day':
            import calendar as _calendar
            if month < 1 or month > 12:
                return Response({'detail': 'Invalid month.'}, status=status.HTTP_400_BAD_REQUEST)
            dim = _calendar.monthrange(year, month)[1]
            if day < 1 or day > dim:
                return Response({'detail': 'Invalid day for the selected month.'}, status=status.HTTP_400_BAD_REQUEST)

        # Timezone-aware time window for counts
        tz = timezone.get_current_timezone()
        now = timezone.now().astimezone(tz)
        if time_range == 'day':
            # Define start/end for the selected day for stats
            start = timezone.make_aware(datetime(year, month, day, 0, 0, 0), tz)
            end = start + timedelta(days=1)
            trunc = TruncDay('submitted_at')
        elif time_range == 'year':
            start = timezone.make_aware(datetime(year, 1, 1, 0, 0, 0), tz)
            end = timezone.make_aware(datetime(year + 1, 1, 1, 0, 0, 0), tz)
            trunc = TruncYear('submitted_at')
        else:  # month
            start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0), tz)
            if month == 12:
                end = timezone.make_aware(datetime(year + 1, 1, 1, 0, 0, 0), tz)
            else:
                end = timezone.make_aware(datetime(year, month + 1, 1, 0, 0, 0), tz)
            trunc = TruncMonth('submitted_at')

        # Base queryset for this branch and range
        base_qs = LoanApplication.objects.filter(branch=branch, submitted_at__gte=start, submitted_at__lt=end)
        
        # Status buckets (branch perspective)
        pending_statuses = [
            'pending',
            'document_requested',
            'resubmitted',
            'branch_document_accepted',
            'branch_resubmitted',
        ]
        approved_statuses = ['branch_approved']
        disbursed_statuses = ['disbursed', 'disbursed_fund_released']
        rejected_statuses = ['reject', 'rejected_by_branch', 'hq_rejected']

        # NOTE: Disbursed stats should be based on the actual disbursement timestamp
        # (disbursed_at), not the application submitted_at, otherwise the dashboard
        # will show incorrect disbursed values for the selected range.
        disbursed_qs = LoanApplication.objects.filter(
            branch=branch,
            disbursed_at__isnull=False,
            disbursed_at__gte=start,
            disbursed_at__lt=end,
            status__in=disbursed_statuses,
        )

        stats = {
            'applied': base_qs.count(),
            'pending': base_qs.filter(status__in=pending_statuses).count(),
            'approved': base_qs.filter(status__in=approved_statuses).count(),
            'disbursed': disbursed_qs.count(),
            'rejected': base_qs.filter(status__in=rejected_statuses).count(),
        }

        savings_base_qs = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=start,
            submitted_at__lt=end,
        )

        savings_pending_statuses = [
            'pending',
            'document_requested',
            'document_requested_by_hq',
            'resubmitted',
            'branch_document_accepted',
            'branch_resubmitted',
            'hq_document_accepted',
            'hq_resubmitted',
        ]
        savings_approved_statuses = ['branch_approved', 'hq_approved', 'active', 'success']
        savings_disbursed_statuses = ['disbursed', 'disbursed_fund_released']
        savings_rejected_statuses = ['reject', 'rejected_by_branch', 'hq_rejected']

        savings_stats = {
            'applied': savings_base_qs.count(),
            'pending': savings_base_qs.filter(status__in=savings_pending_statuses).count(),
            'approved': savings_base_qs.filter(status__in=savings_approved_statuses).count(),
            'disbursed': savings_base_qs.filter(status__in=savings_disbursed_statuses).count(),
            'rejected': savings_base_qs.filter(status__in=savings_rejected_statuses).count(),
        }

        # Trends data depending on range
        trends = []
        emi_categories = []
        emi_scheduled = []
        emi_collected = []
        if time_range == 'year':
            # last 3 years including selected year
            years = [year - 2, year - 1, year]
            for y in years:
                y_start = timezone.make_aware(datetime(y, 1, 1, 0, 0, 0), tz)
                y_end = timezone.make_aware(datetime(y + 1, 1, 1, 0, 0, 0), tz)
                count = LoanApplication.objects.filter(branch=branch, submitted_at__year=y).count()
                trends.append({'label': str(y), 'count': count})
                emi_categories.append(str(y))
                emi_scheduled.append(
                    LoanEMISchedule.objects.filter(
                        loan_application__branch=branch,
                        installment_date__year=y
                    ).aggregate(total=Sum('installment_amount'))['total'] or 0
                )
                emi_collected.append(
                    EmiCollectionDetail.objects.filter(
                        loan_application__branch=branch,
                        collected=True,
                        status='verified',
                        verified_at__isnull=False,
                        verified_at__gte=y_start,
                        verified_at__lt=y_end,
                    ).filter(
                        Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False)
                    ).aggregate(total=Sum('amount_received'))['total'] or 0
                )
        elif time_range == 'day':
            # Trends: full selected month, grouped by day; Stats: selected day only
            month_start = timezone.make_aware(datetime(year, month, 1, 0, 0, 0), tz)
            if month == 12:
                month_end = timezone.make_aware(datetime(year + 1, 1, 1, 0, 0, 0), tz)
            else:
                month_end = timezone.make_aware(datetime(year, month + 1, 1, 0, 0, 0), tz)

            # Build per-day counts for the month
            month_qs = LoanApplication.objects.filter(
                branch=branch,
                submitted_at__gte=month_start,
                submitted_at__lt=month_end
            ).annotate(d=TruncDay('submitted_at')).values('d').annotate(c=Count('pk')).order_by('d')
            by_day = {row['d'].date(): row['c'] for row in month_qs}

            # Fill all days of the month
            import calendar as _calendar
            days_in_month = _calendar.monthrange(year, month)[1]
            trends = []
            for d in range(1, days_in_month + 1):
                dt = datetime(year, month, d).date()
                trends.append({'label': f"{d:02d}", 'count': by_day.get(dt, 0)})
                emi_categories.append(f"{d:02d}")
                emi_scheduled.append(
                    LoanEMISchedule.objects.filter(
                        loan_application__branch=branch,
                        installment_date=dt
                    ).aggregate(total=Sum('installment_amount'))['total'] or 0
                )
                day_start = timezone.make_aware(datetime(year, month, d, 0, 0, 0), tz)
                day_end = day_start + timedelta(days=1)
                emi_collected.append(
                    EmiCollectionDetail.objects.filter(
                        loan_application__branch=branch,
                        collected=True,
                        status='verified',
                        verified_at__isnull=False,
                        verified_at__gte=day_start,
                        verified_at__lt=day_end,
                    ).filter(
                        Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False)
                    ).aggregate(total=Sum('amount_received'))['total'] or 0
                )
        else:
            # month: last 6 months ending at selected month using exact month boundaries
            months = []
            y, m = year, month
            for _ in range(6):
                months.append((y, m))
                # Decrement month
                if m == 1:
                    y -= 1
                    m = 12
                else:
                    m -= 1
            # We built in reverse; sort ascending by date
            months = sorted(months)

            # Count applications per month
            trends = []
            for (yy, mm) in months:
                start_m = timezone.make_aware(datetime(yy, mm, 1, 0, 0, 0), tz)
                if mm == 12:
                    next_m = timezone.make_aware(datetime(yy + 1, 1, 1, 0, 0, 0), tz)
                else:
                    next_m = timezone.make_aware(datetime(yy, mm + 1, 1, 0, 0, 0), tz)
                c = LoanApplication.objects.filter(
                    branch=branch,
                    submitted_at__gte=start_m,
                    submitted_at__lt=next_m
                ).count()
                trends.append({'label': start_m.strftime('%b'), 'count': c})
                emi_categories.append(start_m.strftime('%b'))
                emi_scheduled.append(
                    LoanEMISchedule.objects.filter(
                        loan_application__branch=branch,
                        installment_date__gte=start_m.date(),
                        installment_date__lt=next_m.date()
                    ).aggregate(total=Sum('installment_amount'))['total'] or 0
                )
                emi_collected.append(
                    EmiCollectionDetail.objects.filter(
                        loan_application__branch=branch,
                        collected=True,
                        status='verified',
                        verified_at__isnull=False,
                        verified_at__gte=start_m,
                        verified_at__lt=next_m,
                    ).filter(
                        Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False)
                    ).aggregate(total=Sum('amount_received'))['total'] or 0
                )
        payload = {
            'range': time_range,
            'stats': stats,
            'savings_stats': savings_stats,
            'trends': trends,
            'emi_stats': {
                'categories': emi_categories,
                'scheduled': emi_scheduled,
                'collected': emi_collected,
            },
            'distribution': [
                stats['applied'],
                stats['pending'],
                stats['approved'],
                stats['disbursed'],
                stats['rejected'],
            ],
        }
        # --- Percentage deltas (current window vs previous equal-length window) ---
        # We already have the selected window as [start, end)
        prev_end = start
        prev_start = prev_end - (end - start)

        def _pct(cur, prev):
            # ((Current - Previous) / Previous) * 100 with guard for prev=0
            if prev == 0:
                return 0 if cur == 0 else 100
            return int(round(((cur - prev) / prev) * 100))

        # Buckets consistent with 'stats'
        cur_applied = LoanApplication.objects.filter(
            branch=branch, submitted_at__gte=start, submitted_at__lt=end
        ).count()
        prev_applied = LoanApplication.objects.filter(
            branch=branch, submitted_at__gte=prev_start, submitted_at__lt=prev_end
        ).count()

        cur_pending = LoanApplication.objects.filter(
            branch=branch, submitted_at__gte=start, submitted_at__lt=end, status__in=pending_statuses
        ).count()
        prev_pending = LoanApplication.objects.filter(
            branch=branch, submitted_at__gte=prev_start, submitted_at__lt=prev_end, status__in=pending_statuses
        ).count()

        cur_approved = LoanApplication.objects.filter(
            branch=branch, approved_at__isnull=False, approved_at__gte=start, approved_at__lt=end
        ).count()
        prev_approved = LoanApplication.objects.filter(
            branch=branch, approved_at__isnull=False, approved_at__gte=prev_start, approved_at__lt=prev_end
        ).count()

        cur_disbursed = LoanApplication.objects.filter(
            branch=branch, disbursed_at__isnull=False, disbursed_at__gte=start, disbursed_at__lt=end
        ).count()
        prev_disbursed = LoanApplication.objects.filter(
            branch=branch, disbursed_at__isnull=False, disbursed_at__gte=prev_start, disbursed_at__lt=prev_end
        ).count()

        cur_rejected = LoanApplication.objects.filter(
            branch=branch, submitted_at__gte=start, submitted_at__lt=end, status__in=rejected_statuses
        ).count()
        prev_rejected = LoanApplication.objects.filter(
            branch=branch, submitted_at__gte=prev_start, submitted_at__lt=prev_end, status__in=rejected_statuses
        ).count()

        stats_delta = {
            'applied': _pct(cur_applied, prev_applied),
            'pending': _pct(cur_pending, prev_pending),
            'approved': _pct(cur_approved, prev_approved),
            'disbursed': _pct(cur_disbursed, prev_disbursed),
            'rejected': _pct(cur_rejected, prev_rejected),
        }

        cur_savings_applied = SavingsAccountApplication.objects.filter(
            branch=branch, submitted_at__gte=start, submitted_at__lt=end
        ).count()
        prev_savings_applied = SavingsAccountApplication.objects.filter(
            branch=branch, submitted_at__gte=prev_start, submitted_at__lt=prev_end
        ).count()

        cur_savings_pending = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=start,
            submitted_at__lt=end,
            status__in=savings_pending_statuses,
        ).count()
        prev_savings_pending = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=prev_start,
            submitted_at__lt=prev_end,
            status__in=savings_pending_statuses,
        ).count()

        cur_savings_approved = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=start,
            submitted_at__lt=end,
            status__in=savings_approved_statuses,
        ).count()
        prev_savings_approved = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=prev_start,
            submitted_at__lt=prev_end,
            status__in=savings_approved_statuses,
        ).count()

        cur_savings_disbursed = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=start,
            submitted_at__lt=end,
            status__in=savings_disbursed_statuses,
        ).count()
        prev_savings_disbursed = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=prev_start,
            submitted_at__lt=prev_end,
            status__in=savings_disbursed_statuses,
        ).count()

        cur_savings_rejected = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=start,
            submitted_at__lt=end,
            status__in=savings_rejected_statuses,
        ).count()
        prev_savings_rejected = SavingsAccountApplication.objects.filter(
            branch=branch,
            submitted_at__gte=prev_start,
            submitted_at__lt=prev_end,
            status__in=savings_rejected_statuses,
        ).count()

        savings_stats_delta = {
            'applied': _pct(cur_savings_applied, prev_savings_applied),
            'pending': _pct(cur_savings_pending, prev_savings_pending),
            'approved': _pct(cur_savings_approved, prev_savings_approved),
            'disbursed': _pct(cur_savings_disbursed, prev_savings_disbursed),
            'rejected': _pct(cur_savings_rejected, prev_savings_rejected),
        }

        payload['stats_delta'] = stats_delta
        payload['savings_stats_delta'] = savings_stats_delta
        # --- Recent activity (independent of selected range) ---
        # Recent 5 loan applications for this branch
        recent_loans_qs = (
            LoanApplication.objects
            .filter(branch=branch)
            .select_related('customer')
            .order_by('-submitted_at')[:5]
        )
        recent_loans = []
        for la in recent_loans_qs:
            # Try to get a representative amount from first related loan detail
            first_detail = la.loan_details.first() if hasattr(la, 'loan_details') else None
            amount_val = float(first_detail.loan_amount) if first_detail and first_detail.loan_amount is not None else 0.0
            recent_loans.append({
                'id': la.loan_ref_no,
                'ref_no': la.loan_ref_no,
                'customer': getattr(la.customer, 'full_name', ''),
                'amount': amount_val,
                'date': la.submitted_at.strftime('%Y-%m-%d') if la.submitted_at else '',
                'status': la.status,
            })
        
        # Top 5 agents by number of applications for this branch
        agent_rows = (
            LoanApplication.objects
            .filter(branch=branch, agent__isnull=False)
            .values('agent_id', 'agent__full_name')
            .annotate(applications=Count('loan_ref_no'))
            .order_by('-applications')[:5]
        )
        recent_agents = [
            {
                'agent_id': row['agent_id'],
                'name': row['agent__full_name'] or '',
                'applications': row['applications'] or 0,
            }
            for row in agent_rows
        ]
        
        if not recent_agents:
            # Fallback: show up to 5 agents from this branch with 0 applications
            fallback_agents = Agent.objects.filter(branch=branch).values('agent_id', 'full_name').order_by('-created_at')[:5]
            recent_agents = [
                {
                    'agent_id': a['agent_id'],
                    'name': a['full_name'] or '',
                    'applications': 0,
                }
                for a in fallback_agents
            ]
        
        payload['recent_loans'] = recent_loans
        payload['recent_agents'] = recent_agents
        
        return Response(payload, status=status.HTTP_200_OK)


#############-------------------------------------------------------------------------##############
                        # Cash depositeed by Agent to Branch Office #
#############-------------------------------------------------------------------------##############

# agent today collections view #
class AgentTodayCollectionsView(APIView):
    def get(self, request, *args, **kwargs):
        agent_id = kwargs.get('agent_id')
        if not agent_id:
            return Response({'detail': 'agent_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Only pending collections by this agent (exclude already verified)
            qs = EmiCollectionDetail.objects.filter(
                collected_by_agent__agent_id=agent_id,
                status='collected',
            )

            agg = qs.aggregate(total_amount=Sum('amount_received'), penalty_total=Sum('penalty_received'))
            total = agg['total_amount'] or 0
            penalty_total = agg['penalty_total'] or 0

            # Categories from EMI frequency (support both original and rescheduled EMIs)
            categories = {'daily': 0, 'weekly': 0, 'saving': 0, 'others': 0}
            penalty_categories = {'daily': 0, 'weekly': 0, 'saving': 0, 'others': 0}

            for coll in qs.select_related('emi', 'reschedule_emi'):
                emi_obj = getattr(coll, 'reschedule_emi', None) or getattr(coll, 'emi', None)
                freq = (getattr(emi_obj, 'frequency', None) or '').lower() if emi_obj else ''

                amt = float(coll.amount_received or 0)
                pen = float(coll.penalty_received or 0)

                if freq == 'daily':
                    categories['daily'] += amt
                    penalty_categories['daily'] += pen
                elif freq == 'weekly':
                    categories['weekly'] += amt
                    penalty_categories['weekly'] += pen
                elif freq == 'saving':
                    categories['saving'] += amt
                    penalty_categories['saving'] += pen
                else:
                    categories['others'] += amt
                    penalty_categories['others'] += pen

            # Add pending savings collections for this agent (not yet deposited to branch)
            # We do not filter by date here to match the EMI settlement behavior.
            savings_qs = SavingsCollection.objects.filter(
                collected_by_agent__agent_id=agent_id,
                is_collected=True,
                is_deposited_to_branch=False,
            )
            savings_total = savings_qs.aggregate(total=Sum('amount'))['total'] or 0
            categories['saving'] += float(savings_total)

            total = float(total) + float(savings_total)

            return Response({
                'date': None,
                'agent_id': agent_id,
                'total_amount': float(total),
                'penalty_received': float(penalty_total),
                'categories': categories,
                'penalty_categories': penalty_categories,
                'count': qs.count(),
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Recive cash deposit by Agent to Branch Office #
class AgentDepositReceiveAPIView(APIView):
    def post(self, request, agent_id):
        try:
            data = request.data if isinstance(request.data, dict) else {}
            denominations = data.get('denominations') or []
            categories = data.get('categories') or {}
            online_amount = Decimal(str(data.get('online_amount') or 0)).quantize(Decimal('0.00'))

            # Get branch account ID from request if online amount is present
            branch_account_id = data.get('branch_account_id')
            selected_account = None
            if online_amount > 0 and not branch_account_id:
                return Response(
                    {'detail': 'branch_account_id is required when online_amount > 0'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Compute expected from server: sum of agent's pending ('collected') rows only
            # Include penalties in expected so it equals cash in hand + online actually brought by agent
            agg = (
                EmiCollectionDetail.objects
                .filter(collected_by_agent__agent_id=agent_id, status='collected')
                .aggregate(amount_total=Sum('amount_received'), penalty_total=Sum('penalty_received'))
            )
            server_expected = (agg.get('amount_total') or Decimal('0')) + (agg.get('penalty_total') or Decimal('0'))
            emi_expected_total = (server_expected if isinstance(server_expected, Decimal) else Decimal(str(server_expected))).quantize(Decimal('0.00'))

            savings_agg = (
                SavingsCollection.objects
                .filter(
                    collected_by_agent__agent_id=agent_id,
                    is_collected=True,
                    is_deposited_to_branch=False,
                )
                .aggregate(amount_total=Sum('amount'))
            )
            savings_expected_total = (savings_agg.get('amount_total') or Decimal('0'))
            if not isinstance(savings_expected_total, Decimal):
                savings_expected_total = Decimal(str(savings_expected_total))
            savings_expected_total = savings_expected_total.quantize(Decimal('0.00'))

            expected_total = (emi_expected_total + savings_expected_total).quantize(Decimal('0.00'))

            # Block case: agent has no collected EMIs but online amount is provided
            if expected_total == 0 and online_amount > 0:
                return Response({'detail': 'Amount mismatch'}, status=status.HTTP_400_BAD_REQUEST)

            # Who/where
            try:
                agent = Agent.objects.get(agent_id=agent_id)
            except Agent.DoesNotExist:
                return Response({'detail': 'Invalid agent_id'}, status=400)

            # Prefer the logged in branch employee if available
            received_by = None
            if hasattr(request.user, 'branchemployee') and getattr(request.user, 'branchemployee', None):
                received_by = request.user.branchemployee
            else:
                # Fallback 1: session-based auth used across branch views
                logged_user_id = request.session.get('logged_user_id')
                if logged_user_id:
                    try:
                        received_by = BranchEmployee.objects.get(id=logged_user_id)
                    except BranchEmployee.DoesNotExist:
                        received_by = None
                # Fallback 2: explicit payload field
                if received_by is None:
                    received_by_id = data.get('received_by')
                    if not received_by_id:
                        return Response({'detail': 'received_by is required'}, status=400)
                    try:
                        received_by = BranchEmployee.objects.get(employee_id=received_by_id)
                    except BranchEmployee.DoesNotExist:
                        return Response({'detail': 'Invalid received_by'}, status=400)

            if not received_by.branch:
                return Response({'detail': 'Receiver is not assigned to a branch'}, status=400)
            branch = received_by.branch

            # Get the branch's cash account
            try:
                cash_account = BranchAccount.objects.get(
                    branch=branch,
                    type='CASH'
                )
            except BranchAccount.DoesNotExist:
                return Response(
                    {'detail': 'No active cash account found for this branch'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # If online amount is provided, validate the selected account
            if online_amount > 0:
                try:
                    selected_account = BranchAccount.objects.get(
                        id=branch_account_id,
                        branch=branch,
                        type='BANK'
                    )
                except BranchAccount.DoesNotExist:
                    return Response(
                        {'detail': 'Invalid or inactive branch account selected'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Recompute server-side totals from denominations
            subtotal = Decimal('0.00')
            coin_total = 0
            cash_total = 0
            denom_lines = []
            for d in denominations:
                value = int(d.get('value') or 0)
                qty = int(d.get('qty') or 0)
                coin = int(d.get('coin') or 0)

                # Skip rows with no denomination value or with neither qty nor coin
                if value <= 0:
                    continue
                if qty <= 0 and coin <= 0:
                    continue

                # Server-side integrity: compute line_total and cash
                line_total = (Decimal(value) * Decimal(max(qty, 0))).quantize(Decimal('0.00'))
                if coin < 0:
                    coin = 0
                # coin cannot exceed line_total integer part
                max_coin = int(line_total)
                if coin > max_coin:
                    coin = max_coin
                cash = max(0, int(line_total) - coin)

                subtotal += line_total
                coin_total += coin
                cash_total += cash
                denom_lines.append((value, qty, line_total, coin, cash))

            grand_total = (subtotal + online_amount).quantize(Decimal('0.00'))
            # Backend validation
            # 1) Reject when branch-entered Grand Total exceeds agent's collected amount
            if grand_total > expected_total:
                return Response({'detail': 'Grand Total amount is greater than collected amount'}, status=status.HTTP_400_BAD_REQUEST)
            # 2) Optionally reject when collected exceeds entered Grand Total (kept for safety)
            if expected_total > grand_total:
                return Response({'detail': 'Collected amount exceeds Grand Total entered'}, status=status.HTTP_400_BAD_REQUEST)
            # Mismatch only matters if online is 0 (your UI logic)
            mismatch = (online_amount == 0 and grand_total != expected_total)

            # Pull categories (already computed in GET), default to 0.
            # Then augment daily/weekly/others with the actual penalty_received
            # amounts per frequency from EmiCollectionDetail, so that the
            # resulting AgentDeposit and BranchTransaction amounts include any
            # penalty portion for both normal and rescheduled EMIs.
            base_daily = Decimal(str(categories.get('daily') or 0)).quantize(Decimal('0.00'))
            base_weekly = Decimal(str(categories.get('weekly') or 0)).quantize(Decimal('0.00'))
            base_saving = Decimal(str(categories.get('saving') or 0)).quantize(Decimal('0.00'))
            base_others = Decimal(str(categories.get('others') or 0)).quantize(Decimal('0.00'))

            # Aggregate penalty per EMI frequency from the still-collected rows
            # that are being verified in this deposit. We look at the same
            # collected-by-agent batch that was used to compute expected_total
            # so that both original and rescheduled EMIs are handled uniformly.
            daily_penalty = Decimal('0.00')
            weekly_penalty = Decimal('0.00')
            others_penalty = Decimal('0.00')

            coll_for_penalty = (
                EmiCollectionDetail.objects
                .select_related('emi', 'reschedule_emi')
                .filter(collected_by_agent__agent_id=agent_id, status='collected')
            )

            for coll in coll_for_penalty:
                pen = (coll.penalty_received or Decimal('0.00'))
                if not pen:
                    continue
                emi_obj = getattr(coll, 'emi', None) or getattr(coll, 'reschedule_emi', None)
                freq = getattr(emi_obj, 'frequency', None) if emi_obj is not None else None
                if freq == 'daily':
                    daily_penalty += pen
                elif freq == 'weekly':
                    weekly_penalty += pen
                else:
                    # Treat all non-daily/weekly EMIs (including reschedule variants)
                    # as "others" for the purpose of penalty allocation.
                    others_penalty += pen

            daily_amount = (base_daily + daily_penalty).quantize(Decimal('0.00'))
            weekly_amount = (base_weekly + weekly_penalty).quantize(Decimal('0.00'))
            saving_amount = base_saving  # savings are not EMI-based, keep as-is
            others_amount = (base_others + others_penalty).quantize(Decimal('0.00'))

            with transaction.atomic():
                dep = AgentDeposit.objects.create(
                    agent=agent,
                    branch=branch,
                    received_by=received_by,
                    subtotal_amount=subtotal,
                    coin_total=Decimal(str(coin_total)).quantize(Decimal('0.00')),
                    cash_total=Decimal(str(cash_total)).quantize(Decimal('0.00')),
                    online_amount=online_amount,
                    grand_total=grand_total,
                    expected_total=expected_total,
                    mismatch=mismatch,
                    daily_amount=daily_amount,
                    weekly_amount=weekly_amount,
                    saving_amount=saving_amount,
                    others_amount=others_amount,
                    status='pending',
                    created_by=received_by,
                )

                den_objs = [
                    AgentDepositDenomination(
                        deposit=dep,
                        value=v,
                        qty=q,
                        line_total=lt,
                        coin=c,
                        cash=cs
                    )
                    for (v, q, lt, c, cs) in denom_lines
                ]
                AgentDepositDenomination.objects.bulk_create(den_objs)

                # Update BranchAccount balances for the received deposit.
                # Cash (notes+coins) goes to the branch CASH account; any
                # online_amount goes to the selected BANK account.
                try:
                    # subtotal already represents the full physical cash
                    # amount from denominations (notes + coins).
                    if subtotal and subtotal > 0:
                        cash_account.current_balance = (
                            cash_account.current_balance + subtotal
                        )
                        cash_account.updated_at = timezone.now().date()
                        cash_account.save(update_fields=['current_balance', 'updated_at'])

                    if selected_account is not None and online_amount and online_amount > 0:
                        selected_account.current_balance = (
                            selected_account.current_balance + online_amount
                        )
                        selected_account.updated_at = timezone.now().date()
                        selected_account.save(update_fields=['current_balance', 'updated_at'])
                except Exception as _acct_err:
                    # Do not block the main flow if wallet balance update fails;
                    # it can be reconciled later. Log for investigation.
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.error(f"Error updating BranchAccount balances for deposit {dep.deposit_id}: {_acct_err}")

                # After successful deposit, mark the agent's collected EMIs as paid (all-time, no date filter)
                try:
                    today = timezone.localdate()
                    collections_qs = (
                        EmiCollectionDetail.objects
                        .select_related('emi', 'reschedule_emi', 'loan_application')
                        .filter(
                            collected_by_agent=agent,
                            status__in=['collected']
                        )
                    )
                    for coll in collections_qs:
                        # Resolve the underlying schedule object: original or rescheduled EMI
                        emi_obj = getattr(coll, 'emi', None) or getattr(coll, 'reschedule_emi', None)
                        if emi_obj:
                            emi_obj.paid = True
                            # use collection date if available, else today
                            paid_dt = getattr(coll, 'collected_at', None)
                            emi_obj.paid_date = (paid_dt.date() if paid_dt else today)
                            # optionally persist a reference
                            if not getattr(emi_obj, 'payment_reference', None):
                                emi_obj.payment_reference = getattr(coll, 'collected_id', None) or f"DEP-{dep.deposit_id}"
                            emi_obj.late_fee = getattr(coll, 'penalty_received', Decimal('0.00')) or Decimal('0.00')
                            emi_obj.save(update_fields=['paid', 'paid_date', 'payment_reference', 'late_fee'])

                        # mark collection as verified
                        coll.status = 'verified'
                        coll.verified_by = received_by
                        coll.verified_at = timezone.now()
                        coll.save(update_fields=['status', 'verified_by', 'verified_at'])

                    # Mark pending savings collections as deposited to branch for this agent
                    SavingsCollection.objects.filter(
                        collected_by_agent=agent,
                        is_collected=True,
                        is_deposited_to_branch=False,
                    ).update(
                        is_deposited_to_branch=True,
                        deposited_at=timezone.now(),
                        deposited_deposit_id=dep.deposit_id,
                    )

                    # NEW: Cascade any excess amounts per loan to future EMIs and persist remaining in LoanPeriod
                    # Build per-loan aggregation from the just-verified agent collections
                    from collections import defaultdict
                    loan_groups = defaultdict(lambda: {
                        'total_amount': Decimal('0.00'),
                        'total_principal': Decimal('0.00'),
                        'total_interest': Decimal('0.00'),
                        'scheduled_amount': Decimal('0.00'),
                        'scheduled_principal': Decimal('0.00'),
                        'scheduled_interest': Decimal('0.00'),
                        'max_emi_date': None,
                    })

                    for coll in collections_qs:
                        la = coll.loan_application
                        if not la:
                            continue
                        g = loan_groups[la.loan_ref_no]
                        g['total_amount'] += (coll.amount_received or Decimal('0.00'))
                        g['total_principal'] += (coll.principal_received or Decimal('0.00'))
                        g['total_interest'] += (coll.interest_received or Decimal('0.00'))
                        # Use the underlying EMI object (original or rescheduled) when
                        # computing scheduled totals so that rescheduled EMIs are
                        # treated the same as normal ones for per-loan aggregation.
                        emi_obj = getattr(coll, 'emi', None) or getattr(coll, 'reschedule_emi', None)
                        if emi_obj:
                            g['scheduled_amount'] += (emi_obj.installment_amount or Decimal('0.00'))
                            g['scheduled_principal'] += (emi_obj.principal_amount or Decimal('0.00'))
                            g['scheduled_interest'] += (emi_obj.interest_amount or Decimal('0.00'))
                            if g['max_emi_date'] is None or emi_obj.installment_date > g['max_emi_date']:
                                g['max_emi_date'] = emi_obj.installment_date

                    for loan_ref, aggvals in loan_groups.items():
                        try:
                            loan_app = LoanApplication.objects.get(loan_ref_no=loan_ref)
                        except LoanApplication.DoesNotExist:
                            continue

                        # Pull latest LoanPeriod to include existing remaining in this batch's pool
                        period = loan_app.periods.order_by('-created_at').first()
                        rem_balance = (period.remaining_balance or Decimal('0.00')) if period else Decimal('0.00')
                        rem_principal = (period.remaining_principal or Decimal('0.00')) if period else Decimal('0.00')
                        rem_interest = (period.remaining_interest or Decimal('0.00')) if period else Decimal('0.00')

                        # Compute extras AFTER adding remaining to the collected totals to cover any shortfall first
                        extra_amount = (aggvals['total_amount'] + rem_balance - aggvals['scheduled_amount'])
                        extra_principal = (aggvals['total_principal'] + rem_principal - aggvals['scheduled_principal'])
                        extra_interest = (aggvals['total_interest'] + rem_interest - aggvals['scheduled_interest'])
                        if extra_amount < 0:
                            extra_amount = Decimal('0.00')
                        if extra_principal < 0:
                            extra_principal = Decimal('0.00')
                        if extra_interest < 0:
                            extra_interest = Decimal('0.00')

                        # Budgets available for cascading (already include previous remaining)
                        remainingForFulls = (extra_amount).quantize(Decimal('0.00'))
                        remainingPrincipal = (extra_principal).quantize(Decimal('0.00'))
                        remainingInterest = (extra_interest).quantize(Decimal('0.00'))

                        if remainingForFulls <= 0:
                            # nothing to cascade; adjust LoanPeriod remaining by the cover used in this batch
                            if period:
                                new_rb = (rem_balance + aggvals['total_amount'] - aggvals['scheduled_amount']).quantize(Decimal('0.00'))
                                new_rp = (rem_principal + aggvals['total_principal'] - aggvals['scheduled_principal']).quantize(Decimal('0.00'))
                                new_ri = (rem_interest + aggvals['total_interest'] - aggvals['scheduled_interest']).quantize(Decimal('0.00'))
                                if new_rb < 0:
                                    new_rb = Decimal('0.00')
                                if new_rp < 0:
                                    new_rp = Decimal('0.00')
                                if new_ri < 0:
                                    new_ri = Decimal('0.00')

                                # If the coverage exactly matches the scheduled amount (no
                                # remaining balance) then ensure any unpaid EMIs up to the
                                # latest collected EMI date are marked as paid instead of
                                # leaving them as due with zero remaining balance.
                                if new_rb == Decimal('0.00') and aggvals.get('max_emi_date') is not None:
                                    emis_to_check = LoanEMISchedule.objects.filter(
                                        loan_application=loan_app,
                                        paid=False,
                                        installment_date__lte=aggvals['max_emi_date'],
                                    )

                                    for emi_row in emis_to_check:
                                        sums = (
                                            EmiCollectionDetail.objects
                                            .filter(emi=emi_row, status__in=['collected', 'verified'])
                                            .aggregate(
                                                amt=Sum('amount_received'),
                                                pen=Sum('penalty_received'),
                                            )
                                        )
                                        total_paid = (sums.get('amt') or Decimal('0.00')) + (sums.get('pen') or Decimal('0.00'))
                                        due_amount = (emi_row.installment_amount or Decimal('0.00')) + (emi_row.late_fee or Decimal('0.00'))
                                        if total_paid >= due_amount and not emi_row.paid:
                                            emi_row.paid = True
                                            if not emi_row.paid_date:
                                                emi_row.paid_date = today
                                            emi_row.save(update_fields=['paid', 'paid_date'])

                                has_unpaid = LoanEMISchedule.objects.filter(loan_application=loan_app, paid=False).exists()
                                if not has_unpaid:
                                    new_rb = Decimal('0.00')
                                    new_rp = Decimal('0.00')
                                    new_ri = Decimal('0.00')
                                period.remaining_balance = new_rb
                                period.remaining_principal = new_rp
                                period.remaining_interest = new_ri
                                period.save(update_fields=['remaining_balance', 'remaining_principal', 'remaining_interest'])
                            continue

                        # Determine whether this loan is currently using a RESCHEDULE plan.
                        # If any LoanEMIReschedule rows exist for this loan, cascade extras only
                        # across unpaid LoanEMIReschedule EMIs; otherwise, use original LoanEMISchedule.
                        using_reschedule_plan = LoanEMIReschedule.objects.filter(loan_application=loan_app).exists()

                        if using_reschedule_plan:
                            emi_qs = LoanEMIReschedule.objects.filter(
                                loan_application=loan_app,
                                paid=False,
                            ).order_by('installment_date', 'id')
                        else:
                            emi_qs = LoanEMISchedule.objects.filter(
                                loan_application=loan_app,
                                paid=False,
                            ).order_by('installment_date', 'id')

                        # Iterate and allocate budgets to full EMIs only
                        for row in emi_qs:
                            rowEmi = (row.installment_amount or Decimal('0.00'))
                            rowPrincipal = (row.principal_amount or Decimal('0.00'))
                            rowInterest = (row.interest_amount or Decimal('0.00'))

                            # For rescheduled plans, decide coverage based primarily on
                            # the total EMI amount so that larger deposit batches can
                            # auto-pay multiple rescheduled EMIs (e.g. 300 against
                            # 138-EMI should cover 2 EMIs and leave 24 as remaining
                            # balance). We still track principal/interest budgets but
                            # do not block on them for rescheduled rows. For original
                            # EMIs, keep the stricter amount + principal + interest
                            # requirement.
                            if using_reschedule_plan:
                                if remainingForFulls < rowEmi:
                                    break
                            else:
                                # Original plan: require full cover (amount, principal, interest)
                                if remainingForFulls < rowEmi or remainingPrincipal < rowPrincipal or remainingInterest < rowInterest:
                                    break

                            # Create a branch-side verified collection for this EMI
                            # Find active assignment for this EMI (prefer the same agent)
                            if using_reschedule_plan:
                                assign_qs = EmiAgentAssign.objects.filter(reschedule_emi=row, is_active=True)
                            else:
                                assign_qs = EmiAgentAssign.objects.filter(emi=row, is_active=True)

                            try:
                                assign_obj = assign_qs.filter(agent=agent).order_by('-assigned_at').first() or assign_qs.order_by('-assigned_at').first()
                            except Exception:
                                assign_obj = None

                            # For rescheduled loans, attach the collection to LoanEMIReschedule;
                            # for original loans, attach to LoanEMISchedule.
                            new_coll_kwargs = dict(
                                assignment=assign_obj,
                                loan_application=loan_app,
                                collected_by_agent=agent,
                                amount_received=rowEmi,
                                principal_received=rowPrincipal,
                                interest_received=rowInterest,
                                penalty_received=Decimal('0.00'),
                                payment_mode='Cash',
                                payment_reference=f"DEP-{dep.deposit_id}",
                                remarks='Auto-verified via branch deposit cascade',
                                verified_by=received_by,
                                verified_at=timezone.now(),
                                status='verified',
                            )

                            if using_reschedule_plan:
                                new_coll_kwargs['reschedule_emi'] = row
                                new_coll_kwargs['emi'] = None
                            else:
                                new_coll_kwargs['emi'] = row
                                new_coll_kwargs['reschedule_emi'] = None

                            new_coll = EmiCollectionDetail.objects.create(**new_coll_kwargs)

                            # Mark EMI as paid
                            row.paid = True
                            row.paid_date = today
                            if not getattr(row, 'payment_reference', None):
                                row.payment_reference = new_coll.collected_id
                            row.save(update_fields=['paid', 'paid_date', 'payment_reference'])

                            # Deduct budgets
                            remainingForFulls = (remainingForFulls - rowEmi).quantize(Decimal('0.00'))
                            remainingPrincipal = (remainingPrincipal - rowPrincipal).quantize(Decimal('0.00'))
                            remainingInterest = (remainingInterest - rowInterest).quantize(Decimal('0.00'))

                            if using_reschedule_plan:
                                if remainingPrincipal < 0:
                                    remainingPrincipal = Decimal('0.00')
                                if remainingInterest < 0:
                                    remainingInterest = Decimal('0.00')

                        if remainingForFulls > 0 and aggvals.get('max_emi_date') is not None:
                            emis_to_check = LoanEMISchedule.objects.filter(
                                loan_application=loan_app,
                                paid=False,
                                installment_date__lte=aggvals['max_emi_date'],
                            ).order_by('installment_date', 'id')

                            pool = remainingForFulls
                            for emi_row in emis_to_check:
                                sums = (
                                    EmiCollectionDetail.objects
                                    .filter(emi=emi_row, status__in=['collected', 'verified'])
                                    .aggregate(
                                        amt=Sum('amount_received'),
                                        pen=Sum('penalty_received'),
                                    )
                                )
                                already_paid = (sums.get('amt') or Decimal('0.00')) + (sums.get('pen') or Decimal('0.00'))
                                due_amount = (emi_row.installment_amount or Decimal('0.00')) + (emi_row.late_fee or Decimal('0.00'))

                                if emi_row.paid:
                                    continue

                                needed_from_pool = (due_amount - already_paid).quantize(Decimal('0.00'))
                                if needed_from_pool <= 0:
                                    emi_row.paid = True
                                    if not emi_row.paid_date:
                                        emi_row.paid_date = today
                                    emi_row.save(update_fields=['paid', 'paid_date'])
                                    continue

                                if pool >= needed_from_pool:
                                    pool = (pool - needed_from_pool).quantize(Decimal('0.00'))
                                    emi_row.paid = True
                                    if not emi_row.paid_date:
                                        emi_row.paid_date = today
                                    emi_row.save(update_fields=['paid', 'paid_date'])
                                else:
                                    break

                            remainingForFulls = pool

                        # Persist the leftover to LoanPeriod for future cascades
                        if period:
                            # If all EMIs of the active plan are now paid, zero out remainders
                            if using_reschedule_plan:
                                has_unpaid = LoanEMIReschedule.objects.filter(loan_application=loan_app, paid=False).exists()
                            else:
                                has_unpaid = LoanEMISchedule.objects.filter(loan_application=loan_app, paid=False).exists()

                            if not has_unpaid:
                                period.remaining_balance = Decimal('0.00')
                                period.remaining_principal = Decimal('0.00')
                                period.remaining_interest = Decimal('0.00')
                            else:
                                period.remaining_balance = remainingForFulls
                                period.remaining_principal = remainingPrincipal
                                period.remaining_interest = remainingInterest

                                # Final safety pass: if there is still enough remaining_balance
                                # to cover one or more full EMIs (original schedule), consume
                                # it starting from the earliest unpaid EMIs so that we never
                                # leave an unpaid EMI while remaining_balance fully covers it.
                                if not using_reschedule_plan:
                                    rb_pool = period.remaining_balance or Decimal('0.00')
                                    if rb_pool > 0:
                                        unpaid_qs = (
                                            LoanEMISchedule.objects
                                            .filter(loan_application=loan_app, paid=False)
                                            .order_by('installment_date', 'id')
                                        )

                                        for emi_row in unpaid_qs:
                                            emi_due = (emi_row.installment_amount or Decimal('0.00')) + (emi_row.late_fee or Decimal('0.00'))
                                            if rb_pool >= emi_due and emi_due > 0:
                                                rb_pool = (rb_pool - emi_due).quantize(Decimal('0.00'))
                                                emi_row.paid = True
                                                if not emi_row.paid_date:
                                                    emi_row.paid_date = today
                                                emi_row.save(update_fields=['paid', 'paid_date'])
                                            else:
                                                break

                                        period.remaining_balance = rb_pool

                            period.save(update_fields=['remaining_balance', 'remaining_principal', 'remaining_interest'])
                except Exception as e:
                    # Do not fail the deposit if marking EMIs fails; this can be reconciled later
                    # pass
                    # Log this error but don't fail the transaction
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error marking EMIs as paid: {str(e)}")

                # Create BranchTransaction entries.
                # IMPORTANT: do not swallow errors here; otherwise the branch account can be
                # credited without any transaction record being created.
                payment_mode = 'Cash'
                if online_amount and online_amount > 0:
                    if coin_total > 0 or cash_total > 0:
                        payment_mode = 'Mixed'
                    else:
                        payment_mode = 'Online'

                if payment_mode == 'Mixed':
                    # Mixed: create two summary transactions, avoid category double-counting
                    BranchTransaction.objects.create(
                        branch=branch,
                        branch_account=cash_account,
                        disbursement_log=None,
                        mode='Cash',
                        transaction_type='CREDIT',
                        purpose='Agent deposit - Cash',
                        code=None,
                        amount=Decimal(str(cash_total)).quantize(Decimal('0.00')),
                        description=f"Agent deposit (cash) from {getattr(agent, 'full_name', 'Agent')} (Deposit ID: {dep.deposit_id})",
                        created_by=received_by,
                    )
                    if online_amount and online_amount > 0:
                        if selected_account is None:
                            raise ValueError('Selected bank account not found for online deposit')
                        BranchTransaction.objects.create(
                            branch=branch,
                            branch_account=selected_account,
                            disbursement_log=None,
                            mode='Online',
                            transaction_type='CREDIT',
                            purpose='Agent deposit - Online',
                            code=None,
                            amount=online_amount,
                            description=f"Agent deposit (online) from {getattr(agent, 'full_name', 'Agent')} (Deposit ID: {dep.deposit_id})",
                            created_by=received_by,
                        )
                elif payment_mode == 'Online':
                    # Online-only: always create at least one explicit online transaction to the selected account.
                    if selected_account is None:
                        raise ValueError('Selected bank account not found for online deposit')
                    BranchTransaction.objects.create(
                        branch=branch,
                        branch_account=selected_account,
                        disbursement_log=None,
                        mode='Online',
                        transaction_type='CREDIT',
                        purpose='Agent deposit - Online',
                        code=None,
                        amount=online_amount,
                        description=f"Agent deposit (online) from {getattr(agent, 'full_name', 'Agent')} (Deposit ID: {dep.deposit_id})",
                        created_by=received_by,
                    )
                else:
                    # Cash-only: keep category breakdown to CASH account
                    account_for_txn = cash_account

                    # Daily -> COA 122
                    if dep.daily_amount and dep.daily_amount > 0:
                        desc = f"Daily EMI deposit received from {getattr(agent, 'full_name', 'Agent')} (Deposit ID: {dep.deposit_id})"
                        coa_daily = ChartOfAccount.objects.filter(code='122').first()
                        BranchTransaction.objects.create(
                            branch=branch,
                            branch_account=account_for_txn,
                            disbursement_log=None,
                            mode=payment_mode,
                            transaction_type='CREDIT',
                            purpose=(coa_daily.head_of_account if coa_daily else 'Daily EMI'),
                            code=(coa_daily.code if coa_daily else '122'),
                            amount=dep.daily_amount,
                            description=desc,
                            created_by=received_by,
                        )

                    # Weekly -> COA 123
                    if dep.weekly_amount and dep.weekly_amount > 0:
                        desc = f"Weekly EMI deposit received from {getattr(agent, 'full_name', 'Agent')} (Deposit ID: {dep.deposit_id})"
                        coa_weekly = ChartOfAccount.objects.filter(code='123').first()
                        BranchTransaction.objects.create(
                            branch=branch,
                            branch_account=account_for_txn,
                            disbursement_log=None,
                            mode=payment_mode,
                            transaction_type='CREDIT',
                            purpose=(coa_weekly.head_of_account if coa_weekly else 'Weekly EMI'),
                            code=(coa_weekly.code if coa_weekly else '123'),
                            amount=dep.weekly_amount,
                            description=desc,
                            created_by=received_by,
                        )

                    # Saving -> COA 204
                    if dep.saving_amount and dep.saving_amount > 0:
                        desc = f"Saving deposit received from {getattr(agent, 'full_name', 'Agent')} (Deposit ID: {dep.deposit_id})"
                        coa_saving = ChartOfAccount.objects.filter(code='204').first()
                        BranchTransaction.objects.create(
                            branch=branch,
                            branch_account=account_for_txn,
                            disbursement_log=None,
                            mode=payment_mode,
                            transaction_type='CREDIT',
                            purpose=(coa_saving.head_of_account if coa_saving else 'Saving Deposit'),
                            code=(coa_saving.code if coa_saving else '204'),
                            amount=dep.saving_amount,
                            description=desc,
                            created_by=received_by,
                        )

            return Response({
                'deposit_id': dep.deposit_id,
                'status': dep.status,
                'mismatch': dep.mismatch
            }, status=201)
        except Exception as e:
            return Response({'detail': str(e)}, status=400)


# Add this API view for previous deposit
class AgentDepositPreviousAPIView(APIView):
    def get(self, request, agent_id):
        try:
            agent = Agent.objects.get(agent_id=agent_id)
            
            # Get date parameter
            selected_date = request.GET.get('date')
            
            deposits = AgentDeposit.objects.filter(agent=agent).select_related(
                'branch', 'received_by'
            ).order_by('-received_at')
            
            # Filter by date if provided
            if selected_date:
                deposits = deposits.filter(received_at__date=selected_date)
            else:
                # Default to today if no date provided
                deposits = deposits.filter(received_at__date=timezone.now().date())
            
            deposits_data = []
            for deposit in deposits:
                deposit_data = {
                    'deposit_id': deposit.deposit_id,
                    'received_at': deposit.received_at.isoformat(),
                    'subtotal_amount': str(deposit.subtotal_amount),
                    'coin_total': str(deposit.coin_total),
                    'cash_total': str(deposit.cash_total),
                    'online_amount': str(deposit.online_amount),
                    'grand_total': str(deposit.grand_total),
                    'expected_total': str(deposit.expected_total),
                    'mismatch': deposit.mismatch,
                    'daily_amount': str(deposit.daily_amount),
                    'weekly_amount': str(deposit.weekly_amount),
                    'saving_amount': str(deposit.saving_amount),
                    'others_amount': str(deposit.others_amount),
                    'status': deposit.status,
                    'remarks': deposit.remarks,
                    'branch_name': deposit.branch.branch_name if deposit.branch else '',
                    'received_by_name': deposit.received_by.get_full_name() if deposit.received_by else '',
                    'denominations': []
                }
                
                # Add denomination details
                for denom in deposit.denominations.all():
                    deposit_data['denominations'].append({
                        'value': denom.value,
                        'qty': denom.qty,
                        'line_total': str(denom.line_total),
                        'coin': denom.coin,
                        'cash': denom.cash
                    })
                
                deposits_data.append(deposit_data)
            
            return Response({
                'success': True,
                'deposits': deposits_data,
                'count': len(deposits_data)
            }, status=status.HTTP_200_OK)
            
        except Agent.DoesNotExist:
            return Response({
                'success': False,
                'detail': 'Agent not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({
                'success': False,
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# for AddAccount #
class AddAccount(APIView):
    def post(self, request):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            messages.error(request, 'Authentication required.')
            return redirect('/branch/wallet')

        try:
            branch_manager = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            messages.error(request, 'Branch manager not found.')
            return redirect('/branch/wallet')

        branch = branch_manager.branch

        try:
            # Get form data
            account_name = request.POST.get('account_name')
            account_number = request.POST.get('account_number')
            bank_name = request.POST.get('bank_name')
            amount_raw = request.POST.get('amount')

            # Validation
            errors = {}
            if not account_name:
                errors['account_name'] = "Account name is required."
            if not account_number:
                errors['account_number'] = "Account number is required."
            if not bank_name:
                errors['bank_name'] = "Bank name is required."

            from decimal import Decimal, InvalidOperation
            initial_amount = Decimal('0.00')
            if amount_raw is None or amount_raw == '':
                errors['amount'] = "Amount is required."
            else:
                try:
                    initial_amount = Decimal(str(amount_raw))
                    if initial_amount < 0:
                        errors['amount'] = "Amount cannot be negative."
                except (InvalidOperation, ValueError):
                    errors['amount'] = "Enter a valid amount."

            # Check if account number already exists for this branch
            if BranchAccount.objects.filter(account_number=account_number, branch=branch).exists():
                errors['account_number'] = "Account number already exists for this branch."

            if errors:
                for error in errors.values():
                    messages.error(request, error)
                return redirect('/branch/wallet')

            # Create the account directly (no API call needed since this IS the API)
            account = BranchAccount.objects.create(
                branch=branch,
                type='BANK',  # Default to BANK type for bank accounts
                name=account_name,  # Using 'name' field to store account_name
                bank_name=bank_name,
                account_number=account_number,
                current_balance=initial_amount,
                created_by=branch_manager,
                updated_by=branch_manager
            )

            messages.success(request, f"Account {account_name} added successfully!")
            
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")

        return redirect('/branch/wallet')

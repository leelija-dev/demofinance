from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, CreateView, FormView, View
from django.contrib.auth.views import LoginView, PasswordResetView, PasswordResetConfirmView, PasswordChangeView
from django.urls import reverse_lazy
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect, HttpResponse
from django.contrib.auth.hashers import make_password
from django.db import transaction, IntegrityError
from branch.models import BranchEmployee, BranchAccount, BranchTransaction, AgentDeposit
from agent.models import Agent
from .models import HeadquarterEmployee, Role, Branch, HeadquartersWallet, HeadquartersTransactions, FundTransfers
from .forms import (HQEmployeeRegistrationForm, HQPasswordChangeForm, RoleUserRegistrationForm, 
                   HQAuthenticationForm, RoleForm, UserEditForm, BranchForm, BranchManagerForm, 
                   LoanMainCategoryForm, LoanCategoryForm, LoanInterestForm, LoanTenureForm, DeductionForm, 
                   ProductCategoryForm, ProductSubCategoryForm, ProductForm,
                   SavingTypeForm, OneTimeDepositForm, DailyProductForm,
                   WalletBalanceForm, BranchTransferForm, ChartOfAccountForm, HeadquartersWalletForm,
                   TrialUserCreationForm)

# BranchTransferForm

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .decorators import (
    require_super_admin, require_user_management_access, require_role_management_access,
    require_create_user_permission, require_edit_user_permission, require_delete_user_permission,
    require_branch_management_access, require_permissions_for_class, require_permission
)

from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden
from django.views.decorators.http import require_http_methods
import logging
# from loan.models import LoanApplication, CustomerDetail, DocumentRequest, DocumentReupload, DocumentReview, LoanMainCategory, LoanCategory, LoanInterest, LoanTenure, LoanPeriod, DisbursementLog, Deductions, LoanEMISchedule, LateFeeSetting, LoanCloseRequest, ChartOfAccount
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Sum, Count, F, Case, When, Value, DecimalField, Max
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.template.loader import render_to_string
import asyncio
from django.contrib.admin.models import LogEntry, CHANGE
from django.contrib.contenttypes.models import ContentType
try:
    from playwright.async_api import async_playwright
except ImportError:
    async_playwright = None  # Playwright must be installed
import json
import csv
from io import StringIO
from decimal import Decimal

from savings.models import SavingsAccountApplication, SavingsAgentAssign, SavingsCollection
from loan.models import LoanApplication, CustomerDetail, DocumentRequest, DocumentReupload, DocumentReview, LoanMainCategory, LoanCategory, LoanInterest, LoanTenure, LoanPeriod, DisbursementLog, Deductions, LoanEMISchedule, LateFeeSetting, LoanCloseRequest, ChartOfAccount, ProductCategory, ProductSubCategory, Product, Shop, ShopBankAccount

User = get_user_model()


def _log_loan_action(actor, loan_app, action):
    try:
        if not actor or not getattr(actor, 'is_authenticated', False):
            return

        ct = ContentType.objects.get_for_model(LoanApplication)
        LogEntry.objects.log_action(
            user_id=actor.pk,
            content_type_id=ct.pk,
            object_id=str(loan_app.pk),
            object_repr=str(loan_app),
            action_flag=CHANGE,
            change_message=action,
        )
    except Exception:
        return


@require_permission('loan.view_productcategory')
def product_management(request):
    edit_main_id = (request.GET.get('edit_main') or '').strip()
    edit_sub_id = (request.GET.get('edit_sub') or '').strip()
    edit_product_id = (request.GET.get('edit_product') or '').strip()

    main_category_form = ProductCategoryForm()
    sub_category_form = ProductSubCategoryForm()
    product_form = ProductForm()

    edit_main_form = None
    edit_sub_form = None
    edit_product_form = None

    open_add_main_modal = False
    open_add_sub_modal = False
    open_add_product_modal = False

    if edit_main_id:
        edit_main_obj = ProductCategory.objects.filter(main_category_id=edit_main_id).first()
        if edit_main_obj:
            edit_main_form = ProductCategoryForm(instance=edit_main_obj)

    if edit_sub_id:
        edit_sub_obj = ProductSubCategory.objects.filter(sub_category_id=edit_sub_id).first()
        if edit_sub_obj:
            edit_sub_form = ProductSubCategoryForm(instance=edit_sub_obj)

    if edit_product_id:
        edit_product_obj = Product.objects.filter(product_id=edit_product_id).first()
        if edit_product_obj:
            edit_product_form = ProductForm(instance=edit_product_obj)

    if request.method == 'POST':
        form_type = (request.POST.get('form_type') or '').strip()

        if form_type == 'main_category':
            main_category_form = ProductCategoryForm(request.POST)
            if main_category_form.is_valid():
                obj = main_category_form.save(commit=False)
                obj.created_by = request.user
                obj.save()
                messages.success(request, 'Product category added successfully!')
                return redirect('hq:product_management')
            open_add_main_modal = True
            messages.error(request, 'Failed to add product category. Please check the form.')

        elif form_type == 'main_category_edit':
            target_id = (request.POST.get('edit_id') or '').strip()
            edit_obj = ProductCategory.objects.filter(main_category_id=target_id).first()
            if not edit_obj:
                messages.error(request, 'Main product not found.')
                return redirect('hq:product_management')
            edit_main_form = ProductCategoryForm(request.POST, instance=edit_obj)
            if edit_main_form.is_valid():
                edit_main_form.save()
                messages.success(request, 'Main product updated successfully!')
                return redirect('hq:product_management')
            messages.error(request, 'Failed to update main product. Please check the form.')

        elif form_type == 'main_category_toggle':
            target_id = (request.POST.get('toggle_id') or '').strip()
            obj = ProductCategory.objects.filter(main_category_id=target_id).first()
            if not obj:
                messages.error(request, 'Main product not found.')
                return redirect('hq:product_management')
            obj.is_active = not obj.is_active
            obj.save(update_fields=['is_active', 'updated_at'])
            ProductSubCategory.objects.filter(main_category=obj).update(is_active=obj.is_active)
            Product.objects.filter(sub_category__main_category=obj).update(is_active=obj.is_active)
            messages.success(request, 'Main product status updated successfully!')
            return redirect('hq:product_management')

        elif form_type == 'sub_category':
            sub_category_form = ProductSubCategoryForm(request.POST)
            if sub_category_form.is_valid():
                obj = sub_category_form.save(commit=False)
                obj.created_by = request.user
                obj.save()
                messages.success(request, 'Product sub category added successfully!')
                return redirect('hq:product_management')
            open_add_sub_modal = True
            messages.error(request, 'Failed to add product sub category. Please check the form.')

        elif form_type == 'sub_category_edit':
            target_id = (request.POST.get('edit_id') or '').strip()
            edit_obj = ProductSubCategory.objects.filter(sub_category_id=target_id).first()
            if not edit_obj:
                messages.error(request, 'Product category not found.')
                return redirect('hq:product_management')
            edit_sub_form = ProductSubCategoryForm(request.POST, instance=edit_obj)
            if edit_sub_form.is_valid():
                edit_sub_form.save()
                messages.success(request, 'Product category updated successfully!')
                return redirect('hq:product_management')
            messages.error(request, 'Failed to update product category. Please check the form.')

        elif form_type == 'sub_category_toggle':
            target_id = (request.POST.get('toggle_id') or '').strip()
            obj = ProductSubCategory.objects.filter(sub_category_id=target_id).first()
            if not obj:
                messages.error(request, 'Product category not found.')
                return redirect('hq:product_management')
            obj.is_active = not obj.is_active
            obj.save(update_fields=['is_active', 'updated_at'])
            Product.objects.filter(sub_category=obj).update(is_active=obj.is_active)
            messages.success(request, 'Product category status updated successfully!')
            return redirect('hq:product_management')

        elif form_type == 'product':
            product_form = ProductForm(request.POST)
            if product_form.is_valid():
                obj = product_form.save(commit=False)
                obj.created_by = request.user
                obj.save()
                messages.success(request, 'Product added successfully!')
                return redirect('hq:product_management')
            open_add_product_modal = True
            messages.error(request, 'Failed to add product. Please check the form.')

        elif form_type == 'product_edit':
            target_id = (request.POST.get('edit_id') or '').strip()
            edit_obj = Product.objects.filter(product_id=target_id).first()
            if not edit_obj:
                messages.error(request, 'Product not found.')
                return redirect('hq:product_management')
            edit_product_form = ProductForm(request.POST, instance=edit_obj)
            if edit_product_form.is_valid():
                edit_product_form.save()
                messages.success(request, 'Product updated successfully!')
                return redirect('hq:product_management')
            messages.error(request, 'Failed to update product. Please check the form.')

        elif form_type == 'product_toggle':
            target_id = (request.POST.get('toggle_id') or '').strip()
            obj = Product.objects.filter(product_id=target_id).first()
            if not obj:
                messages.error(request, 'Product not found.')
                return redirect('hq:product_management')
            obj.is_active = not obj.is_active
            obj.save(update_fields=['is_active', 'updated_at'])
            messages.success(request, 'Product status updated successfully!')
            return redirect('hq:product_management')

    main_categories = ProductCategory.objects.select_related('loan_main_category', 'loan_category').all().order_by('name')
    sub_categories = ProductSubCategory.objects.select_related('main_category').all().order_by('main_category__name', 'name')
    products = Product.objects.select_related('sub_category', 'sub_category__main_category').all().order_by(
        'sub_category__main_category__name',
        'sub_category__name',
        'name',
    )

    return render(request, 'product-manage/product_management.html', {
        'main_categories': main_categories,
        'sub_categories': sub_categories,
        'products': products,
        'main_category_form': main_category_form,
        'sub_category_form': sub_category_form,
        'product_form': product_form,
        'edit_main_form': edit_main_form,
        'edit_sub_form': edit_sub_form,
        'edit_product_form': edit_product_form,
        'edit_main_id': edit_main_id,
        'edit_sub_id': edit_sub_id,
        'edit_product_id': edit_product_id,
        'open_add_main_modal': open_add_main_modal,
        'open_add_sub_modal': open_add_sub_modal,
        'open_add_product_modal': open_add_product_modal,
    })


class HQDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'hq/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Set default permissions for non-admin users
        if self.request.user.is_superuser:
            context['is_super_admin'] = True
            context['can_access_user_management'] = True
            context['can_access_role_management'] = True
            context['can_create_users'] = True
            context['can_edit_users'] = True
            context['can_delete_users'] = True
        elif isinstance(self.request.user, HeadquarterEmployee):
            # Default permissions for non-admin users
            context['is_super_admin'] = False
            context['can_access_user_management'] = False
            context['can_access_role_management'] = False
            context['can_create_users'] = False
            context['can_edit_users'] = False
            context['can_delete_users'] = False
            
            # Check if user has specific permissions through their role
            if hasattr(self.request.user, 'role') and self.request.user.role:
                context['can_access_user_management'] = self.request.user.role.can_access_user_management(self.request.user)
                context['can_access_role_management'] = self.request.user.role.can_access_role_management(self.request.user)
                context['can_create_users'] = self.request.user.role.can_create_users(self.request.user)
                context['can_edit_users'] = self.request.user.role.can_edit_users(self.request.user)
                context['can_delete_users'] = self.request.user.role.can_delete_users(self.request.user)
                context['is_super_admin'] = self.request.user.role.is_super_admin(self.request.user)
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        # Add HQ approved loan count to context (filtered by user's branches/agents)
        context['hq_approved_count'] = LoanApplication.objects.filter(status='hq_approved').filter(
            Q(branch__in=user_branches) | Q(agent__in=user_agents)
        ).count()
        # context['loan_applications'] = LoanApplication.objects.all()
        context['pending_loan_count'] = LoanApplication.objects.filter(status='branch_approved').filter(
            Q(branch__in=user_branches) | Q(agent__in=user_agents)
        ).count()
        return context

class HQHomeView(TemplateView):
    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('hq:dashboard')
        return redirect('hq:login')

@require_permissions_for_class('view_agent')
class HQAgentListView(LoginRequiredMixin, TemplateView):
    template_name = 'agent/agent-list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from django.core.paginator import Paginator

        branch_id = (self.request.GET.get('branch_id') or '').strip()
        status_filter = (self.request.GET.get('status') or 'active').strip().lower()
        q = (self.request.GET.get('q') or '').strip()

        # Filter agents from branches created by the logged-in HQ employee
        agents_qs = Agent.objects.select_related('branch').filter(branch__created_by=self.request.user)
        if status_filter == 'active':
            agents_qs = agents_qs.filter(status='active')
        elif status_filter == 'inactive':
            agents_qs = agents_qs.filter(status='inactive')
        else:
            status_filter = 'all'

        if branch_id:
            agents_qs = agents_qs.filter(branch_id=branch_id)

        if q:
            agents_qs = agents_qs.filter(
                Q(agent_id__icontains=q)
                | Q(full_name__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(branch__branch_name__icontains=q)
            )

        agents_qs = agents_qs.order_by('branch__branch_name', 'full_name')

        paginator = Paginator(agents_qs, 15)
        page_obj = paginator.get_page(self.request.GET.get('page') or 1)
        try:
            page_links = list(
                paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            page_links = list(paginator.page_range)

        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        query_string = query_params.urlencode()

        context['agents'] = list(page_obj.object_list)
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['page_links'] = page_links
        context['query_string'] = query_string
        context['branches'] = Branch.objects.filter(created_by=self.request.user).order_by('branch_name')
        context['selected_branch_id'] = branch_id
        context['status_filter'] = status_filter
        context['q'] = q
        return context

@require_permissions_for_class('loan.view_customerdetail')
class HQCustomerListView(LoginRequiredMixin, TemplateView):
    template_name = 'customer/customer-list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        from django.core.paginator import Paginator

        q = (self.request.GET.get('q') or '').strip()
        branch_id = (self.request.GET.get('branch_id') or '').strip()
        agent_id = (self.request.GET.get('agent_id') or '').strip()

        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

        qs = CustomerDetail.objects.select_related('branch', 'agent').filter(
            Q(branch__in=user_branches) | Q(agent__in=user_agents)
        )

        if branch_id:
            qs = qs.filter(branch__branch_id=branch_id)

        if agent_id:
            qs = qs.filter(agent_id=agent_id)

        if q:
            qs = qs.filter(
                Q(customer_id__icontains=q)
                | Q(full_name__icontains=q)
                | Q(contact__icontains=q)
                | Q(adhar_number__icontains=q)
                | Q(pan_number__icontains=q)
                | Q(branch__branch_name__icontains=q)
                | Q(agent__full_name__icontains=q)
                | Q(agent__agent_id__icontains=q)
            )

        qs = qs.order_by('-submitted_at')

        paginator = Paginator(qs, 15)
        page_obj = paginator.get_page(self.request.GET.get('page') or 1)
        try:
            page_links = list(
                paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            page_links = list(paginator.page_range)

        query_params = self.request.GET.copy()
        query_params.pop('page', None)
        query_string = query_params.urlencode()

        agents_qs = user_agents.select_related('branch').order_by('full_name')
        if branch_id:
            agents_qs = agents_qs.filter(branch__branch_id=branch_id)

        context['customers'] = list(page_obj.object_list)
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['page_links'] = page_links
        context['query_string'] = query_string

        context['branches'] = user_branches.order_by('branch_name')
        context['agents'] = agents_qs
        context['q'] = q
        context['selected_branch_id'] = branch_id
        context['selected_agent_id'] = agent_id
        return context

@require_permissions_for_class('loan.view_customerdetail')
class HQCustomerDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'customer/customer-detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer_id = self.kwargs.get('customer_id')

        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

        customer = get_object_or_404(
            CustomerDetail.objects.filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).select_related('address', 'account', 'branch', 'agent'),
            customer_id=customer_id,
        )

        loan_applications = (
            LoanApplication.objects
            .filter(customer=customer)
            .annotate(
                loan_amount=Max('loan_details__loan_amount'),
                emi_amount=Max('loan_details__emi_amount'),
                disbursed_total=Sum('disbursement_logs__amount'),
            )
            .select_related('branch', 'agent')
            .order_by('-submitted_at')
        )

        savings_accounts = (
            SavingsAccountApplication.objects
            .filter(customer=customer)
            .select_related('branch', 'agent')
            .order_by('-submitted_at')
        )

        context['customer'] = customer
        context['loan_applications'] = loan_applications
        context['savings_accounts'] = savings_accounts
        return context

@require_permissions_for_class('view_agent')
class HQAgentDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'agent/agent-detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = self.kwargs.get('agent_id')
        agent = get_object_or_404(Agent.objects.select_related('branch'), agent_id=agent_id)
        context['agent'] = agent

        from decimal import Decimal
        from django.utils import timezone
        from django.db.models import Sum
        from loan.models import LoanApplication, EmiCollectionDetail, EmiAgentAssign, LoanEMISchedule

        loans_qs = LoanApplication.objects.filter(agent=agent)

        from_date_str = (self.request.GET.get('from_date') or '').strip()
        to_date_str = (self.request.GET.get('to_date') or '').strip()
        from_date = parse_date(from_date_str) if from_date_str else None
        to_date = parse_date(to_date_str) if to_date_str else None
        context['from_date'] = from_date_str
        context['to_date'] = to_date_str

        if from_date:
            loans_qs = loans_qs.filter(submitted_at__date__gte=from_date)
        if to_date:
            loans_qs = loans_qs.filter(submitted_at__date__lte=to_date)

        context['loans_assigned_count'] = loans_qs.count()
        context['loans_active_count'] = loans_qs.filter(status='disbursed_fund_released').count()

        collections_qs = EmiCollectionDetail.objects.filter(collected_by_agent=agent)
        if from_date:
            collections_qs = collections_qs.filter(collected_at__date__gte=from_date)
        if to_date:
            collections_qs = collections_qs.filter(collected_at__date__lte=to_date)

        collected_qs = collections_qs.filter(collected=True)
        context['emi_collections_count'] = collected_qs.count()
        context['emi_collections_amount'] = (
            collected_qs.aggregate(total=Sum(F('amount_received') + F('penalty_received')))['total']
            or Decimal('0.00')
        )

        pending_verify_qs = collected_qs.filter(status='collected')
        context['emi_pending_verify_count'] = pending_verify_qs.count()
        context['emi_pending_verify_amount'] = (
            pending_verify_qs.aggregate(total=Sum(F('amount_received') + F('penalty_received')))['total']
            or Decimal('0.00')
        )

        active_assignments_qs = EmiAgentAssign.objects.filter(agent=agent, is_active=True)
        if from_date:
            active_assignments_qs = active_assignments_qs.filter(installment_date__gte=from_date)
        if to_date:
            active_assignments_qs = active_assignments_qs.filter(installment_date__lte=to_date)
        context['assigned_emi_count'] = active_assignments_qs.count()
        context['assigned_emi_amount'] = (
            active_assignments_qs.aggregate(total=Sum('installment_amount'))['total']
            or Decimal('0.00')
        )

        today = timezone.localdate()

        pending_assigned_qs = active_assignments_qs.filter(
            Q(emi__paid=False) | Q(reschedule_emi__paid=False)
        )
        context['assigned_pending_emi_count'] = pending_assigned_qs.count()
        context['assigned_pending_emi_amount'] = (
            pending_assigned_qs.aggregate(total=Sum('installment_amount'))['total']
            or Decimal('0.00')
        )

        overdue_assigned_qs = pending_assigned_qs.filter(installment_date__lt=today)
        context['assigned_overdue_emi_count'] = overdue_assigned_qs.count()
        context['assigned_overdue_emi_amount'] = (
            overdue_assigned_qs.aggregate(total=Sum('installment_amount'))['total']
            or Decimal('0.00')
        )

        due_emis_qs = LoanEMISchedule.objects.filter(
            loan_application__agent=agent,
            paid=False,
        )
        if from_date:
            due_emis_qs = due_emis_qs.filter(installment_date__gte=from_date)
        if to_date:
            due_emis_qs = due_emis_qs.filter(installment_date__lte=to_date)
        context['emi_due_count'] = due_emis_qs.count()
        context['emi_due_amount'] = (
            due_emis_qs.aggregate(total=Sum('installment_amount'))['total']
            or Decimal('0.00')
        )

        overdue_emis_qs = due_emis_qs.filter(installment_date__lt=today)
        context['emi_overdue_count'] = overdue_emis_qs.count()
        context['emi_overdue_amount'] = (
            overdue_emis_qs.aggregate(total=Sum('installment_amount'))['total']
            or Decimal('0.00')
        )

        savings_qs = SavingsAccountApplication.objects.filter(agent=agent)
        if from_date:
            savings_qs = savings_qs.filter(submitted_at__date__gte=from_date)
        if to_date:
            savings_qs = savings_qs.filter(submitted_at__date__lte=to_date)
        context['savings_total_count'] = savings_qs.count()
        rd_qs = savings_qs.filter(product_type='rd')
        fd_qs = savings_qs.filter(product_type='fd')
        context['savings_rd_count'] = rd_qs.count()
        context['savings_fd_count'] = fd_qs.count()
        context['savings_rd_amount'] = (
            rd_qs.aggregate(total=Sum('installment_amount'))['total']
            or Decimal('0.00')
        )
        context['savings_fd_amount'] = (
            fd_qs.aggregate(total=Sum('installment_amount'))['total']
            or Decimal('0.00')
        )

        savings_assignments_qs = (
            SavingsAgentAssign.objects
            .filter(agent=agent, is_active=True)
            .select_related('account', 'account__customer')
            .order_by('-assigned_at')
        )
        if from_date:
            savings_assignments_qs = savings_assignments_qs.filter(assigned_at__date__gte=from_date)
        if to_date:
            savings_assignments_qs = savings_assignments_qs.filter(assigned_at__date__lte=to_date)
        context['savings_assigned_active_count'] = savings_assignments_qs.count()
        context['savings_assigned_rd_count'] = savings_assignments_qs.filter(account__product_type='rd').count()
        context['savings_assigned_fd_count'] = savings_assignments_qs.filter(account__product_type='fd').count()
        recent_assigned_accounts_qs = (
            SavingsAccountApplication.objects
            .filter(agent_assignments__agent=agent, agent_assignments__is_active=True)
            .select_related('customer')
            .order_by('-submitted_at')
            .distinct()
        )
        if from_date:
            recent_assigned_accounts_qs = recent_assigned_accounts_qs.filter(
                agent_assignments__assigned_at__date__gte=from_date
            )
        if to_date:
            recent_assigned_accounts_qs = recent_assigned_accounts_qs.filter(
                agent_assignments__assigned_at__date__lte=to_date
            )

        from django.core.paginator import Paginator

        savings_page_number = (self.request.GET.get('s_page') or '').strip() or 1
        savings_paginator = Paginator(recent_assigned_accounts_qs, 10)
        savings_page_obj = savings_paginator.get_page(savings_page_number)
        try:
            savings_page_links = list(
                savings_paginator.get_elided_page_range(
                    savings_page_obj.number, on_each_side=2, on_ends=1
                )
            )
        except Exception:
            savings_page_links = list(savings_paginator.page_range)

        savings_query_params = self.request.GET.copy()
        savings_query_params.pop('s_page', None)
        savings_query_string = savings_query_params.urlencode()

        context['savings_page_obj'] = savings_page_obj
        context['savings_paginator'] = savings_paginator
        context['savings_page_links'] = savings_page_links
        context['savings_query_string'] = savings_query_string

        recent_savings_assigned_accounts = list(savings_page_obj.object_list)

        account_ids = [a.application_id for a in recent_savings_assigned_accounts]
        if account_ids:
            savings_collection_totals = (
                SavingsCollection.objects
                .filter(account_id__in=account_ids, is_collected=True)
                .filter(
                    Q(collection_date__gte=from_date) if from_date else Q()
                )
                .filter(
                    Q(collection_date__lte=to_date) if to_date else Q()
                )
                .values('account_id')
                .annotate(
                    total_amount=Sum('amount'),
                    interest_amount=Sum(
                        Case(
                            When(collection_type='interest', then=F('amount')),
                            default=Value(0),
                            output_field=DecimalField(max_digits=12, decimal_places=2),
                        )
                    ),
                )
            )
            totals_by_account = {
                row['account_id']: {
                    'total_amount': row.get('total_amount') or Decimal('0.00'),
                    'interest_amount': row.get('interest_amount') or Decimal('0.00'),
                }
                for row in savings_collection_totals
            }
        else:
            totals_by_account = {}

        for acc in recent_savings_assigned_accounts:
            totals = totals_by_account.get(acc.application_id) or {}
            total_amount = totals.get('total_amount') or Decimal('0.00')
            interest_amount = totals.get('interest_amount') or Decimal('0.00')
            collected_amount = total_amount - interest_amount

            acc.collected_amount = collected_amount
            acc.interest_amount = interest_amount
            acc.total_with_interest = total_amount

        context['recent_savings_assigned_accounts'] = recent_savings_assigned_accounts

        return context

class ProfileView(TemplateView):
    template_name = 'hq/profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

class HQLogin(LoginView):
    template_name = 'hq/login.html'
    redirect_authenticated_user = True
    form_class = HQAuthenticationForm
    
    def get_success_url(self):
        # return reverse_lazy('hq:dashboard')
        # Get the 'next' parameter from the URL, default to dashboard
        return self.request.GET.get('next', reverse_lazy('hq:dashboard'))
    
    def get(self, request, *args, **kwargs):
        # Ensure CSRF token is available
        return super().get(request, *args, **kwargs)
    
    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        # Add a success message so dashboard shows a success toast
        messages.success(self.request, 'Login successful.')
        return super().form_valid(form)

    def form_invalid(self, form):
        """If the form is invalid, render the invalid form."""
        return super().form_invalid(form)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def render_to_response(self, context, **response_kwargs):
        # Ensure CSRF token is available in the response
        return super().render_to_response(context, **response_kwargs)

class HQLogoutView(LoginRequiredMixin, TemplateView):
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
        return redirect('hq:login')

class CreateTrialUserView(LoginRequiredMixin, View):
    """View for creating trial users with custom email and duration"""
    template_name = 'hq/create_trial_user.html'
    
    def get(self, request):
        form = TrialUserCreationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = TrialUserCreationForm(request.POST)
        if form.is_valid():
            try:
                trial_user, trial_password = form.create_trial_user()
                messages.success(request, f'Trial user created successfully! Email: {trial_user.email}, Password: {trial_password}')
                return redirect('hq:create_trial_user')
            except Exception as e:
                messages.error(request, f'Error creating trial user: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
        
        return render(request, self.template_name, {'form': form})

#==========================================================================================
#                                 ROLE OPERATIONS STARTS                                  #
#==========================================================================================

# @method_decorator(require_role_management_access, name='dispatch')
@require_permissions_for_class('headquater.view_role')
class RoleManagementView(LoginRequiredMixin, View):
    template_name = 'rollmanage/role_management.html'

    def get(self, request):
        form = RoleForm()
        roles = Role.objects.all()
        return render(request, self.template_name, {
            'form': form,
            'roles': roles
        })

    def post(self, request):
        form = RoleForm(request.POST)
        if form.is_valid():
            role = form.save()
            messages.success(request, f'Role {role.name} has been created successfully.')
            return redirect('hq:role_management')
        roles = Role.objects.all()
        return render(request, self.template_name, {
            'form': form,
            'roles': roles
        })

# def permission_denied_view(request, exception=None):
#     return render(request, 'hq/403.html', {
#         'title': 'Access Denied',
#         'message': str(exception) if exception else 'You do not have permission to access this page.'
#     }, status=403)

# def check_headquarters_admin(user):
#     if not isinstance(user, HeadquarterEmployee):
#         raise PermissionDenied(
#             "You must be a HeadquarterEmployee user to access this page. "
#             "Please contact the administrator to convert your account."
#         )
#     if not user.is_headquater_admin:
#         raise PermissionDenied(
#             "You must be a HeadquarterEmployee admin to access this page. "
#             "Please contact the administrator to grant you admin privileges."
#         )

@require_permission('headquater.add_role')
def create_role(request):
    if request.method == 'POST':
        form = RoleForm(request.POST)
        if form.is_valid():
            role = form.save()
            messages.success(request, f'Role {role.name} has been created successfully.')
            return redirect('hq:role_management')
    else:
        form = RoleForm()
    
    return render(request, 'rollmanage/role_form.html', {
        'form': form,
        'title': 'Create New Role'
    })

@require_permission('headquater.change_role')
def edit_role(request, role_id):
    role = get_object_or_404(Role, id=role_id)
    if request.method == 'POST':
        form = RoleForm(request.POST, instance=role)
        if form.is_valid():
            form.save()
            messages.success(request, f'Role {role.name} has been updated successfully.')
            return redirect('hq:role_management')
    else:
        form = RoleForm(instance=role)
    
    return render(request, 'rollmanage/role_form.html', {
        'form': form,
        'title': f'Edit Role: {role.name}'
    })

@require_permission('headquater.view_role')
def role_list(request):
    roles = Role.objects.all()
    return render(request, 'rollmanage/role_management.html', {
        'roles': roles,
        'title': 'Role List'
    })

## for user management ##
# @require_user_management_access
@require_permission('headquater.view_headquarteremployee')
def user_list(request):
    users = HeadquarterEmployee.objects.all()
    roles = Role.objects.all()
    return render(request, 'userAuth/user.html', {
        'users': users,
        'roles': roles,
        'title': 'User List'
    })

# @require_create_user_permission
@require_permission('headquater.add_headquarteremployee')
def add_user(request):
    roles = Role.objects.all()
    return render(request, 'userAuth/user_form.html', {
        'roles': roles,
        'title': 'Add New User'
    })

# @require_create_user_permission
# @require_permission('headquater.add_headquarteremployee')
def register_role_user(request):

    roles = Role.objects.all()

    if request.method == 'POST':
        form = RoleUserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'User {user.username} has been registered successfully.')
            
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'User {user.username} has been registered successfully.',
                    'redirect_url': reverse_lazy('hq:user_management')
                })
            return redirect('hq:user_management')
        else:        
            # If form is invalid and it's an AJAX request, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
            # For regular form submission, render the form with errors
            return render(request, 'userAuth/user_form.html', {
                'roles': roles,
                'form': form,
                'title': 'Register New User'
            })
    else:
        form = RoleUserRegistrationForm()
    
    return render(request, 'hq/register_role_user.html', {
        'form': form,
        'title': 'Register New User'
    })

def photo_update(request, user_id):
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Method not allowed.'
        }, status=405)

    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'message': 'Not logged in.'}, status=401)

    employee_id = request.user.id

    photo_file = request.FILES.get('photo')
    if not photo_file:
        return JsonResponse({'success': False, 'message': 'No photo provided.'}, status=400)

    try:
        employee = HeadquarterEmployee.objects.get(id=employee_id)
    except HeadquarterEmployee.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Employee not found.'}, status=404)

    employee.image = photo_file
    employee.save(update_fields=['image'])

    if getattr(employee, 'image', None):
        try:
            photo_url = employee.image.url
        except ValueError:
            photo_url = None
    else:
        photo_url = None

    return redirect('hq:profile')
#==========================================================================================
#                                 ROLE OPERATIONS ENDS                                    #
#==========================================================================================

#==========================================================================================
#                                 USER OPERATIONS STARTS                                  #
#==========================================================================================

# @require_edit_user_permission
@require_permission('headquater.change_headquarteremployee')
def edit_user(request, user_id):
    user = get_object_or_404(HeadquarterEmployee, id=user_id)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.username} has been updated successfully.')
            
            # Check if it's an AJAX request
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f'User {user.username} has been updated successfully.',
                    'redirect_url': reverse_lazy('hq:user_management')
                })
            return redirect('hq:user_management')
        else:
            # If form is invalid and it's an AJAX request, return JSON response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
            # For regular form submission, render the form with errors
            return render(request, 'hq/register_role_user.html', {
                'form': form,
                'title': f'Edit User: {user.username}'
            })
    else:
        form = UserEditForm(instance=user)
        roles = Role.objects.all()
    
    return render(request, 'userAuth/user_form.html', {
        'form': form,
        'roles': roles,
        'title': f'Edit User: {user.username}'
    })


@require_permission('headquater.change_headquarteremployee')
def update_user(request, user_id):
    """Update only first_name, last_name, and phone_number for the given user.

    Expects POST fields: firstName, lastName, phone (from profile form).
    """
    user = get_object_or_404(HeadquarterEmployee, id=user_id)

    if request.method == 'POST':
        # Read fields from the simple profile form
        first_name = request.POST.get('firstName', '').strip()
        last_name = request.POST.get('lastName', '').strip()
        phone = request.POST.get('phone', '').strip()

        # Basic required validation (you can relax this if needed)
        errors = {}
        if not first_name:
            errors['firstName'] = 'First name is required.'
        if not last_name:
            errors['lastName'] = 'Last name is required.'

        if errors:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': errors})
            # For non-AJAX, just reload profile page with a message
            messages.error(request, 'Please fill in all required fields.')
            return redirect('hq:profile')

        # Apply updates
        user.first_name = first_name
        user.last_name = last_name
        user.phone_number = phone
        user.save()

        messages.success(request, f'User {user.username} has been updated successfully.')

        # Check if it's an AJAX request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f'User {user.username} has been updated successfully.',
                'redirect_url': reverse_lazy('hq:user_management')
            })

        # For normal POST, go back to profile or user management as desired
        return redirect('hq:profile')

    # For non-POST methods, redirect to profile
    return redirect('hq:profile')


# @require_edit_user_permission
# @require_permission('change_headquarteremployee')
# def get_user_data(request, user_id):
#     """Get user data for edit modal via AJAX"""
#     user = get_object_or_404(HeadquarterEmployee, id=user_id)
#     roles = Role.objects.all()
    
#     user_data = {
#         'id': user.id,
#         'username': user.username,
#         'email': user.email,
#         'phone_number': user.phone_number or '',
#         'address': user.address or '',
#         'role_id': user.role.id if user.role else '',
#         'is_active': user.is_active,
#     }
    
#     roles_data = [{'id': role.id, 'name': role.name} for role in roles]
    
#     return JsonResponse({
#         'success': True,
#         'user': user_data,
#         'roles': roles_data
#     })

# @require_delete_user_permission
@require_permission('headquater.delete_headquarteremployee')
def delete_user(request, user_id):
    """Delete user via AJAX"""
    user = get_object_or_404(HeadquarterEmployee, id=user_id)
    
    # Prevent deleting the current user
    if user == request.user:
        return JsonResponse({
            'success': False,
            'message': 'You cannot delete your own account.'
        })
    
    # Prevent deleting superusers (optional security measure)
    if user.is_superuser and not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'message': 'You cannot delete superuser accounts.'
        })
    
    try:
        username = user.username
        # Soft delete: mark inactive instead of deleting the record
        user.is_active = False
        user.save(update_fields=['is_active'])
        
        return JsonResponse({
            'success': True,
            'message': f'User {username} has been deactivated successfully.',
            'redirect_url': reverse_lazy('hq:user_management')
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error deleting user: {str(e)}'
        })


@require_permission('headquater.view_headquarteremployee')
@require_http_methods(["GET"])
def user_activity_summary(request, user_id):
    """Return a summary of activities related to a user for confirmation before deactivation."""
    user = get_object_or_404(HeadquarterEmployee, id=user_id)


    def qs_preview(qs, limit=10):
        return [str(obj) for obj in qs[:limit]]

    activities = []

    loan_categories_qs = LoanCategory.objects.filter(created_by=user).order_by('-created_at')
    activities.append({
        'title': 'Loan Categories Created',
        'count': loan_categories_qs.count(),
        'items': qs_preview(loan_categories_qs),
    })

    loan_interests_qs = LoanInterest.objects.filter(created_by=user).order_by('-created_at')
    activities.append({
        'title': 'Loan Interests Created',
        'count': loan_interests_qs.count(),
        'items': qs_preview(loan_interests_qs),
    })

    loan_tenures_qs = LoanTenure.objects.filter(created_by=user).order_by('-created_at')
    activities.append({
        'title': 'Loan Tenures Created',
        'count': loan_tenures_qs.count(),
        'items': qs_preview(loan_tenures_qs),
    })

    deductions_created_qs = Deductions.objects.filter(created_by=user).order_by('-created_at')
    activities.append({
        'title': 'Deductions Created',
        'count': deductions_created_qs.count(),
        'items': qs_preview(deductions_created_qs),
    })

    deductions_updated_qs = Deductions.objects.filter(updated_by=user).order_by('-updated_at')
    activities.append({
        'title': 'Deductions Updated',
        'count': deductions_updated_qs.count(),
        'items': qs_preview(deductions_updated_qs),
    })

    late_fee_qs = LateFeeSetting.objects.filter(created_by=user).order_by('-created_at')
    activities.append({
        'title': 'Late Fee Settings Created',
        'count': late_fee_qs.count(),
        'items': qs_preview(late_fee_qs),
    })

    doc_req_qs = DocumentRequest.objects.filter(requested_by_hq=user).order_by('-requested_at')
    activities.append({
        'title': 'Document Requests Raised',
        'count': doc_req_qs.count(),
        'items': [
            f"{dr.get_document_type_display()} - {dr.loan_application_id or 'N/A'}" for dr in doc_req_qs[:10]
        ],
    })

    branches_qs = Branch.objects.filter(created_by=user).order_by('-created_at')
    activities.append({
        'title': 'Branches Created',
        'count': branches_qs.count(),
        'items': qs_preview(branches_qs),
    })

    activities = [a for a in activities if a.get('count', 0) > 0]

    loan_ct = ContentType.objects.get_for_model(LoanApplication)
    base_loan_logs = LogEntry.objects.filter(user_id=user.pk, content_type_id=loan_ct.pk)
    approved_logs = base_loan_logs.filter(change_message='loan_hq_approved').order_by('-action_time')
    rejected_logs = base_loan_logs.filter(change_message='loan_hq_rejected').order_by('-action_time')
    disbursed_logs = base_loan_logs.filter(change_message='loan_hq_disbursed').order_by('-action_time')

    return JsonResponse({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'name': user.get_full_name() or user.username,
            'email': getattr(user, 'email', '') or '',
            'role': (user.get_role_name() if hasattr(user, 'get_role_name') else '') or '',
            'is_active': bool(user.is_active),
        },
        'loan_stats': {
            'hq_approved': {
                'count': approved_logs.count(),
                'items': [l.object_repr for l in approved_logs[:5]],
            },
            'hq_rejected': {
                'count': rejected_logs.count(),
                'items': [l.object_repr for l in rejected_logs[:5]],
            },
            'disbursed_fund_released': {
                'count': disbursed_logs.count(),
                'items': [l.object_repr for l in disbursed_logs[:5]],
            },
        },
        'activities': activities,
    })

@require_permission('headquater.change_headquarteremployee')
@require_http_methods(["POST"])
def toggle_user_active(request, user_id):
    """Toggle user active/inactive (soft delete)."""
    user = get_object_or_404(HeadquarterEmployee, id=user_id)

    if user == request.user:
        return JsonResponse({
            'success': False,
            'message': 'You cannot deactivate your own account.'
        })

    if user.is_superuser and not request.user.is_superuser:
        return JsonResponse({
            'success': False,
            'message': 'You cannot change the status of superuser accounts.'
        })

    desired = request.POST.get('is_active')
    if desired is None:
        new_value = not bool(user.is_active)
    else:
        new_value = str(desired).lower() in ('1', 'true', 'yes', 'on')

    user.is_active = new_value
    user.save(update_fields=['is_active'])

    return JsonResponse({
        'success': True,
        'message': f"User {user.username} has been {'activated' if user.is_active else 'deactivated'} successfully.",
        'redirect_url': reverse_lazy('hq:user_management')
    })

#==========================================================================================
#                                BRANCH OPERATIONS STARTS                                 #
#==========================================================================================

# @require_permission('headquater.view_branch')
# def branch_list(request):
#     branches = Branch.objects.all()
#     branch_list = []
#     for branch in branches:
#         manager = branch.managers.first()
#         manager_id = manager.manager_id if manager else ''
#         branch_list.append({
#             'branch_id': branch.branch_id,
#             'branch_name': branch.branch_name,
#             'address_line_1': branch.address_line_1 or '',
#             'address_line_2': branch.address_line_2 or '',
#             'city': branch.city or '',
#             'state': branch.state or '',
#             'postal_code': branch.postal_code or '',
#             'country': branch.country or '',
#             'district': branch.district or '',
#             'contact_number': branch.contact_number or '',
#             'email': branch.email or '',
#             'manager_id': manager_id,
#             'status': branch.status,
#         })
#     form = BranchForm()
#     return render(request, 'branch/branch.html', {
#         'branches': branch_list,
#         'form': form,
#         'title': 'Branch List'
#     })

# @require_permission('headquater.view_branch')
# def branch_list(request):
#     branches = Branch.objects.all()
#     branch_list = []
#     for branch in branches:
#         # Get the branch manager (employee where is_manager=True for this branch)
#         manager = branch.employees.filter(is_manager=True).first()
#         manager_name = f"{manager.first_name} {manager.last_name}" if manager else ''
#         manager_id = manager.employee_id if manager else ''
        
#         branch_list.append({
#             'branch_id': branch.branch_id,
#             'branch_name': branch.branch_name,
#             'manager_name': manager_name,  # Added manager's full name
#             'manager_id': manager_id,
#             'address_line_1': branch.address_line_1 or '',
#             'address_line_2': branch.address_line_2 or '',
#             'city': branch.city or '',
#             'state': branch.state or '',
#             'postal_code': branch.postal_code or '',
#             'country': branch.country or '',
#             'district': branch.district or '',
#             'contact_number': branch.contact_number or '',
#             'email': branch.email or '',
#         })


@require_permission('headquater.view_branch')
def branch_list(request):
    from branch.models import BranchEmployee  # Add this import at the top of your file
    # Filter branches by status: active (default), inactive, or all
    status_filter = (request.GET.get('status') or 'active').lower()

    # Filter branches by the logged-in HQ employee (only show branches they created)
    branches = Branch.objects.filter(created_by=request.user).prefetch_related('employees')
    if status_filter == 'active':
        branches = branches.filter(status=True)
    elif status_filter == 'inactive':
        branches = branches.filter(status=False)
    else:
        status_filter = 'all'
    
    branch_list = []
    
    for branch in branches:
        # Get the branch manager (employee where is_manager=True for this branch)
        manager = branch.employees.filter(is_manager=True).first()
        
        branch_list.append({
            'branch_id': branch.branch_id,
            'branch_name': branch.branch_name,
            'manager_name': f"{manager.first_name} {manager.last_name}" if manager else '',
            'manager_id': manager.manager_id if manager else '',
            'address_line_1': branch.address_line_1 or '',
            'address_line_2': branch.address_line_2 or '',
            'city': branch.city or '',
            'state': branch.state or '',
            'postal_code': branch.postal_code or '',
            'country': branch.country or '',
            'district': branch.district or '',
            'contact_number': branch.contact_number or '',
            'email': branch.email or '',
            'status': branch.status  # Added status back as it was in the original code
        })
    
    form = BranchForm()
    return render(request, 'branch/branch.html', {
        'branches': branch_list,
        'form': form,
        'title': 'Branch List',
        'status_filter': status_filter,
    })


@require_permission('headquater.view_branch')
def branch_overview(request, branch_id):
    branch = get_object_or_404(Branch, branch_id=branch_id)
    # All applications for this branch
    loans_qs = LoanApplication.objects.filter(branch__branch_id=branch_id).select_related('customer', 'branch', 'agent')

    # ---- Reporting window (monthly by default; custom via GET) ----
    from datetime import timedelta
    now = timezone.now()
    today = timezone.localdate()
    first_day_this_month = now.replace(day=1).date()

    report_mode = request.GET.get('report_mode', 'monthly')
    date_from_param = request.GET.get('from')
    date_to_param = request.GET.get('to')

    def parse_date_safe(val):
        try:
            return timezone.datetime.fromisoformat(val).date() if val else None
        except Exception:
            try:
                # Fallback for YYYY-MM-DD
                return timezone.datetime.strptime(val, '%Y-%m-%d').date()
            except Exception:
                return None

    if report_mode == 'custom':
        date_from = parse_date_safe(date_from_param) or first_day_this_month
        date_to = parse_date_safe(date_to_param) or today
    else:
        report_mode = 'monthly'
        date_from = first_day_this_month
        date_to = today

    # Constrain core querysets by reporting window where appropriate
    loans_in_window = loans_qs.filter(submitted_at__date__gte=date_from, submitted_at__date__lte=date_to)

    # Basic counts
    total_applications = loans_in_window.count()
    approved_count = loans_in_window.filter(status='hq_approved').count()
    rejected_count = loans_in_window.filter(status='hq_rejected').count()
    active_loans = loans_in_window.filter(status='disbursed_fund_released')
    active_loans_count = active_loans.count()

    # Amount aggregates
    from django.db.models import Sum
    loan_amount_agg = loans_in_window.aggregate(total=Sum('loan_details__loan_amount'))
    total_loan_amount = float(loan_amount_agg['total'] or 0)

    hq_approved_amount = float(
        loans_in_window.filter(status='hq_approved')
        .aggregate(total=Sum('loan_details__loan_amount'))['total'] or 0
    )

    # ---- Daily KPIs (today) ----
    daily_loan_amount = float(
        loans_qs.filter(submitted_at__date=today).aggregate(total=Sum('loan_details__loan_amount'))['total'] or 0
    )
    daily_loan_count = loans_qs.filter(submitted_at__date=today).count()

    daily_hq_approved_loan_amount = float(
        loans_qs.filter(submitted_at__date=today, status='hq_approved')
        .aggregate(total=Sum('loan_details__loan_amount'))['total'] or 0
    )
    daily_hq_approved_loan_count = loans_qs.filter(submitted_at__date=today, status='hq_approved').count()

    # Savings collections/deposits (RD/FD) for this branch (today)
    from savings.models import SavingsCollection
    savings_base_qs = SavingsCollection.objects.filter(
        branch=branch,
        is_collected=True,
    ).filter(
        Q(is_deposited_to_branch=True, deposited_at__isnull=False, deposited_at__date=today) |
        Q(Q(is_deposited_to_branch=False) | Q(deposited_at__isnull=True), collection_date=today)
    )

    daily_savings_rd_collected_amount = float(
        savings_base_qs.filter(account__product_type='rd').aggregate(total=Sum('amount'))['total'] or 0
    )
    daily_savings_fd_collected_amount = float(
        savings_base_qs.filter(account__product_type='fd').aggregate(total=Sum('amount'))['total'] or 0
    )
    daily_savings_collected_amount = daily_savings_rd_collected_amount + daily_savings_fd_collected_amount

    # EMI metrics for this branch
    from loan.models import LoanEMISchedule, DisbursementLog, EmiCollectionDetail
    # Window for scheduled / overdue is based on installment_date
    emi_qs = LoanEMISchedule.objects.filter(
        loan_application__in=loans_qs,
        installment_date__gte=date_from,
        installment_date__lte=date_to,
    )
    totals = emi_qs.aggregate(
        scheduled=Sum('installment_amount'),
        outstanding=Sum('installment_amount', filter=Q(paid=False)),
    )
    total_scheduled = float(totals['scheduled'] or 0)
    outstanding_amount = float(totals['outstanding'] or 0)

    # Collections should match Branch Portal logic (EmiCollectionDetail)
    from datetime import time
    tz = timezone.get_current_timezone()
    window_start_dt = timezone.make_aware(timezone.datetime.combine(date_from, time.min), tz)
    window_end_dt = timezone.make_aware(timezone.datetime.combine(date_to, time.min), tz) + timedelta(days=1)
    collected_totals = EmiCollectionDetail.objects.filter(
        loan_application__in=loans_qs,
        verified_at__gte=window_start_dt,
        verified_at__lt=window_end_dt,
        verified_at__isnull=False,
        collected=True,
        status='verified',
    ).filter(
        Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False)
    ).aggregate(total=Sum('amount_received'))
    collected_amount = float(collected_totals['total'] or 0)

    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(timezone.datetime.combine(today, time.min), tz)
    day_end = day_start + timedelta(days=1)
    daily_collected_amount = float(
        EmiCollectionDetail.objects.filter(
            loan_application__in=loans_qs,
            collected=True,
            status='verified',
            verified_at__isnull=False,
            verified_at__gte=day_start,
            verified_at__lt=day_end,
        ).filter(
            Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False)
        ).aggregate(total=Sum('amount_received'))['total'] or 0
    )

    daily_outstanding_amount = float(
        LoanEMISchedule.objects.filter(
            loan_application__in=loans_qs,
            paid=False,
            installment_date=today,
        ).aggregate(total=Sum('installment_amount'))['total'] or 0
    )

    # EMI status counts and PAR (based on installment_date window)
    upcoming_count = emi_qs.filter(paid=False, installment_date__gt=today).count()
    due_count = emi_qs.filter(paid=False, installment_date=today).count()
    overdue_qs = emi_qs.filter(paid=False, installment_date__lt=today)
    overdue_count = overdue_qs.count()
    par_amount = float(overdue_qs.aggregate(total=Sum('installment_amount'))['total'] or 0)
    par_ratio = (par_amount / outstanding_amount) * 100 if outstanding_amount > 0 else 0.0

    # Total disbursements (sum of DisbursementLog amounts for loans in this branch, filtered by created_at)
    disb_qs = DisbursementLog.objects.filter(loan_id__in=loans_qs, created_at__date__gte=date_from, created_at__date__lte=date_to)
    total_disbursements = float(disb_qs.aggregate(total=Sum('amount'))['total'] or 0)

    # daily_disb_qs = DisbursementLog.objects.filter(
    #     loan_id__in=loans_qs,
    #     created_at__date=today,
    # )
    # daily_disbursed_amount = float(daily_disb_qs.aggregate(total=Sum('amount'))['total'] or 0)
    # daily_disbursed_count = daily_disb_qs.values('loan_id').distinct().count()

    daily_disb_qs = DisbursementLog.objects.filter(
    disbursed_by=branch,
    created_at__gte=day_start,
    created_at__lt=day_end,
    )
    daily_disbursed_amount = float(
        daily_disb_qs.aggregate(total=Sum('amount'))['total'] or 0
    )
    daily_disbursed_net_amount_cust = float(
        daily_disb_qs.aggregate(total=Sum('net_amount_cust'))['total'] or 0
    )
    daily_disbursed_tax_charges = float(
        daily_disb_qs.aggregate(total=Sum('tax_charges'))['total'] or 0
    )
    daily_disbursed_count = daily_disb_qs.values('disbursed_to_id').distinct().count()

    daily_provided_to_branch = float(
        FundTransfers.objects.filter(
            transfer_to=str(branch.branch_id),
            hq_transaction__isnull=False,
            created_at__date=today,
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    daily_collected_from_branch = float(
        FundTransfers.objects.filter(
            branch_transaction__branch=branch,
            created_at__date=today,
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    # Active borrowers (distinct customers with active loans in window)
    active_borrowers = active_loans.values('customer_id').distinct().count()

    agents_qs = Agent.objects.filter(branch=branch)
    total_agents = agents_qs.count()
    active_agents = agents_qs.filter(status='active').count()

    # Repayment rate (for window)
    repayment_rate = (collected_amount / total_scheduled) * 100 if total_scheduled > 0 else 0.0

    # Branch growth vs target (Month-over-Month total disbursements vs previous month) - keep based on calendar months
    first_day_prev_month = (first_day_this_month - timedelta(days=1)).replace(day=1)
    last_day_prev_month = first_day_this_month - timedelta(days=1)

    current_month_disb = float(
        DisbursementLog.objects.filter(loan_id__in=loans_qs, created_at__date__gte=first_day_this_month, created_at__date__lte=today)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    prev_month_disb = float(
        DisbursementLog.objects.filter(loan_id__in=loans_qs, created_at__date__gte=first_day_prev_month, created_at__date__lte=last_day_prev_month)
        .aggregate(total=Sum('amount'))['total'] or 0
    )
    growth_vs_target_pct = ((current_month_disb - prev_month_disb) / prev_month_disb) * 100 if prev_month_disb > 0 else (100.0 if current_month_disb > 0 else 0.0)

    # Funds movement between HQ and Branch (provided vs collected) within window
    provided_to_branch_qs = FundTransfers.objects.filter(
        transfer_to=str(branch.branch_id),
        hq_transaction__isnull=False,
        created_at__date__gte=date_from,
        created_at__date__lte=date_to,
    ).select_related('hq_transaction__wallet', 'branch_account')

    provided_to_branch = float(
        provided_to_branch_qs.aggregate(total=Sum('amount'))['total'] or 0
    )

    hq_wallet_ids = provided_to_branch_qs.filter(
        hq_transaction__wallet__isnull=False
    ).values_list('hq_transaction__wallet__wallet_id', flat=True).distinct()
    
    # HeadquartersWallet primary key is wallet_id, so filter on wallet_id__in
    hq_all_account = HeadquartersWallet.objects.filter(wallet_id__in=hq_wallet_ids)

    branch_all_account = BranchAccount.objects.filter(
        branch=branch,
        transactions__transaction_type='DEBIT',
        transactions__transfer_to_from='Headquarters',
        transactions__transaction_date__date__gte=date_from,
        transactions__transaction_date__date__lte=date_to,
    ).distinct()

    branch_account_balance = float(
        BranchAccount.objects.filter(branch=branch).aggregate(total=Sum('current_balance'))['total'] or 0
    )

    from branch.models import BranchTransaction
    daily_tx_qs = BranchTransaction.objects.filter(
        branch=branch,
        transaction_date__date=today,
    )
    daily_transaction_credit = float(
        daily_tx_qs.filter(transaction_type='CREDIT').aggregate(total=Sum('amount'))['total'] or 0
    )
    daily_transaction_debit = float(
        daily_tx_qs.filter(transaction_type='DEBIT').aggregate(total=Sum('amount'))['total'] or 0
    )
    daily_transaction_net = daily_transaction_credit - daily_transaction_debit

    window_account_qs = BranchTransaction.objects.filter(
        branch=branch,
        transaction_date__date__gte=date_from,
        transaction_date__date__lte=date_to,
    )
    window_account_credit = float(
        window_account_qs.filter(transaction_type='CREDIT').aggregate(total=Sum('amount'))['total'] or 0
    )
    window_account_debit = float(
        window_account_qs.filter(transaction_type='DEBIT').aggregate(total=Sum('amount'))['total'] or 0
    )

    # Map of account.id -> list of branch->HQ transfer transactions for that account
    branch_tx_qs = BranchTransaction.objects.filter(
        branch=branch,
        branch_account__in=branch_all_account,
        transaction_type='DEBIT',
        transfer_to_from='Headquarters',
        transaction_date__date__gte=date_from,
        transaction_date__date__lte=date_to,
    ).select_related('branch_account').order_by('-transaction_date')

    branch_account_tx = {}
    for tx in branch_tx_qs:
        acc_id = str(tx.branch_account_id) if tx.branch_account_id else None
        if not acc_id:
            continue
        branch_account_tx.setdefault(acc_id, []).append({
            'date': tx.transaction_date.strftime('%Y-%m-%d %H:%M'),
            'amount': float(tx.amount or 0),
            'purpose': tx.purpose or '',
            'description': tx.description or '',
            'mode': tx.mode or '',
        })

    collected_from_branch = float(
        FundTransfers.objects.filter(branch_transaction__branch=branch, created_at__date__gte=date_from, created_at__date__lte=date_to)
        .aggregate(total=Sum('amount'))['total'] or 0
    )

    due_amount = max(0, provided_to_branch - collected_from_branch)
    profit_amount = max(0, collected_from_branch - provided_to_branch)

    alt_profit_amount = max(0, collected_amount - total_loan_amount)

    daily_profit_amount = max(0, daily_collected_from_branch - daily_provided_to_branch)
    daily_alt_profit_amount = max(0, daily_collected_amount - daily_loan_amount)

    # Build Overdue Loans detail list for display/export (respect window)
    # We join via LoanEMISchedule back to LoanApplication and related customer/agent
    overdue_emi = LoanEMISchedule.objects.select_related('loan_application__customer', 'loan_application__agent') \
        .filter(loan_application__in=loans_qs, paid=False, installment_date__lt=today, installment_date__gte=date_from)

    overdue_loans = []
    for emi in overdue_emi:
        app = emi.loan_application
        customer_name = getattr(app.customer, 'full_name', '') if app and app.customer else ''
        agent_name = getattr(app.agent, 'full_name', '') if app and app.agent else ''
        contact = getattr(app.customer, 'phone_number', '') if app and app.customer else ''
        days_past_due = (today - emi.installment_date).days
        overdue_loans.append({
            'loan_ref_no': getattr(app, 'loan_ref_no', ''),
            'customer': customer_name,
            'agent': agent_name,
            'contact': contact,
            'installment_date': emi.installment_date,
            'amount_due': float(emi.installment_amount or 0),
            'days_past_due': days_past_due,
        })

    # CSV export for overdue loans
    if request.GET.get('export') == 'overdue_csv':
        csv_buffer = StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(['Loan Ref', 'Customer', 'Agent', 'Contact', 'Installment Date', 'Amount Due', 'Days Past Due'])
        for row in overdue_loans:
            writer.writerow([
                row['loan_ref_no'],
                row['customer'],
                row['agent'],
                row['contact'],
                row['installment_date'].strftime('%Y-%m-%d') if row['installment_date'] else '',
                f"{row['amount_due']:.2f}",
                row['days_past_due'],
            ])
        response = HttpResponse(csv_buffer.getvalue(), content_type='text/csv')
        filename = f"overdue_loans_{branch.branch_id}_{date_from}_{date_to}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    from django.core.paginator import Paginator

    active_apps_qs = loans_qs.order_by('-submitted_at')
    active_apps_page_obj = None
    active_apps_page_links = []
    active_apps_query_params = request.GET.copy()
    active_apps_query_params.pop('a_page', None)
    active_apps_query_string = active_apps_query_params.urlencode()

    active_apps_paginator = Paginator(active_apps_qs, 10)
    active_apps_page_obj = active_apps_paginator.get_page(request.GET.get('a_page') or 1)
    try:
        active_apps_page_links = list(
            active_apps_paginator.get_elided_page_range(
                active_apps_page_obj.number, on_each_side=2, on_ends=1
            )
        )
    except Exception:
        active_apps_page_links = list(active_apps_paginator.page_range)

    # Recent loans list (respect window)
    from django.core.paginator import Paginator

    active_page_number = (request.GET.get('a_page') or '').strip() or 1
    active_qs = loans_qs.order_by('-submitted_at')
    active_paginator = Paginator(active_qs, 10)
    active_page_obj = active_paginator.get_page(active_page_number)
    try:
        active_page_links = list(
            active_paginator.get_elided_page_range(active_page_obj.number, on_each_side=2, on_ends=1)
        )
    except Exception:
        active_page_links = list(active_paginator.page_range)

    active_query_params = request.GET.copy()
    active_query_params.pop('a_page', None)
    active_query_string = active_query_params.urlencode()

    top_agents_page_number = (request.GET.get('t_page') or '').strip() or 1
    top_agents_qs = (
        emi_qs
        .exclude(loan_application__agent_id__isnull=True)
        .values('loan_application__agent_id', 'loan_application__agent__full_name')
        .annotate(loan_count=Count('loan_application_id', distinct=True))
        .order_by('-loan_count')
    )
    top_agents_paginator = Paginator(top_agents_qs, 10)
    top_agents_page_obj = top_agents_paginator.get_page(top_agents_page_number)
    try:
        top_agents_page_links = list(
            top_agents_paginator.get_elided_page_range(
                top_agents_page_obj.number, on_each_side=2, on_ends=1
            )
        )
    except Exception:
        top_agents_page_links = list(top_agents_paginator.page_range)

    top_agents_query_params = request.GET.copy()
    top_agents_query_params.pop('t_page', None)
    top_agents_query_string = top_agents_query_params.urlencode()

    top_active_agents = [
        {
            'agent_id': row['loan_application__agent_id'],
            'agent_name': row['loan_application__agent__full_name'] or '',
            'applications': row['loan_count'] or 0,
        }
        for row in top_agents_page_obj.object_list
    ]

    context = {
        'branch': branch,
        'title': f"Branch Overview • {branch.branch_name}",
        'kpis': {
            'total_applications': total_applications,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'active_loans_count': active_loans_count,
            'total_loan_amount': total_loan_amount,
            'total_scheduled': total_scheduled,
            'collected_amount': collected_amount,
            'outstanding_amount': outstanding_amount,
            'daily_total_loan_amount': daily_loan_amount,
            'daily_collected_amount': daily_collected_amount,
            'daily_outstanding_amount': daily_outstanding_amount,
            'daily_savings_collected_amount': daily_savings_collected_amount,
            'daily_savings_rd_collected_amount': daily_savings_rd_collected_amount,
            'daily_savings_fd_collected_amount': daily_savings_fd_collected_amount,
            'upcoming_count': upcoming_count,
            'due_count': due_count,
            'overdue_count': overdue_count,
            'par_amount': par_amount,
            'par_ratio': round(par_ratio, 2),
            'total_disbursements': total_disbursements,
            'daily_disbursed_amount': daily_disbursed_amount,
            'daily_disbursed_count': daily_disbursed_count,
            'active_borrowers': active_borrowers,
            'repayment_rate': round(repayment_rate, 2),
            'current_month_disb': current_month_disb,
            'prev_month_disb': prev_month_disb,
            'growth_vs_target_pct': round(growth_vs_target_pct, 2),
            'provided_to_branch': provided_to_branch,
            'provided_to_branch_tx': provided_to_branch_qs,
            'branch_all_account': branch_all_account,
            'branch_account_balance': branch_account_balance,
            'daily_transaction_credit': daily_transaction_credit,
            'daily_transaction_debit': daily_transaction_debit,
            'daily_transaction_net': daily_transaction_net,
            'window_account_credit': window_account_credit,
            'window_account_debit': window_account_debit,
            'collected_from_branch': collected_from_branch,
            'hq_all_account': hq_all_account,
            'due_amount': due_amount,
            'profit_amount': profit_amount,
            'alt_profit_amount': alt_profit_amount,
            'daily_profit_amount': daily_profit_amount,
            'daily_alt_profit_amount': daily_alt_profit_amount,
        },
        'recent_active_applications': list(active_page_obj.object_list),
        'active_page_obj': active_page_obj,
        'active_paginator': active_paginator,
        'active_page_links': active_page_links,
        'active_query_string': active_query_string,
        'top_active_agents': top_active_agents,
        'top_agents_page_obj': top_agents_page_obj,
        'top_agents_paginator': top_agents_paginator,
        'top_agents_page_links': top_agents_page_links,
        'top_agents_query_string': top_agents_query_string,
    }

    # Build chart series for Disbursements vs Collections per day in window
    def date_iter(start, end):
        cur = start
        while cur <= end:
            yield cur
            cur += timedelta(days=1)

    # Map disbursements per day
    disb_by_date = {
        d['created_at__date']: float(d['total'] or 0)
        for d in disb_qs.values('created_at__date').annotate(total=Sum('amount')).order_by('created_at__date')
    }
    # Collections per day by verified_at within window (match KPI rules)
    coll_source_qs = EmiCollectionDetail.objects.filter(
        loan_application__in=loans_qs,
        verified_at__gte=window_start_dt,
        verified_at__lt=window_end_dt,
        verified_at__isnull=False,
        collected=True,
        status='verified',
    ).filter(
        Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False)
    )
    coll_by_date = {
        d['verified_at__date']: float(d['total'] or 0)
        for d in coll_source_qs.values('verified_at__date').annotate(total=Sum('amount_received')).order_by('verified_at__date')
    }
    # Scheduled per day (total installment_amount scheduled for that date)
    sched_by_date = {
        d['installment_date']: float(d['total'] or 0)
        for d in emi_qs.values('installment_date').annotate(total=Sum('installment_amount')).order_by('installment_date')
    }
    chart_dates = [d.strftime('%Y-%m-%d') for d in date_iter(date_from, date_to)]
    disb_series = [disb_by_date.get(d, 0.0) for d in [timezone.datetime.fromisoformat(x).date() for x in chart_dates]]
    coll_series = [coll_by_date.get(d, 0.0) for d in [timezone.datetime.fromisoformat(x).date() for x in chart_dates]]
    sched_series = [sched_by_date.get(d, 0.0) for d in [timezone.datetime.fromisoformat(x).date() for x in chart_dates]]

    # PAR trend for last 6 months (end with current month)
    par_month_labels = []
    par_month_values = []
    anchor = first_day_this_month
    for i in range(5, -1, -1):
        # month start and end
        month_start = (anchor - timedelta(days=1)).replace(day=1) if i == 5 else None
    # Calculate each month start/end
    from calendar import monthrange
    def month_bounds(dt):
        start = dt.replace(day=1)
        last_day = monthrange(dt.year, dt.month)[1]
        end = dt.replace(day=last_day)
        return start, end
    # Build labels/values
    cur = first_day_this_month
    months = []
    for k in range(5, -1, -1):
        # Move back k months
        y = cur.year
        m = cur.month - k
        while m <= 0:
            m += 12
            y -= 1
        dt = cur.replace(year=y, month=m, day=1)
        start_m, end_m = month_bounds(dt)
        months.append((start_m, end_m))
        par_month_labels.append(dt.strftime('%b %Y'))
    for start_m, end_m in months:
        emi_month = LoanEMISchedule.objects.filter(
            loan_application__in=loans_qs,
            installment_date__gte=start_m,
            installment_date__lte=end_m,
        )
        
        outstanding_m = float(emi_month.aggregate(total=Sum('installment_amount', filter=Q(paid=False)))['total'] or 0)
        overdue_m = float(emi_month.aggregate(total=Sum('installment_amount', filter=Q(paid=False, installment_date__lt=end_m)))['total'] or 0)
        par_val = (overdue_m / outstanding_m) * 100 if outstanding_m > 0 else 0.0
        par_month_values.append(round(par_val, 2))

    # Application funnel (counts by stages)
    # Keep branch-specific, but align each stage with its event date within the selected reporting window.
    applied_count = loans_qs.filter(submitted_at__date__gte=date_from, submitted_at__date__lte=date_to).count()
    reviewed_count = loans_qs.filter(
        submitted_at__date__gte=date_from,
        submitted_at__date__lte=date_to,
    ).filter(
        Q(status__icontains='review')
        | Q(status__icontains='branch_approved')
        | Q(status__icontains='hq_approved')
        | Q(status__icontains='document')
        | Q(status__icontains='resubmitted')
    ).count()
    approved_total = loans_qs.filter(
        approved_at__date__gte=date_from,
        approved_at__date__lte=date_to,
        status__in=['hq_approved', 'disbursed', 'disbursed_fund_released'],
    ).count()
    disbursed_total = loans_qs.filter(
        disbursed_at__date__gte=date_from,
        disbursed_at__date__lte=date_to,
        status__in=['disbursed', 'disbursed_fund_released'],
    ).count()

    charts_payload = {
        'dates': chart_dates,
        'disbursements': disb_series,
        'scheduled': sched_series,
        'collections': coll_series,
        'par': {
            'labels': par_month_labels,
            'values': par_month_values,
        },
        'funnel': {
            'labels': ['Applied', 'Reviewed', 'Approved', 'Disbursed'],
            'values': [applied_count, reviewed_count, approved_total, disbursed_total],
        }
    }

    recent_loans = [
        {
            'loan_ref_no': loan.loan_ref_no,
            'customer_name': getattr(loan.customer, 'full_name', '') if loan.customer else '',
            'status': loan.status,
            'submitted_at': loan.submitted_at.strftime('%Y-%m-%d %H:%M') if loan.submitted_at else '',
        }
        for loan in loans_qs.order_by('-submitted_at')[:5]
    ]

    context = {
        'branch': branch,
        'title': f"Branch Overview • {branch.branch_name}",
        'kpis': {
            'total_applications': total_applications,
            'approved_count': approved_count,
            'rejected_count': rejected_count,
            'active_loans_count': active_loans_count,
            'active_borrowers': active_borrowers,
            'total_loan_amount': total_loan_amount,
            'hq_approved_loan_amount': hq_approved_amount,
            'hq_approved_loan_count': approved_count,
            'total_scheduled': total_scheduled,
            'collected_amount': collected_amount,
            'outstanding_amount': outstanding_amount,
            'daily_total_loan_amount': daily_loan_amount,
            'daily_total_loan_count': daily_loan_count,
            'daily_hq_approved_loan_amount': daily_hq_approved_loan_amount,
            'daily_hq_approved_loan_count': daily_hq_approved_loan_count,
            'daily_collected_amount': daily_collected_amount,
            'daily_outstanding_amount': daily_outstanding_amount,
            'daily_savings_collected_amount': daily_savings_collected_amount,
            'daily_savings_rd_collected_amount': daily_savings_rd_collected_amount,
            'daily_savings_fd_collected_amount': daily_savings_fd_collected_amount,
            'upcoming_count': upcoming_count,
            'due_count': due_count,
            'overdue_count': overdue_count,
            'par_amount': par_amount,
            'par_ratio': round(par_ratio, 2),
            'total_disbursements': total_disbursements,
            'daily_disbursed_amount': daily_disbursed_amount,
            'daily_disbursed_net_amount_cust': daily_disbursed_net_amount_cust,
            'daily_disbursed_tax_charges': daily_disbursed_tax_charges,
            'daily_disbursed_count': daily_disbursed_count,
            'active_borrowers': active_borrowers,
            'repayment_rate': round(repayment_rate, 2),
            'current_month_disb': current_month_disb,
            'prev_month_disb': prev_month_disb,
            'growth_vs_target_pct': round(growth_vs_target_pct, 2),
            'provided_to_branch': provided_to_branch,
            'provided_to_branch_tx': provided_to_branch_qs,
            'branch_all_account': branch_all_account,
            'branch_account_balance': branch_account_balance,
            'daily_transaction_credit': daily_transaction_credit,
            'daily_transaction_debit': daily_transaction_debit,
            'daily_transaction_net': daily_transaction_net,
            'window_account_credit': window_account_credit,
            'window_account_debit': window_account_debit,
            'collected_from_branch': collected_from_branch,
            'hq_all_account': hq_all_account,
            'due_amount': due_amount,
            'profit_amount': profit_amount,
            'alt_profit_amount': alt_profit_amount,
            'daily_profit_amount': daily_profit_amount,
            'daily_alt_profit_amount': daily_alt_profit_amount,
        },
        'recent_loans': recent_loans,
        'total_agents': total_agents,
        'active_agents': active_agents,
        'report_mode': report_mode,
        'date_from': date_from,
        'date_to': date_to,
        'overdue_loans': overdue_loans,
        'overdue_count': overdue_count,
        'par_ratio_rounded': round(par_ratio, 2),
        'charts_json': json.dumps(charts_payload, default=str),
        'branch_account_tx_json': json.dumps(branch_account_tx, default=str),
        'kpi_series_json': json.dumps([
            total_applications,
            approved_count,
            rejected_count,
            active_loans_count,
        ]),
        'recent_active_applications': [
            {
                'loan_ref_no': la.loan_ref_no,
                'customer': (la.customer.full_name if la.customer else ''),
                'status': la.status,
                'submitted_at': la.submitted_at.strftime('%Y-%m-%d') if la.submitted_at else ''
            }
            for la in list(active_apps_page_obj.object_list)
        ],
        'active_apps_page_obj': active_apps_page_obj,
        'active_apps_page_links': active_apps_page_links,
        'active_apps_query_string': active_apps_query_string,
        # Agents who have EMIs for loans of this branch in the selected window
        'top_active_agents': [],
    }

    top_agents_base_rows = list(
        emi_qs
            .exclude(loan_application__agent_id__isnull=True)
            .values('loan_application__agent_id', 'loan_application__agent__full_name')
            .annotate(loan_count=Count('loan_application_id', distinct=True))
            .order_by('-loan_count')
    )

    top_agents_rows = [
        {
            'agent_id': row['loan_application__agent_id'],
            'agent_name': row['loan_application__agent__full_name'] or '',
            'applications': row['loan_count'] or 0,
        }
        for row in top_agents_base_rows
    ]

    top_agents_query_params = request.GET.copy()
    top_agents_query_params.pop('t_page', None)
    top_agents_query_string = top_agents_query_params.urlencode()

    top_agents_paginator = Paginator(top_agents_rows, 5)
    top_agents_page_obj = top_agents_paginator.get_page(request.GET.get('t_page') or 1)
    try:
        top_agents_page_links = list(
            top_agents_paginator.get_elided_page_range(
                top_agents_page_obj.number, on_each_side=2, on_ends=1
            )
        )
    except Exception:
        top_agents_page_links = list(top_agents_paginator.page_range)

    context['top_active_agents'] = list(top_agents_page_obj.object_list)
    context['top_agents_page_obj'] = top_agents_page_obj
    context['top_agents_page_links'] = top_agents_page_links
    context['top_agents_query_string'] = top_agents_query_string
    return render(request, 'branch/branch_overview.html', context)


@require_permission('headquater.add_branch')
def register_branch(request):
    try:
        if request.method == 'POST':
            form = BranchForm(request.POST, prefix='branch')
            manager_form = BranchManagerForm(request.POST, prefix='manager')

            # Check if user has permission to create branches
            if not request.user.is_superuser:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Only superusers can create branches.'
                    }, status=403)
                else:
                    messages.error(request, 'Only superusers can create branches.')
                    return redirect('hq:branch_management')

            if form.is_valid() and manager_form.is_valid():
                try:
                    # Save branch first
                    branch = form.save(commit=False)
                    branch.created_by = request.user

                    # Save branch manager
                    manager = manager_form.save(commit=False)
                    manager.branch = branch
                    manager.is_manager = True
                    manager.is_verified = True
                    manager.created_by = request.user.id

                    try:
                        with transaction.atomic():
                            branch.save()
                            manager.save()
                            # Ensure default CASH account for this branch
                            BranchAccount.objects.get_or_create(
                                branch=branch,
                                type='CASH',
                                defaults={
                                    'name': 'Cash',
                                    'bank_name': 'Cash',
                                    'account_number': '',
                                    'current_balance': Decimal('0.00'),
                                    'created_by': manager,
                                    'updated_by': manager,
                                }
                            )
                    except Exception as manager_error:
                        logger = logging.getLogger(__name__)
                        logger.error(f'Error saving branch manager: {manager_error}', exc_info=True)
                        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                            return JsonResponse({
                                'success': False,
                                'message': f'Failed to save branch manager. Reason: {str(manager_error)}'
                            }, status=500)
                        else:
                            messages.error(request, f'Failed to save branch manager. Reason: {str(manager_error)}')
                            return redirect('hq:branch_management')

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        # Update branch's manager_id
                        branch.manager_id = manager.manager_id
                        branch.save(update_fields=['manager_id'])
                        
                        return JsonResponse({
                            'success': True,
                            'message': f'Branch {branch.branch_name} and manager have been created successfully.',
                            'branch_id': branch.branch_id
                        })
                    else:
                        # Update branch's manager_id for non-AJAX requests too
                        branch.manager_id = manager.manager_id
                        branch.save(update_fields=['manager_id'])
                        messages.success(request, f'Branch {branch.branch_name} and manager have been created successfully.')
                        return redirect('hq:branch_management')

                except Exception as e:
                    logger = logging.getLogger(__name__)
                    logger.error(f'Error saving branch or manager: {str(e)}', exc_info=True)
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        return JsonResponse({
                            'success': False,
                            'message': f'Failed to save branch or manager. Reason: {str(e)}'
                        }, status=500)
                    else:
                        messages.error(request, f'Failed to save branch or manager. Reason: {str(e)}')
                        return redirect('hq:branch_management')
            else:
                # Collect all form errors as a dict for JSON
                form_errors = {}
                for field, errors in form.errors.items():
                    form_errors[f'branch-{field}'] = list(errors)
                for field, errors in manager_form.errors.items():
                    form_errors[f'manager-{field}'] = list(errors)

                # Add debugging information
                logger = logging.getLogger(__name__)
                logger.error(f'Form validation failed. Branch form errors: {form.errors}')
                logger.error(f'Manager form errors: {manager_form.errors}')
                logger.error(f'Combined errors: {form_errors}')

                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'errors': form_errors,
                        'message': 'Form validation failed.',
                        'invalid_input': True
                    }, status=400)
                else:
                    # Display all errors at once
                    if form_errors:
                        messages.error(request, 'Please correct the following errors:')
                        for error_list in form_errors.values():
                            for error in error_list:
                                messages.error(request, error)

                    # Return with forms and errors
                    return render(request, 'branch/branch_create.html', {
                        'form': form,
                        'manager_form': manager_form,
                        'title': 'Create New Branch'
                    })
        else:
            # Initialize forms with prefixes
            form = BranchForm(prefix='branch')
            manager_form = BranchManagerForm(prefix='manager')

        return render(request, 'branch/branch_create.html', {
            'form': form,
            'manager_form': manager_form,
            'title': 'Create New Branch'
        })
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f'Error in branch registration: {str(e)}')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': f'An unexpected error occurred. Reason: {str(e)}'
            }, status=500)
        messages.error(request, f'An unexpected error occurred. Reason: {str(e)}')
        return render(request, 'branch/branch_create.html', {
            'form': form,
            'manager_form': manager_form,
            'title': 'Create New Branch'
        })

@require_permission('headquater.view_branch')
def get_branch_data(request, branch_id):
    """Get branch data for edit modal via AJAX"""
    branch = get_object_or_404(Branch, pk=branch_id)
    branch_data = {
        'branch_id': branch.branch_id,
        'branch_name': branch.branch_name,
        'address_line_1': branch.address_line_1 or '',
        'address_line_2': branch.address_line_2 or '',
        'city': branch.city or '',
        'state': branch.state or '',
        'postal_code': branch.postal_code or '',
        'country': branch.country or '',
        'district': branch.district or '',
        'contact_number': branch.contact_number or '',
        'email': branch.email or '',
        'manager_id': branch.manager_id if branch.manager_id else '',
        'status': branch.status,
    }
    return JsonResponse({'success': True, 'branch': branch_data})



@require_http_methods(["GET", "POST"])
@require_permission('headquater.change_branch')
def edit_branch(request, branch_id):
    branch = get_object_or_404(Branch, pk=branch_id)
    # Fetch the branch manager (employee where is_manager=True for this branch)
    manager = branch.employees.filter(is_manager=True).first()

    print(request.method)

    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch, prefix='branch')
        manager_form = BranchManagerForm(request.POST, instance=manager, prefix='manager')
        
        # Validate forms
        branch_valid = form.is_valid()
        manager_valid = manager_form.is_valid()
        
        if branch_valid and manager_valid:
            try:
                with transaction.atomic():
                    # Save branch first
                    branch = form.save()
                    
                    # Handle manager update/creation
                    manager_instance = manager_form.save(commit=False)
                    manager_instance.branch = branch
                    manager_instance.is_manager = True  # Ensure this is set to True
                    
                    # Only update password if provided
                    if manager_form.cleaned_data.get('password'):
                        manager_instance.password = make_password(manager_form.cleaned_data['password'])
                    
                    # Generate employee_id if new manager
                    if not manager_instance.employee_id:
                        from branch.models import BranchEmployee
                        last_employee = BranchEmployee.objects.filter(
                            branch=branch
                        ).order_by('-employee_id').first()
                        if last_employee and last_employee.employee_id.isdigit():
                            new_id = str(int(last_employee.employee_id) + 1).zfill(4)
                        else:
                            new_id = "0001"
                        manager_instance.employee_id = new_id
                    
                    manager_instance.save()
                    
                    # Update manager_id in branch if it's different
                    if branch.manager_id != manager_instance.manager_id:
                        branch.manager_id = manager_instance.manager_id
                        branch.save(update_fields=['manager_id'])
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': f'Branch {branch.branch_name} and manager have been updated successfully.',
                        'redirect_url': str(reverse_lazy('hq:branch_management'))
                    })
                messages.success(request, f'Branch {branch.branch_name} and manager have been updated successfully.')
                return redirect('hq:branch_management')
                
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f'Error updating branch: {str(e)}', exc_info=True)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': f'Error updating branch: {str(e)}'
                    }, status=500)
                messages.error(request, f'Error updating branch: {str(e)}')
        else:
            # Handle form errors
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                if not branch_valid:
                    errors.update({f'branch-{k}': v for k, v in form.errors.items()})
                if not manager_valid:
                    errors.update({f'manager-{k}': v for k, v in manager_form.errors.items()})
                return JsonResponse({
                    'success': False,
                    'message': 'Please correct the errors below:',
                    'errors': errors
                }, status=400)
    else:
        # GET request - initialize forms
        form = BranchForm(instance=branch, prefix='branch')
        initial = {}
        if manager:
            initial = {
                'first_name': manager.first_name,
                'last_name': manager.last_name,
                'email': manager.email,
                'phone_number': manager.phone_number,
                # Add other fields as needed
            }
        manager_form = BranchManagerForm(instance=manager, prefix='manager', initial=initial)
    
    return render(request, 'branch/branch_edit_form.html', {
        'form': form, 
        'manager_form': manager_form, 
        'branch': branch
    })

@require_permission('headquater.delete_branch')
def delete_branch(request, branch_id):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
    branch = get_object_or_404(Branch, pk=branch_id)
    try:
        branch_name = branch.branch_name
        # Soft delete: mark branch as inactive instead of deleting
        branch.status = False
        branch.save(update_fields=['status'])
        return JsonResponse({
            'success': True,
            'message': f'Branch {branch_name} has been deactivated successfully.',
            'redirect_url': f"{reverse_lazy('hq:branch_management')}?status=inactive"
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error deactivating branch: {str(e)}'})

@require_permission('headquater.change_branch')
@require_http_methods(["POST"])
def activate_branch(request, branch_id):
    branch = get_object_or_404(Branch, pk=branch_id)
    try:
        branch_name = branch.branch_name
        branch.status = True
        branch.save(update_fields=['status'])
        return JsonResponse({
            'success': True,
            'message': f'Branch {branch_name} has been activated successfully.',
            'redirect_url': f"{reverse_lazy('hq:branch_management')}?status=active"
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f'Error activating branch: {str(e)}'})

@require_permission('headquater.view_branch')
def branch_activity_summary(request, branch_id):
    if request.method != 'GET':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)

    branch = get_object_or_404(Branch, pk=branch_id)

    employees_qs = BranchEmployee.objects.filter(branch=branch)
    agents_qs = Agent.objects.filter(branch=branch)
    loans_qs = LoanApplication.objects.filter(branch=branch).select_related('customer').order_by('-submitted_at')
    customers_qs = CustomerDetail.objects.filter(branch=branch)
    accounts_qs = BranchAccount.objects.filter(branch=branch)
    tx_qs = BranchTransaction.objects.filter(branch=branch).order_by('-transaction_date')
    deposits_qs = AgentDeposit.objects.filter(branch=branch).select_related('agent').order_by('-received_at')

    provided_to_branch = float(
        FundTransfers.objects.filter(
            transfer_to=str(branch.branch_id),
            hq_transaction__isnull=False,
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    received_from_branch = float(
        FundTransfers.objects.filter(
            branch_transaction__branch=branch,
        ).aggregate(total=Sum('amount'))['total'] or 0
    )

    due_amount = max(0.0, provided_to_branch - received_from_branch)

    recent_loans = [
        {
            'loan_ref_no': loan.loan_ref_no,
            'customer_name': getattr(loan.customer, 'full_name', '') if loan.customer else '',
            'status': loan.status,
            'submitted_at': loan.submitted_at.strftime('%Y-%m-%d %H:%M') if loan.submitted_at else '',
        }
        for loan in loans_qs[:5]
    ]

    recent_transactions = [
        {
            'transaction_id': tx.transaction_id,
            'transaction_type': tx.transaction_type,
            'amount': float(tx.amount or 0),
            'purpose': tx.purpose or '',
            'transaction_date': tx.transaction_date.strftime('%Y-%m-%d %H:%M') if tx.transaction_date else '',
        }
        for tx in tx_qs[:5]
    ]

    recent_deposits = [
        {
            'deposit_id': dep.deposit_id,
            'agent': str(dep.agent) if dep.agent else '',
            'amount': float(dep.grand_total or 0),
            'received_at': dep.received_at.strftime('%Y-%m-%d %H:%M') if dep.received_at else '',
            'status': dep.status,
        }
        for dep in deposits_qs[:5]
    ]

    return JsonResponse({
        'success': True,
        'branch': {
            'branch_id': branch.branch_id,
            'branch_name': branch.branch_name,
            'status': branch.status,
        },
        'funds': {
            'provided_to_branch': provided_to_branch,
            'received_from_branch': received_from_branch,
            'due_amount': due_amount,
        },
        'employees': {
            'total': employees_qs.count(),
            'active': employees_qs.filter(is_active=True).count(),
            'inactive': employees_qs.filter(is_active=False).count(),
            'managers': employees_qs.filter(is_manager=True).count(),
        },
        'agents': {
            'total': agents_qs.count(),
            'active': agents_qs.filter(status='active').count(),
            'inactive': agents_qs.filter(status='inactive').count(),
        },
        'loans': {
            'total': loans_qs.count(),
            'pending': loans_qs.filter(status='pending').count(),
            'branch_approved': loans_qs.filter(status='branch_approved').count(),
            'hq_approved': loans_qs.filter(status='hq_approved').count(),
            'hq_rejected': loans_qs.filter(status='hq_rejected').count(),
            'disbursed_fund_released': loans_qs.filter(status='disbursed_fund_released').count(),
            'recent': recent_loans,
        },
        'customers': {
            'total': customers_qs.count(),
        },
        'accounts': {
            'total': accounts_qs.count(),
        },
        'transactions': {
            'total': tx_qs.count(),
            'recent': recent_transactions,
        },
        'agent_deposits': {
            'total': deposits_qs.count(),
            'recent': recent_deposits,
        },
    })

@require_permissions_for_class('loan.view_loanapplication')
class HQLoanListView(LoginRequiredMixin, TemplateView):
    template_name = 'loan/loan_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Read status filter from query params: all | request | approve | reject
        status_filter = (self.request.GET.get('status') or 'all').lower()
        # Optional branch filter (by branch.branch_id) - no session persistence
        selected_branch_id = (self.request.GET.get('branch_id') or '').strip()

        # Get branches created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        
        # Get agents created by those branches
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

        # Base queryset: only applications in relevant statuses
        base_qs = LoanApplication.objects.filter(
            Q(status='branch_approved') |
            Q(
                status__in=[
                    'branch_document_accepted', 'branch_resubmitted', 'hq_document_accepted',
                    'hq_resubmitted', 'document_requested_by_hq', 'hq_approved', 'hq_rejected',
                    'resubmitted',
                ],
                ever_branch_approved=True,
            )
        ).filter(
            Q(branch__in=user_branches) | Q(agent__in=user_agents)
        ).select_related('customer', 'branch', 'agent')

        # Apply branch filter if provided (only from user's branches)
        if selected_branch_id:
            base_qs = base_qs.filter(branch__branch_id=selected_branch_id)

        # Apply specific filters when requested
        if status_filter == 'request':
            qs = base_qs.filter(status='document_requested_by_hq')
        elif status_filter == 'approve':
            qs = base_qs.filter(status='hq_approved')
        elif status_filter == 'reject':
            qs = base_qs.filter(status='hq_rejected')
        else:
            # Default to all
            status_filter = 'all'
            qs = base_qs

        context['loan_applications'] = qs
        context['status_filter'] = status_filter
        context['selected_branch_id'] = selected_branch_id
        context['branches'] = user_branches.order_by('branch_name')  # Provide only user's branches for filter UI
        return context

#==========================================================================================
#                                BRANCH OPERATIONS ENDS                                   #
#==========================================================================================

#==========================================================================================
#                                LOAN OPERATIONS STARTS                                   #
#==========================================================================================

@require_permissions_for_class('loan.view_loanapplication')
class HQLoanDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'loan/loan_detailview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_ref_no = self.kwargs.get('loan_ref_no')
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        # Filter loan application to only show those from user's branches or agents
        app = LoanApplication.objects.select_related('customer', 'branch', 'agent').filter(
            Q(branch__in=user_branches) | Q(agent__in=user_agents)
        ).get(loan_ref_no=loan_ref_no)
        context['app'] = app

        context['customer_account'] = getattr(app.customer, 'account', None)
        # Check if accessed from loan close requests
        context['from_loan_close_requests'] = self.request.GET.get('source') == 'loan_close_requests'

        # Provide documents dict: latest approved reupload or original
        documents = getattr(app, 'documents', None)
        def get_approved_document(loan_application, doc_type, original_file):
            # Special handling for residential proof: check both possible doc_type values
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
            # Only return the file if there is an approved review
            for reupload in reuploads:
                if reupload.reviews.filter(decision='approved').exists():
                    return reupload.uploaded_file
            # Fallback to original (even if there are unapproved uploads)
            return original_file
        # Use get_approved_document for all document fields
        context['documents'] = {
            'id_proof': get_approved_document(app, 'id_proof', documents.id_proof if documents else None),
            'pan_card_document': get_approved_document(app, 'pan_card_document', getattr(documents, 'pan_card_document', None) if documents else None),
            'id_proof_back': get_approved_document(app, 'id_proof_back', documents.id_proof_back if documents else None),
            'income_proof': get_approved_document(app, 'income_proof', documents.income_proof if documents else None),
            'photo': get_approved_document(app, 'photo', documents.photo if documents else None),
            'signature': get_approved_document(app, 'signature', documents.signature if documents else None),
            'collateral': get_approved_document(app, 'collateral', documents.collateral if documents else None),
            'residential_proof_file': get_approved_document(app, 'residential_proof', documents.residential_proof_file if documents else None),
        }

        # Only branch reuploads that are still pending review (no review with decision 'approved' or 'request_again')
        branch_reuploads = DocumentReupload.objects.filter(
            loan_application=app,
            uploaded_by__isnull=True
        ).order_by('-uploaded_at')
        pending_branch_reuploads = [
            r for r in branch_reuploads
            if not r.reviews.filter(decision__in=['approved', 'request_again']).exists()
        ]
        context['branch_reuploads'] = pending_branch_reuploads

        # All document reviews for this application
        context['document_reviews'] = app.document_reviews.all().order_by('-reviewed_at')
        
        # Get document requests for this application
        document_requests = app.document_requests.all()
        context['document_requests'] = document_requests
        
        # Create a list of requested document types for template logic
        requested_docs = []
        for request in document_requests:
            if not request.is_resolved:
                requested_docs.append(request.document_type)
        
        # Also check for resubmitted documents that haven't been reviewed yet
        # Get all resubmitted documents for this application
        resubmitted_docs = DocumentReupload.objects.filter(
            loan_application=app
        ).order_by('-uploaded_at')
        
        # Check each resubmitted document to see if it has any reviews
        for resubmitted in resubmitted_docs:
            # If no reviews exist for this resubmitted document, consider it pending
            if not resubmitted.reviews.exists():
                if resubmitted.document_type not in requested_docs:
                    requested_docs.append(resubmitted.document_type)
        
        context['requested_docs'] = requested_docs
        
        return context

@require_permissions_for_class('loan.change_loanapplication')
@method_decorator(csrf_exempt, name='dispatch')
class HQLoanApproveRejectView(LoginRequiredMixin, View):
    def post(self, request, loan_ref_no):
        if not request.user.is_authenticated:
            return HttpResponseForbidden('Authentication required')
        action = request.POST.get('action')
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        # Filter loan application to only allow actions on user's branches/agents
        loan_app = LoanApplication.objects.filter(
            Q(branch__in=user_branches) | Q(agent__in=user_agents)
        ).get(loan_ref_no=loan_ref_no)
        if loan_app.status in ['document_requested', 'document_requested_by_hq']:
            return JsonResponse({'success': False, 'error': 'Cannot approve/reject while documents are requested.'}, status=400)
        if DocumentRequest.objects.filter(loan_application=loan_app, is_resolved=False).exists():
            return JsonResponse({'success': False, 'error': 'Cannot approve/reject while document requests are pending.'}, status=400)
        if action == 'approve':
            loan_app.status = 'hq_approved'
            loan_app.approved_at = timezone.now()
            loan_app.save()
            _log_loan_action(request.user, loan_app, 'loan_hq_approved')
            return JsonResponse({'success': True, 'new_status': 'hq_approved'})
        elif action == 'reject':
            loan_app.status = 'hq_rejected'
            loan_app.save()
            _log_loan_action(request.user, loan_app, 'loan_hq_rejected')
            return JsonResponse({'success': True, 'new_status': 'hq_rejected'})
        return JsonResponse({'success': False, 'error': 'Invalid action'})

@require_permissions_for_class('loan.change_loanapplication')
@method_decorator(csrf_exempt, name='dispatch')
class HQDocumentRequestAPI(View):
    def post(self, request, *args, **kwargs):
        import json
        data = json.loads(request.body.decode('utf-8'))
        loan_ref_no = data.get('loan_ref_no')
        document_type = data.get('document_type')
        reason = data.get('reason')
        comment = data.get('comment', '')
        if not (loan_ref_no and document_type and reason):
            return JsonResponse({'success': False, 'error': 'Missing required fields.'}, status=400)
        try:
            # Get branches and agents created by the logged-in HQ user
            user_branches = Branch.objects.filter(created_by=request.user)
            user_branch_ids = user_branches.values_list('branch_id', flat=True)
            user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
            
            # Filter loan application to only allow actions on user's branches/agents
            loan_app = LoanApplication.objects.filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).get(loan_ref_no=loan_ref_no)
            DocumentRequest.objects.create(
                loan_application=loan_app,
                document_type=document_type,
                reason=reason,
                comment=comment,
                requested_by=None,
                requested_by_hq=request.user if request.user.is_authenticated else None,
                branch=loan_app.branch
            )
            loan_app.status = 'document_requested_by_hq'
            loan_app.save()
            # TODO: send notification to branch/agent if needed
            return JsonResponse({'success': True, 'new_status': 'document_requested_by_hq'})
        except LoanApplication.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Loan application not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

@login_required
@require_permission('loan.view_loanapplication')
def hq_document_requests_list(request):
    loan_applications = LoanApplication.objects.filter(status='document_requested_by_hq').select_related('customer', 'branch', 'agent')
    return render(request, 'loan/document_requests.html', {'loan_applications': loan_applications})

@login_required
@require_permission('loan.view_loanapplication')
def hq_approved_applications_list(request):
    loan_applications = LoanApplication.objects.filter(status='hq_approved').select_related('customer', 'branch', 'agent')
    return render(request, 'loan/approved_applications.html', {'loan_applications': loan_applications})

@login_required
@require_permission('loan.view_loanapplication')
def hq_rejected_applications_list(request):
    loan_applications = LoanApplication.objects.filter(status='hq_rejected').select_related('customer', 'branch', 'agent')
    return render(request, 'loan/rejected_applications.html', {'loan_applications': loan_applications})

@require_permissions_for_class('loan.change_loanapplication')
@method_decorator(csrf_exempt, name='dispatch')
class HQDocumentReviewAPI(View):
    def post(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=403)
        import json
        data = json.loads(request.body.decode('utf-8'))
        reupload_id = data.get('reupload_id')
        decision = data.get('decision')
        review_comment = data.get('review_comment', '')
        if not reupload_id or not decision:
            return JsonResponse({'success': False, 'error': 'Missing required fields.'}, status=400)
        try:
            reupload = DocumentReupload.objects.get(id=reupload_id)
            loan_app = reupload.loan_application
            # HQ-specific status update
            if decision == 'approved':
                # loan_app.status = 'hq_document_accepted'
                # Update the corresponding field in CustomerDocument
                customer_document = getattr(loan_app, 'documents', None)
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
                # from loan.models import DocumentReupload
                all_reuploads = DocumentReupload.objects.filter(loan_application=loan_app)
                all_approved = True
                for r in all_reuploads:
                    if not r.reviews.filter(decision='approved').exists():
                        all_approved = False
                        break
                
                # Only update status when ALL reuploads are approved
                if all_approved:
                    loan_app.status = 'hq_document_accepted'
                    loan_app.save()

            elif decision == 'request_again':
                loan_app.status = 'hq_resubmitted'
            loan_app.save()
            review = DocumentReview.objects.create(
                document_reupload=reupload,
                loan_application=loan_app,
                decision=decision,
                review_comment=review_comment,
                reviewed_by=None,  # Optionally set to HQ user if you have a model for it
                branch=None  # Optionally set to HQ branch if needed
            )
            # If decision is to request again, create a new document request
            if decision == 'request_again':
                from loan.models import DocumentRequest
                DocumentRequest.objects.create(
                    loan_application=loan_app,
                    document_type=reupload.document_type,
                    reason='other',
                    comment=f"Re-requested after HQ review. Previous comment: {review_comment}",
                    requested_by=None,
                    requested_by_hq=request.user,
                    branch=loan_app.branch
                )
            return JsonResponse({'success': True, 'message': 'Document review completed successfully'})
        except DocumentReupload.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Document reupload not found.'}, status=404)
@require_permission('loan.change_loancategory')
def loan_management(request):
    selected_main_category_id = (request.GET.get('main_category') or request.POST.get('selected_main_category') or '').strip()
    manage_main_categories = (request.GET.get('manage_main_categories') or request.POST.get('manage_main_categories') or '').strip() == '1'
    selected_main_category = None
    if selected_main_category_id:
        selected_main_category = LoanMainCategory.objects.filter(main_category_id=selected_main_category_id).first()

    from django.db.models import Case, When, IntegerField, Q
    main_categories = LoanMainCategory.objects.filter(
        Q(created_by=request.user) | Q(created_by__isnull=True)
    ).annotate(
        _display_order=Case(
            When(name='Personal Loans', then=0),
            When(name='Home & Property Loans', then=1),
            When(name='Consumer / Gadget Loans', then=2),
            When(name='Vehicle Loans', then=3),
            default=99,
            output_field=IntegerField(),
        )
    ).order_by('_display_order', 'name')

    active_main_categories = main_categories.filter(is_active=True)

    categories = LoanCategory.objects.select_related('main_category').filter(created_by=request.user).filter(Q(main_category__isnull=True) | Q(main_category__is_active=True))
    interests = LoanInterest.objects.filter(created_by=request.user).filter(Q(main_category__isnull=True) | Q(main_category__is_active=True))
    tenures = LoanTenure.objects.select_related('interest_rate').filter(created_by=request.user).filter(Q(interest_rate__main_category__isnull=True) | Q(interest_rate__main_category__is_active=True))
    deductions = Deductions.objects.filter(created_by=request.user).filter(Q(main_category__isnull=True) | Q(main_category__is_active=True))
    late_fees = LateFeeSetting.objects.filter(created_by=request.user).filter(Q(main_category__isnull=True) | Q(main_category__is_active=True))

    if selected_main_category and selected_main_category.is_active:
        categories = categories.filter(main_category=selected_main_category)
        interests = interests.filter(main_category=selected_main_category)
        tenures = tenures.filter(interest_rate__main_category=selected_main_category)
        deductions = deductions.filter(main_category=selected_main_category)
        late_fees = late_fees.filter(main_category=selected_main_category)

    categories = categories.order_by('main_category__name', 'name')
    interests = interests.order_by('rate_of_interest')
    tenures = tenures.order_by('value', 'unit')
    deductions = deductions.order_by('deduction_name')
    late_fees = late_fees.order_by('-created_at')

    post_form_type = (request.POST.get('form_type') or '').strip()

    show_assign_unmapped_modal = False
    unmapped_target_main_category = None
    unmapped_categories = LoanCategory.objects.filter(created_by=request.user, main_category__isnull=True).order_by('name')
    unmapped_interests = LoanInterest.objects.filter(created_by=request.user, main_category__isnull=True).order_by('rate_of_interest')
    unmapped_deductions = Deductions.objects.filter(created_by=request.user, main_category__isnull=True).order_by('deduction_name')
    unmapped_late_fees = LateFeeSetting.objects.filter(created_by=request.user, main_category__isnull=True).order_by('-created_at')

    if request.method == 'POST' and post_form_type == 'assign_unmapped':
        target_main_category_id = (request.POST.get('target_main_category_id') or '').strip()
        unmapped_target_main_category = LoanMainCategory.objects.filter(main_category_id=target_main_category_id).first()
        show_assign_unmapped_modal = True

        if not unmapped_target_main_category:
            messages.error(request, 'Please select a valid main category.')
        else:
            category_ids = request.POST.getlist('category_ids')
            interest_ids = request.POST.getlist('interest_ids')
            deduction_ids = request.POST.getlist('deduction_ids')
            late_fee_ids = request.POST.getlist('late_fee_ids')

            if not (category_ids or interest_ids or deduction_ids or late_fee_ids):
                messages.error(request, 'Please select at least one item to assign.')
            else:
                LoanCategory.objects.filter(created_by=request.user, main_category__isnull=True, category_id__in=category_ids).update(
                    main_category=unmapped_target_main_category,
                    is_active=unmapped_target_main_category.is_active,
                )
                LoanInterest.objects.filter(created_by=request.user, main_category__isnull=True, interest_id__in=interest_ids).update(
                    main_category=unmapped_target_main_category,
                    is_active=unmapped_target_main_category.is_active,
                )
                Deductions.objects.filter(created_by=request.user, main_category__isnull=True, deduction_id__in=deduction_ids).update(
                    main_category=unmapped_target_main_category,
                    is_active=unmapped_target_main_category.is_active,
                )
                LateFeeSetting.objects.filter(created_by=request.user, main_category__isnull=True, id__in=late_fee_ids).update(
                    main_category=unmapped_target_main_category,
                    is_active=unmapped_target_main_category.is_active,
                )

                if interest_ids:
                    LoanTenure.objects.filter(created_by=request.user, interest_rate__interest_id__in=interest_ids).update(
                        is_active=unmapped_target_main_category.is_active,
                    )

                messages.success(request, 'Unmapped items assigned successfully!')
                if selected_main_category_id:
                    return redirect(f"/hq/loan-manage/management/?manage_main_categories=1&main_category={selected_main_category_id}")
                return redirect(f"/hq/loan-manage/management/?manage_main_categories=1")

    elif (request.GET.get('assign_unmapped') or '').strip() == '1':
        show_assign_unmapped_modal = True

    show_main_category_modal = False
    main_category_form = None
    main_category_modal_action = ''
    main_category_modal_title = ''

    edit_main_category_id = request.GET.get('edit_main_category')
    if request.method == 'POST' and post_form_type == 'main_category':

        old_is_active = None
        if request.POST.get('main_category_id'):
            main_category = get_object_or_404(LoanMainCategory, main_category_id=request.POST['main_category_id'])
            old_is_active = main_category.is_active
            main_category_form = LoanMainCategoryForm(request.POST, instance=main_category)
            main_category_modal_action = 'Edit'
            main_category_modal_title = 'Edit Loan Main Category'
        else:
            main_category_form = LoanMainCategoryForm(request.POST)
            main_category_modal_action = 'Add'
            main_category_modal_title = 'Add Loan Main Category'
        show_main_category_modal = True
        if main_category_form.is_valid():
            obj = main_category_form.save(commit=False)
            obj.created_by = request.user
            obj.save()

            # Cascade active/inactive to all related master data
            if old_is_active is not None and old_is_active != obj.is_active:
                LoanCategory.objects.filter(main_category=obj).update(is_active=obj.is_active)
                LoanInterest.objects.filter(main_category=obj).update(is_active=obj.is_active)
                LoanTenure.objects.filter(interest_rate__main_category=obj).update(is_active=obj.is_active)
                Deductions.objects.filter(main_category=obj).update(is_active=obj.is_active)
                LateFeeSetting.objects.filter(main_category=obj).update(is_active=obj.is_active)

            messages.success(request, f"Loan main category {main_category_modal_action.lower()}ed successfully!")
            if manage_main_categories:
                if selected_main_category_id:
                    return redirect(f"/hq/loan-manage/management/?manage_main_categories=1&main_category={selected_main_category_id}")
                return redirect(f"/hq/loan-manage/management/?manage_main_categories=1")

            if selected_main_category_id:
                return redirect(f"/hq/loan-manage/management/?main_category={selected_main_category_id}")
            return redirect('hq:loan_management')

        else:
            messages.error(request, 'Failed to save loan main category. Please check the form.')
    elif edit_main_category_id:
        main_category = get_object_or_404(LoanMainCategory, main_category_id=edit_main_category_id)
        main_category_form = LoanMainCategoryForm(instance=main_category)
        main_category_modal_action = 'Edit'
        main_category_modal_title = 'Edit Loan Main Category'
        show_main_category_modal = True
    elif request.GET.get('add_main_category') == '1':
        main_category_form = LoanMainCategoryForm()
        main_category_modal_action = 'Add'
        main_category_modal_title = 'Add Loan Main Category'
        show_main_category_modal = True

    # Category modal logic
    show_modal = False
    form = None
    modal_action = ''
    modal_title = ''
    category_id = request.GET.get('edit')
    if request.method == 'POST' and post_form_type == 'category':

        if request.POST.get('category_id'):
            category = get_object_or_404(LoanCategory, category_id=request.POST['category_id'])
            original_main_category = category.main_category
            form = LoanCategoryForm(request.POST, instance=category)
            modal_action = 'Edit'
            modal_title = 'Edit Loan Category'
        else:
            form = LoanCategoryForm(request.POST)
            modal_action = 'Add'
            modal_title = 'Add Loan Category'
        show_modal = True
        if form.is_valid():
            cat = form.save(commit=False)
            cat.created_by = request.user

            if request.POST.get('category_id'):
                cat.main_category = original_main_category
            elif selected_main_category:
                # Always set main_category from URL parameter when creating new category
                # This ensures it's set even when the form field is disabled
                cat.main_category = selected_main_category

            cat.save()
            messages.success(request, f"Loan category {modal_action.lower()}ed successfully!")
            if selected_main_category_id:
                return redirect(f"/hq/loan-manage/management/?main_category={selected_main_category_id}")
            return redirect('hq:loan_management')
        else:
            messages.error(request, "Failed to save loan category. Please check the form.")
            # If there's a validation error and we have a selected main category, 
            # ensure the form maintains the preselected and readonly state
            if not request.POST.get('category_id') and selected_main_category:
                form.fields['main_category'].widget.attrs['readonly'] = True
                form.fields['main_category'].widget.attrs['disabled'] = True
    elif category_id:
        category = get_object_or_404(LoanCategory, category_id=category_id)
        form = LoanCategoryForm(instance=category)
        modal_action = 'Edit'
        modal_title = 'Edit Loan Category'
        show_modal = True
    elif request.GET.get('add') == '1':
        # Preselect main_category if provided in URL
        initial_data = {}
        if selected_main_category:
            initial_data['main_category'] = selected_main_category
        form = LoanCategoryForm(initial=initial_data)
        
        # Make main_category field readonly if preselected
        if selected_main_category:
            form.fields['main_category'].widget.attrs['readonly'] = True
            form.fields['main_category'].widget.attrs['disabled'] = True
        
        modal_action = 'Add'
        modal_title = 'Add Loan Category'
        show_modal = True

    # Interest modal logic
    show_interest_modal = False
    interest_form = None
    interest_modal_action = ''
    interest_modal_title = ''
    interest_id = request.GET.get('edit_interest')
    if request.method == 'POST' and ('rate_of_interest' in request.POST):

        if request.POST.get('interest_id'):
            interest = get_object_or_404(LoanInterest, interest_id=request.POST['interest_id'])
            interest_form = LoanInterestForm(request.POST, instance=interest)
            interest_modal_action = 'Edit'
            interest_modal_title = 'Edit Interest Rate'
        else:
            interest_form = LoanInterestForm(request.POST)
            interest_modal_action = 'Add'
            interest_modal_title = 'Add Interest Rate'
        show_interest_modal = True
        if selected_main_category:
            interest_form.instance.main_category = selected_main_category
        if interest_form.is_valid():
            try:
                obj = interest_form.save(commit=False)
                obj.created_by = request.user
                obj.save()
                messages.success(request, f"Interest rate {interest_modal_action.lower()}ed successfully!")
                if selected_main_category_id:
                    return redirect(f"/hq/loan-manage/management/?main_category={selected_main_category_id}")
                return redirect('hq:loan_management')
            except IntegrityError as e:
                if 'loan_loaninterest_main_category_id_rate_of_f2429aff_uniq' in str(e):
                    messages.error(request, "This interest rate already exists for the selected main category. Please use a different interest rate.")
                else:
                    messages.error(request, "A database error occurred. Please try again.")
        else:
            messages.error(request, "Failed to save interest rate. Please check the form.")
    elif interest_id:
        interest = get_object_or_404(LoanInterest, interest_id=interest_id)
        interest_form = LoanInterestForm(instance=interest)
        interest_modal_action = 'Edit'
        interest_modal_title = 'Edit Interest Rate'
        show_interest_modal = True
    elif request.GET.get('add_interest') == '1':
        interest_form = LoanInterestForm()

        interest_modal_action = 'Add'
        interest_modal_title = 'Add Interest Rate'
        show_interest_modal = True

    # Tenure modal logic
    show_tenure_modal = False
    tenure_form = None
    tenure_modal_action = ''
    tenure_modal_title = ''
    tenure_id = request.GET.get('edit_tenure')
    if request.method == 'POST' and ('value' in request.POST and 'unit' in request.POST):

        if request.POST.get('tenure_id'):
            tenure = get_object_or_404(LoanTenure, tenure_id=request.POST['tenure_id'])
            tenure_form = LoanTenureForm(request.POST, instance=tenure, main_category=selected_main_category, user=request.user)

            tenure_modal_action = 'Edit'
            tenure_modal_title = 'Edit Loan Tenure'
        else:
            tenure_form = LoanTenureForm(request.POST, main_category=selected_main_category, user=request.user)

            tenure_modal_action = 'Add'
            tenure_modal_title = 'Add Loan Tenure'
        show_tenure_modal = True
        if tenure_form.is_valid():
            obj = tenure_form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, f"Loan tenure {tenure_modal_action.lower()}ed successfully!")
            if selected_main_category_id:
                return redirect(f"/hq/loan-manage/management/?main_category={selected_main_category_id}")
            return redirect('hq:loan_management')
        else:
            messages.error(request, "Failed to save loan tenure. Please check the form.")
    elif tenure_id:
        tenure = get_object_or_404(LoanTenure, tenure_id=tenure_id)
        tenure_form = LoanTenureForm(instance=tenure, main_category=selected_main_category, user=request.user)

        tenure_modal_action = 'Edit'
        tenure_modal_title = 'Edit Loan Tenure'
        show_tenure_modal = True
    elif request.GET.get('add_tenure') == '1':
        tenure_form = LoanTenureForm(main_category=selected_main_category, user=request.user)

        tenure_modal_action = 'Add'
        tenure_modal_title = 'Add Loan Tenure'
        show_tenure_modal = True

    # Deduction master modal logic
    show_deduction_modal = False
    deduction_form = None
    deduction_modal_action = ''
    deduction_modal_title = ''
    deduction_id = request.GET.get('edit_deduction')
    if request.method == 'POST' and ('deduction_name' in request.POST and 'deduction_type' in request.POST and 'deduction_value' in request.POST):

            if request.POST.get('deduction_id'):
                deduction = get_object_or_404(Deductions, deduction_id=request.POST['deduction_id'])
                deduction_form = DeductionForm(request.POST, instance=deduction)
                deduction_modal_action = 'Edit'
                deduction_modal_title = 'Edit Deduction'
            else:
                deduction_form = DeductionForm(request.POST)
                deduction_modal_action = 'Add'
                deduction_modal_title = 'Add Deduction'
            show_deduction_modal = True
            if selected_main_category:
                deduction_form.instance.main_category = selected_main_category
            if deduction_form.is_valid():
                obj = deduction_form.save(commit=False)
                obj.created_by = request.user
                obj.save()
                messages.success(request, f"Deduction {deduction_modal_action.lower()}ed successfully!")
                if selected_main_category_id:
                    return redirect(f"/hq/loan-manage/management/?main_category={selected_main_category_id}")
                return redirect('hq:loan_management')

            else:
                messages.error(request, "Failed to save deduction. Please check the form.")
    elif deduction_id:
        deduction = get_object_or_404(Deductions, deduction_id=deduction_id)
        deduction_form = DeductionForm(instance=deduction)
        deduction_modal_action = 'Edit'
        deduction_modal_title = 'Edit Deduction'
        show_deduction_modal = True
        # Pass the deduction_id to the template context
        edit_deduction_id = deduction_id
    elif request.GET.get('add_deduction') == '1':
        deduction_form = DeductionForm()

        deduction_modal_action = 'Add'
        deduction_modal_title = 'Add Deduction'
        show_deduction_modal = True

    # Late Fee Settings modal logic
    show_late_fee_modal = False
    late_fee_modal_action = ''
    late_fee_modal_title = ''
    edit_late_fee_id = request.GET.get('edit_late_fee')
    if request.method == 'POST' and ('late_fee_type' in request.POST and 'late_fee_value' in request.POST and 'late_fee_grace_days' in request.POST and 'late_fee_frequency' in request.POST):

        # Create or update LateFeeSetting with new fields
        fee_type = (request.POST.get('late_fee_type') or 'percentage').strip()
        fee_value_raw = (request.POST.get('late_fee_value') or '').strip()
        frequency = (request.POST.get('late_fee_frequency') or 'monthly').strip()
        grace_days_raw = (request.POST.get('late_fee_grace_days') or '').strip()
        is_active = True if request.POST.get('late_fee_is_active') in ['on', 'true', 'True', '1'] else False
        late_fee_id = request.POST.get('late_fee_id')
        show_late_fee_modal = True
        try:
            from decimal import Decimal
            fee_value = Decimal(fee_value_raw)
            grace_days = int(grace_days_raw)
        except Exception:
            messages.error(request, 'Invalid late fee input. Enter numeric value and integer grace days.')
            late_fee_modal_action = 'Edit' if late_fee_id else 'Add'
            late_fee_modal_title = f"{late_fee_modal_action} Late Fee Setting"
        else:
            if late_fee_id:
                inst = get_object_or_404(LateFeeSetting, id=late_fee_id)

                inst.fee_type = fee_type
                inst.fee_value = fee_value
                inst.frequency = frequency
                inst.grace_days = grace_days
                inst.is_active = is_active
                # Backward-compatibility: set deprecated percentage when applicable
                inst.percentage = fee_value if fee_type == 'percentage' else None
                inst.created_by = request.user if hasattr(request.user, 'id') else None
                inst.main_category = selected_main_category
                inst.save()
                messages.success(request, 'Late fee setting updated successfully!')
            else:
                inst = LateFeeSetting.objects.create(
                    fee_type=fee_type,
                    fee_value=fee_value,
                    frequency=frequency,
                    grace_days=grace_days,
                    is_active=is_active,
                    # Backward-compatibility
                    percentage=(fee_value if fee_type == 'percentage' else None),
                    created_by=request.user if hasattr(request.user, 'id') else None,
                    main_category=selected_main_category,
                )
                messages.success(request, 'Late fee setting added successfully!')
            if selected_main_category_id:
                return redirect(f"/hq/loan-manage/management/?main_category={selected_main_category_id}")
            return redirect('hq:loan_management')

    elif edit_late_fee_id:
         # Open edit modal
         try:
             inst = LateFeeSetting.objects.get(id=edit_late_fee_id)
             late_fee_modal_action = 'Edit'
             late_fee_modal_title = 'Edit Late Fee Setting'
             show_late_fee_modal = True
         except LateFeeSetting.DoesNotExist:
             messages.error(request, 'Late fee setting not found.')
    elif request.GET.get('add_late_fee') == '1':
         late_fee_modal_action = 'Add'
         late_fee_modal_title = 'Add Late Fee Setting'
         show_late_fee_modal = True

    context = {
        'main_categories': main_categories,
        'active_main_categories': active_main_categories,
        'selected_main_category_id': selected_main_category_id,
        'selected_main_category': selected_main_category,
        'manage_main_categories': manage_main_categories,
        'show_main_category_list_modal': manage_main_categories,
        'show_assign_unmapped_modal': show_assign_unmapped_modal,
        'unmapped_target_main_category': unmapped_target_main_category,
        'unmapped_categories': unmapped_categories,
        'unmapped_interests': unmapped_interests,
        'unmapped_deductions': unmapped_deductions,
        'unmapped_late_fees': unmapped_late_fees,
        'main_category_form': main_category_form,
        'show_main_category_modal': show_main_category_modal,
        'main_category_modal_action': main_category_modal_action,
        'main_category_modal_title': main_category_modal_title,

        'edit_main_category_id': edit_main_category_id,
        'categories': categories,
        'interests': interests,
        'tenures': tenures,
        'deductions': deductions,
        'late_fees': late_fees,
        'form': form,
        'show_modal': show_modal,
        'modal_action': modal_action,
        'modal_title': modal_title,
        'edit_category_id': category_id,
        'interest_form': interest_form,
        'show_interest_modal': show_interest_modal,
        'interest_modal_action': interest_modal_action,
        'interest_modal_title': interest_modal_title,
        'edit_interest_id': interest_id,
        'tenure_form': tenure_form,
        'show_tenure_modal': show_tenure_modal,
        'tenure_modal_action': tenure_modal_action,
        'tenure_modal_title': tenure_modal_title,
        'edit_tenure_id': tenure_id,
        'deduction_form': deduction_form,
        'show_deduction_modal': show_deduction_modal,
        'deduction_modal_action': deduction_modal_action,
        'deduction_modal_title': deduction_modal_title,
        'edit_deduction_id': deduction_id,
        'show_late_fee_modal': show_late_fee_modal,
        'late_fee_modal_action': late_fee_modal_action,
        'late_fee_modal_title': late_fee_modal_title,
        # 'edit_late_fee_id': edit_late_fee_id,
        'edit_late_fee_id': edit_late_fee_id,
        'late_fee_to_edit': (inst if (locals().get('inst') and edit_late_fee_id) else None),
    }
    return render(request, 'loan-manage/loan_management.html', context)

@login_required
@require_permission('loan.change_loancategory')
def loan_monitoring(request):
    periodList = LoanPeriod.objects.all()
    return render(request, 'loan-manage/loan_monitoring.html', {
        'periodList': periodList,
    })

@require_permissions_for_class('loan.view_disbursementlog')
class LoanDisbursementList(LoginRequiredMixin, TemplateView):
    template_name = 'loan-disbursement/disbursement.html'
    # permission_required = 'loan.view_disbursementlog'
    # permission_denied_message = "You don't have permission to view this page."
    
    # def has_permission(self):
    #     # Allow super admins or users with the specific permission
    #     return (self.request.user.is_superuser or super().has_permission())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        # if self.request.user.is_headquater_admin or self.request.user.has_perm('loan.view_disbursementlog'):
        context['loan_disbursement'] = LoanApplication.objects.filter(
            status='hq_approved'
        ).filter(
            Q(branch__in=user_branches) | Q(agent__in=user_agents)
        ).select_related(
            'customer', 'branch', 'agent'
        ).prefetch_related(
            'loan_details__loan_category', 
            'loan_details__tenure', 
            'loan_details__interest_rate'
        )
        return context

@require_permissions_for_class('loan.view_disbursementlog')
class LoanDisbursementDetail(LoginRequiredMixin, TemplateView):
    template_name = 'loan-disbursement/disbursementDetail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_ref_no = self.kwargs.get('loan_ref_no')
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        try:
            loan_application = LoanApplication.objects.filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).select_related(
                'customer', 'branch', 'agent'
            ).prefetch_related(
                'loan_details__loan_category', 'loan_details__tenure', 'loan_details__interest_rate', 'periods'
            ).get(loan_ref_no=loan_ref_no)
            context['app'] = loan_application
            context['title'] = f'Loan Disbursement Details - {loan_ref_no}'
        except LoanApplication.DoesNotExist:
            context['error'] = 'Loan application not found.'
            context['app'] = None
        return context

    def post(self, request, *args, **kwargs):
        loan_ref_no = self.kwargs.get('loan_ref_no')
        try:
            # Get branches and agents created by the logged-in HQ user
            user_branches = Branch.objects.filter(created_by=request.user)
            user_branch_ids = user_branches.values_list('branch_id', flat=True)
            user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
            
            # Filter loan application to only allow actions on user's branches/agents
            loan_app = LoanApplication.objects.filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).get(loan_ref_no=loan_ref_no)
            if loan_app.status != 'hq_approved':
                return JsonResponse({
                    'success': False,
                    'message': 'Loan is not approved for disbursement.'
                }, status=400)

            # Ensure loan_details exists
            loan_detail = loan_app.loan_details.first()
            if not loan_detail:
                return JsonResponse({
                    'success': False,
                    'message': 'Loan details not found for this application.'
                }, status=400)

            if not isinstance(request.user, HeadquarterEmployee):
                return JsonResponse({
                    'success': False,
                    'message': 'User is not authorized to disburse loans. Must be a Headquarter Employee.'
                }, status=403)

            # Update loan status to 'disbursed'
            loan_app.status = 'disbursed'
            loan_app.disbursed_at = timezone.now()
            loan_app.save()

            _log_loan_action(request.user, loan_app, 'loan_hq_disbursed')

            # # Create DisbursementLog entry (HQ to Branch)
            # DisbursementLog.objects.create(
            #     loan_id=loan_app,
            #     disbursed_by=request.user,
            #     disbursed_to=loan_app.branch.branch_id or 'N/A',
            #     amount=loan_detail.loan_amount,
            #     type='HTB'  # Always HQ to Branch
            # )

            return JsonResponse({
                'success': True,
                'message': 'Loan disbursed successfully to branch.',
                'redirect_url': reverse_lazy('hq:loan_disbursement')
            })
            
        except LoanApplication.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Loan application not found.'
            }, status=404)
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error processing disbursement: {str(e)}'
            }, status=500)
        except LoanApplication.DoesNotExist:
            context = self.get_context_data(**kwargs)
            context['error'] = 'Loan application not found.'
            messages.error(request, context['error'])
            return self.render_to_response(context)
        except Exception as e:
            # logger.error(f"Error disbursing loan {loan_ref_no}: {str(e)}", exc_info=True)
            context = self.get_context_data(**kwargs)
            context['error'] = f'Error disbursing loan: {str(e)}'
            messages.error(request, context['error'])
            return self.render_to_response(context)

@require_permissions_for_class('loan.view_disbursementlog')
class DisbursementHold(LoginRequiredMixin, TemplateView):
    template_name = 'loan-disbursement/disbursementHold.html'

    def get_context_data(self, **kwargs):
       context = super().get_context_data(**kwargs)
       
       # Get branches and agents created by the logged-in HQ user
       user_branches = Branch.objects.filter(created_by=self.request.user)
       user_branch_ids = user_branches.values_list('branch_id', flat=True)
       user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
       
       context['loan_disbursement'] = LoanApplication.objects.filter(status='disbursed').filter(
           Q(branch__in=user_branches) | Q(agent__in=user_agents)
       ).select_related('customer', 'branch', 'agent',).prefetch_related('loan_details__loan_category', 'loan_details__tenure', 'loan_details__interest_rate')
       return context

@require_permissions_for_class('loan.view_disbursementlog')
class DisbursementHoldDetail(LoginRequiredMixin, TemplateView):
    template_name = 'loan-disbursement/disbursementHoldDetail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_ref_no = self.kwargs.get('loan_ref_no')
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        try:
            loan_application = LoanApplication.objects.filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).select_related(
                'customer', 'branch', 'agent'
            ).prefetch_related(
                'loan_details__loan_category', 'loan_details__tenure', 'loan_details__interest_rate', 'periods'
            ).get(loan_ref_no=loan_ref_no)
            context['app'] = loan_application
            context['title'] = f'Loan Disbursement On Hold - {loan_ref_no}'
        except LoanApplication.DoesNotExist:
            context['error'] = 'Loan application not found.'
            context['app'] = None
        return context

@require_permissions_for_class('loan.view_disbursementlog')
class DisbursedAndFundRelease(LoginRequiredMixin, TemplateView):
    template_name = 'loan-disbursement/disbursedFundRelease.html'

    def get_context_data(self, **kwargs):
        import json
        from django.core.paginator import Paginator
        context = super().get_context_data(**kwargs)

        # Optional branch filter from query params
        request = self.request
        selected_branch_id = request.GET.get('branch_id') or ''

        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

        # Base queryset: all disbursed loans
        qs = LoanApplication.objects.filter(status='disbursed_fund_released') \
            .filter(Q(branch__in=user_branches) | Q(agent__in=user_agents)) \
            .select_related('customer', 'branch', 'agent') \
            .prefetch_related('loan_details__loan_category', 'loan_details__tenure', 'loan_details__interest_rate')

        # Apply branch filter if provided (only from user's branches)
        if selected_branch_id:
            qs = qs.filter(branch__branch_id=selected_branch_id)

        qs = qs.order_by('-disbursed_at', '-submitted_at')

        per_page = 10
        try:
            per_page = int(request.GET.get('per_page') or per_page)
        except Exception:
            per_page = 10

        paginator = Paginator(qs, per_page)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        try:
            page_links = list(
                paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            page_links = list(paginator.page_range)

        preserved = request.GET.copy()
        if 'page' in preserved:
            preserved.pop('page')
        context['querystring'] = preserved.urlencode()
        context['query_string'] = context['querystring']
        context['page_obj'] = page_obj
        context['page_links'] = page_links
        context['is_paginated'] = page_obj.has_other_pages()

        from datetime import datetime
        def serialize_qs(qs, fields):
            data = []
            for obj in qs:
                item = {}
                for f in fields:
                    val = getattr(obj, f, None)
                    if f in ('document_type', 'reason', 'comment'):
                        val = val if val is not None else ''
                    if isinstance(val, datetime):
                        item[f] = val.isoformat() if val else None
                    else:
                        item[f] = str(val) if val is not None and not isinstance(val, (int, float, bool, dict, list)) else val
                data.append(item)
            return data

        # Build a list of loan dicts with all fields and unique tracking history
        loans = []
        for app in page_obj.object_list:
            # Document requests
            requests_data = serialize_qs(getattr(app, 'document_requests', []).all() if hasattr(app, 'document_requests') and hasattr(getattr(app, 'document_requests', []), 'all') else [],
                fields=["id", "loan_application_id", "document_type", "reason", "comment", "requested_by_id", "requested_at", "is_resolved", "resolved_at"])
            for req in requests_data:
                if 'document_type' not in req or req['document_type'] is None:
                    req['document_type'] = ''
                if 'reason' not in req or req['reason'] is None:
                    req['reason'] = ''
            # Document reviews
            reviews_data = serialize_qs(getattr(app, 'document_reviews', []).all() if hasattr(app, 'document_reviews') and hasattr(getattr(app, 'document_reviews', []), 'all') else [],
                fields=["id", "loan_application_id", "document_type", "decision", "reviewed_by_id", "review_comment", "reviewed_at"])
            for rev in reviews_data:
                if 'document_type' not in rev or rev['document_type'] is None:
                    rev['document_type'] = ''
                if 'decision' not in rev or rev['decision'] is None:
                    rev['decision'] = ''
            # Document reuploads
            reuploads_data = serialize_qs(getattr(app, 'document_reuploads', []).all() if hasattr(app, 'document_reuploads') and hasattr(getattr(app, 'document_reuploads', []), 'all') else [],
                fields=["id", "document_request_id", "document_type", "reason", "agent_note", "uploaded_by_id", "uploaded_at"])
            for reu in reuploads_data:
                if 'document_type' not in reu or reu['document_type'] is None:
                    reu['document_type'] = ''
                if 'reason' not in reu or reu['reason'] is None:
                    reu['reason'] = ''
            # DisbursementLog tracking history (system/branch/HQ)
            disb_logs = app.disbursement_logs.all() if hasattr(app, 'disbursement_logs') and hasattr(app.disbursement_logs, 'all') else []
            tracking_history = []
            for log in disb_logs:
                tracking_history.append({
                    'dis_id': log.dis_id,
                    'amount': float(log.amount) if log.amount is not None else None,
                    'disb_mode': log.disb_mode,
                    'bank_name': log.bank_name,
                    'account_number': log.account_number,
                    'net_amount_cust': float(log.net_amount_cust) if log.net_amount_cust is not None else None,
                    'tax_charges': float(log.tax_charges) if log.tax_charges is not None else None,
                    'disburse_proof': log.disburse_proof,
                    'remarks': log.remarks,
                    'disbursed_by': str(log.disbursed_by) if log.disbursed_by else '',
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                    'agent': str(app.agent.full_name) if hasattr(app, 'agent') and app.agent else '',
                })

            # Agent tracking history (agent actions on this loan)
            agent_tracking = []
            # DocumentReupload: agent uploads
            reuploads = getattr(app, 'document_reuploads', []).all() if hasattr(app, 'document_reuploads') and hasattr(getattr(app, 'document_reuploads', []), 'all') else []
            for reu in reuploads:
                if reu.uploaded_by:
                    agent_tracking.append({
                        'type': 'document_reupload',
                        'agent_name': str(reu.uploaded_by.full_name) if hasattr(reu.uploaded_by, 'full_name') else str(reu.uploaded_by),
                        'document_type': getattr(reu, 'document_type', ''),
                        'reason': getattr(reu, 'reason', ''),
                        'agent_note': getattr(reu, 'agent_note', ''),
                        'uploaded_at': reu.uploaded_at.isoformat() if reu.uploaded_at else None,
                    })
            # Add more agent actions here if needed (e.g., agent-initiated logs)

            # Merge and categorize tracking events for frontend
            categorized_history = {
                'agent': agent_tracking,
                'system': tracking_history,  # you can further split into branch/hq/system if needed
            }
            # Build loan dict with all required fields for the template
            loan_dict = {
                'loan_ref_no': app.loan_ref_no,
                'status': app.status,
                'submitted_at': getattr(app, 'submitted_at', None),
                'disbursed_at': getattr(app, 'disbursed_at', None),
                'branch_approved_at': getattr(app, 'branch_approved_at', None),
                'hq_approved_at': getattr(app, 'hq_approved_at', None),
                'ever_branch_approved': getattr(app, 'ever_branch_approved', False),
                'branch_approver': getattr(app, 'branch_approver', ''),
                'hq_approver': getattr(app, 'hq_approver', ''),
                'customer': app.customer,
                'agent': app.agent,
                'branch': app.branch,
                'loan_details': app.loan_details,
                'document_requests_json': json.dumps(requests_data),
                'document_reviews_json': json.dumps(reviews_data),
                'document_reuploads_json': json.dumps(reuploads_data),
                'tracking_history_json': json.dumps(categorized_history),
            }
            loans.append(loan_dict)
        context['disbursement_releaseFund'] = loans
        context['selected_branch_id'] = selected_branch_id or None
        return context




# --- PDF Generation View ---
@login_required
def generate_loan_pdf(request, loan_ref_no):
    """
    Generate a PDF report for a loan disbursement using Playwright and Chromium.
    This view is intended to be used as a direct download link (no AJAX/API).
    """
    from loan.models import LoanApplication
    try:
        app = LoanApplication.objects.select_related('customer', 'branch', 'agent').get(loan_ref_no=loan_ref_no)
        customer = app.customer
        agent = app.agent
        loan = app.loan_details.first()
    except LoanApplication.DoesNotExist:
        return HttpResponse("Loan application not found.", status=404)

    context = {
        "generated_date": timezone.now().strftime("%Y-%m-%d %H:%M"),
        "loan_application": app,
        "customer": customer,
        "agent": agent,
        "loan": loan,
    }
    html_content = render_to_string("loan-disbursement/loan_disvursed_fund_pdf.html", context)

    async def render_pdf(html):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            pdf_bytes = await page.pdf(format="A4", print_background=True)
            await browser.close()
            return pdf_bytes

    if async_playwright is None:
        return HttpResponse("Playwright is not installed.", status=500)

    pdf_bytes = asyncio.run(render_pdf(html_content))

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Loan_Disbursement_Report_{loan_ref_no}.pdf"'
    return response


class GenerateLoanPDF(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'loan-disbursement/loan_disvursed_fund_pdf.html')
    
    def post(self, request, *args, **kwargs):
        return render(request, 'loan-disbursement/loan_disvursed_fund_pdf.html')
        

############## for wallet ##############
@require_permissions_for_class('loan.view_disbursementlog')
class HQWallet(LoginRequiredMixin, View):
    template_name = 'hq-wallet/wallet.html'
    balance_form_class = WalletBalanceForm
    transfer_form_class = BranchTransferForm

    def get(self, request, *args, **kwargs):
        # NOTE: Multiple HQ accounts can exist (CASH and BANK). Do not assume a singleton wallet.
        # Ensure a default CASH HQ account exists for cash transfers
        if not HeadquartersWallet.objects.filter(type='CASH').exists():
            HeadquartersWallet.objects.get_or_create(type='CASH', defaults={'name': 'Cash', 'balance': 0.00})
        # Initialize balance form
        balance_form = self.balance_form_class(user=request.user)

        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        # Get recent transactions filtered by user hierarchy
        hq_transactions = HeadquartersTransactions.objects.select_related('wallet') \
            .filter(
                Q(created_by=request.user) |
                Q(fund_transfers__branch_transaction__branch__in=user_branches)
            ).distinct().order_by('-transaction_date')[:50]
        
        # NEW APPROACH: Get branch names through FundTransfers -> BranchTransaction
        try:
            # Get all fund transfers for these HQ transactions filtered by user hierarchy
            fund_transfers = FundTransfers.objects.filter(
                hq_transaction__in=hq_transactions,
                branch_transaction__branch__in=user_branches
            ).select_related('branch_transaction__branch')
            
            # Create a mapping of HQ transaction IDs to branch names
            hq_to_branch_display = {}
            for ft in fund_transfers:
                if ft.hq_transaction_id and ft.branch_transaction:
                    # Access branch through branch_transaction relationship
                    branch = ft.branch_transaction.branch
                    hq_to_branch_display[ft.hq_transaction_id] = f"{branch.branch_name} ({branch.branch_id})"
                elif ft.hq_transaction_id and ft.transfer_to:
                    # Fallback: use transfer_to field if branch_transaction is None
                    try:
                        branch = Branch.objects.get(branch_id=ft.transfer_to, created_by=request.user)
                        hq_to_branch_display[ft.hq_transaction_id] = f"{branch.branch_name} ({branch.branch_id})"
                    except Branch.DoesNotExist:
                        hq_to_branch_display[ft.hq_transaction_id] = f"Unknown Branch ({ft.transfer_to})"
            
            # Attach branch info to transactions
            for tx in hq_transactions:
                tx.branch_display = hq_to_branch_display.get(tx.transaction_id, "-")
                # Also set individual attributes for filtering
                if tx.transaction_id in hq_to_branch_display:
                    display_text = hq_to_branch_display[tx.transaction_id]
                    tx.branch_name = display_text.split(' (')[0]  # Extract name part
                    tx.branch_id = display_text.split(' (')[-1].rstrip(')')  # Extract ID part
                else:
                    tx.branch_name = None
                    tx.branch_id = None
                    
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error mapping branch names: {str(e)}")
            for tx in hq_transactions:
                tx.branch_display = "-"
                tx.branch_name = None
                tx.branch_id = None
        
        # Handle branch selection from GET parameters or session
        selected_branch = None
        branch_id = request.GET.get('branch') or request.session.get('selected_branch')
        
        if branch_id:
            try:
                selected_branch = Branch.objects.get(branch_id=branch_id)
                # Store in session for form re-rendering
                request.session['selected_branch'] = branch_id
            except Branch.DoesNotExist:
                selected_branch = None
                if 'selected_branch' in request.session:
                    del request.session['selected_branch']
        
        # Initialize transfer form with session data if available
        transfer_form_data = request.session.pop('transfer_form_data', None)
        # Ensure a default CASH HQ account exists before initializing transfer form
        if not HeadquartersWallet.objects.filter(type='CASH').exists():
            HeadquartersWallet.objects.get_or_create(type='CASH', defaults={'name': 'Cash', 'balance': 0.00})
        transfer_form = self.transfer_form_class(
            data=transfer_form_data,
            request=request,
            wallet=None,
            selected_branch=selected_branch 
        )

        # Build accounts map for client-side population (branch_id -> list of accounts)
        try:
            from branch.models import BranchAccount
            accounts_data = {}
            for acc in BranchAccount.objects.select_related('branch').filter(type='BANK', branch__in=user_branches):
                bid = str(acc.branch.branch_id)
                accounts_data.setdefault(bid, []).append({
                    'id': acc.id,
                    'label': f"{acc.bank_name} - {acc.account_number}"
                })
        except Exception:
            accounts_data = {}
        
        # Get recent fund transfers with related data filtered by user hierarchy
        recent_transfers = FundTransfers.objects.select_related(
            'hq_transaction', 'branch_transaction__branch'
        ).filter(
            hq_transaction__isnull=False,  # Only show transfers initiated from HQ
            branch_transaction__branch__in=user_branches
        ).order_by('-transfer_date')[:10]
        
        # Calculate monthly income and expenses
        from django.db.models import Sum, Max, Min
        from datetime import datetime, timedelta
        
        # Get the first day of current month
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        
        # Total balances by account type filtered by logged-in user
        cash_balance = HeadquartersWallet.objects.filter(type='CASH', created_by=request.user).aggregate(total=Sum('balance'))['total'] or 0.00
        account_balance = HeadquartersWallet.objects.filter(type='BANK', created_by=request.user).aggregate(total=Sum('balance'))['total'] or 0.00
        # Calculate monthly income (credits) filtered by user hierarchy
        monthly_income = HeadquartersTransactions.objects.filter(
            transaction_type='credit',
            transaction_date__date__gte=first_day_of_month
        ).filter(
            Q(created_by=request.user) |
            Q(fund_transfers__branch_transaction__branch__in=user_branches)
        ).distinct().aggregate(total=Sum('amount'))['total'] or 0.00
        
        # Calculate monthly expenses (debits) filtered by user hierarchy
        monthly_expenses = HeadquartersTransactions.objects.filter(
            transaction_type='debit',
            transaction_date__date__gte=first_day_of_month
        ).filter(
            Q(created_by=request.user) |
            Q(fund_transfers__branch_transaction__branch__in=user_branches)
        ).distinct().aggregate(total=Sum('amount'))['total'] or 0.00

        # Compute wallet summary across HQ accounts created by logged-in user
        aggregates = HeadquartersWallet.objects.filter(
            created_by=request.user
        ).aggregate(
            total_balance=Sum('balance'),
            last_updated=Max('last_updated'),
            created_at=Min('created_at'),
        )
        wallet_summary = {
            'wallet_id': 'SUMMARY',
            'balance': float(aggregates['total_balance'] or 0.00),
            'last_updated': aggregates['last_updated'],
            'created_at': aggregates['created_at'],
        }
        
        # Build HQ BANK accounts payload filtered by logged-in user
        bank_qs = HeadquartersWallet.objects.filter(type='BANK', created_by=request.user)
        bank_accounts = []
        for acc in bank_qs:
            bank_accounts.append({
                'wallet_id': str(acc.wallet_id),
                'name': acc.name or '',
                'bank_name': acc.bank_name or '',
                'account_number': acc.account_number or '',
                'balance': float(acc.balance or 0),
                'last_updated': acc.last_updated.isoformat() if acc.last_updated else ''
            })

        # Prepare context
        context = {
            'wallet': wallet_summary,
            'form': balance_form,
            'transfer_form': transfer_form,
            'hqtransaction': hq_transactions,
            'recent_transfers': recent_transfers,
            'cash_balance': float(cash_balance),
            'account_balance': float(account_balance),
            'monthly_income': float(monthly_income) if monthly_income else 0.00,
            'monthly_expenses': float(monthly_expenses) if monthly_expenses else 0.00,
            'selected_branch_id': selected_branch.branch_id if selected_branch else None, 
            'all_accounts_json': json.dumps(accounts_data), 
            'hq_bank_accounts_json': json.dumps(bank_accounts),
            'hq_wallet_form': HeadquartersWalletForm(),
        }
        
        # Add any messages that might have been set
        storage = messages.get_messages(request)
        if storage:
            context['messages'] = storage
            
        return render(request, self.template_name, context)


    def post(self, request, *args, **kwargs):
        # Check permissions
        if not (request.user.is_superuser or 
               (hasattr(request.user, 'role') and 
                request.user.role.role_type in ['super_admin', 'finance_manager'])):
            messages.error(request, 'You do not have permission to perform this action.')
            return redirect('hq:wallet')

        wallet = None  # No singleton wallet; operations will use the selected hq_account

        # Check which form was submitted
        if 'hq_add_account' in request.POST:
            return self._handle_add_account(request)
        if 'transfer_submit' in request.POST:
            return self._handle_transfer(request, wallet)
        else:
            return self._handle_balance_update(request, wallet)
    
    def _handle_add_account(self, request):
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        form = HeadquartersWalletForm(request.POST)
        if form.is_valid():
            try:
                name = form.cleaned_data.get('name')
                bank_name = form.cleaned_data.get('bank_name')
                account_number = form.cleaned_data.get('account_number')
                amount_raw = request.POST.get('amount')

                # Parse and validate initial amount
                initial_balance = Decimal('0.00')
                if amount_raw is None or str(amount_raw).strip() == '':
                    err = 'Amount is required.'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': err}, status=400)
                    messages.error(request, err)
                    return redirect('hq:wallet')
                try:
                    initial_balance = Decimal(str(amount_raw))
                    if initial_balance < 0:
                        raise ValueError('negative')
                except Exception:
                    err = 'Enter a valid non-negative amount.'
                    if is_ajax:
                        return JsonResponse({'success': False, 'message': err}, status=400)
                    messages.error(request, err)
                    return redirect('hq:wallet')
                
                # Infer type: if bank fields present -> BANK else CASH
                inferred_type = 'BANK' if (bank_name or account_number) else 'CASH'

                # Create wallet with initial balance
                wallet = HeadquartersWallet.objects.create(
                    type=inferred_type,
                    name=name,
                    bank_name=bank_name if inferred_type == 'BANK' else None,
                    account_number=account_number if inferred_type == 'BANK' else None,
                    balance=initial_balance
                )

                # Create corresponding HQ transaction for opening balance
                if initial_balance > 0:
                    HeadquartersTransactions.objects.create(
                        wallet=wallet,
                        transaction_type='credit',
                        amount=initial_balance,
                        description='Opening balance on HQ account creation',
                        purpose='Opening balance',
                        code=None,
                        reference_number=None,
                        proof_document=None,
                        created_by=request.user
                    )

                msg = f"HQ account created: {wallet.name or wallet.get_type_display()} ({wallet.wallet_id})"
                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': msg,
                        'wallet': {
                            'wallet_id': wallet.wallet_id,
                            'type': wallet.type,
                            'label': f"{wallet.bank_name} - {wallet.account_number}" if wallet.type == 'BANK' else 'Cash'
                        }
                    })
                messages.success(request, msg)
                return redirect('hq:wallet')
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error creating HQ account: {str(e)}")
                err = 'Failed to create HQ account. Please try again.'
                if is_ajax:
                    return JsonResponse({'success': False, 'message': err}, status=500)
                messages.error(request, err)
                return redirect('hq:wallet')
        else:
            err = 'Invalid account data. Please check inputs.'
            if is_ajax:
                return JsonResponse({'success': False, 'message': err, 'errors': form.errors}, status=400)
            messages.error(request, err)
            return redirect('hq:wallet')
    
    def _handle_balance_update(self, request, wallet):
        """Handle wallet balance update (deposit/withdraw)"""
        form = self.balance_form_class(request.POST, request.FILES, user=request.user)
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        
        if form.is_valid():
            try:
                transaction_type = form.cleaned_data['transaction_type']
                amount = form.cleaned_data['amount']
                description_notes = form.cleaned_data.get('description', '')
                purpose_account = form.cleaned_data.get('purpose_account')
                reference_number = form.cleaned_data.get('reference_number')
                proof_document = request.FILES.get('proof_document')
                hq_account = form.cleaned_data.get('hq_account')

                # Fallback to default wallet if none selected (should not happen due to required=True)
                target_wallet = hq_account or wallet

                # Get purpose from the selected Chart of Account
                purpose = f"{purpose_account.head_of_account}" if purpose_account else "Manual transaction"

                code = purpose_account.code if purpose_account else None

                # Compose description using ChartOfAccount if selected
                desc_parts = []
                if purpose:
                    desc_parts.append(str(purpose))
                if description_notes:
                    desc_parts.append(str(description_notes).strip())
                composed_description = " - ".join(desc_parts) if desc_parts else ''
                
                with transaction.atomic():
                    # Update selected wallet balance
                    if transaction_type == 'credit':
                        target_wallet.balance += amount
                        success_message = f'Successfully deposited ₹{amount:,.2f} to HQ account.'
                    else:  # debit
                        if target_wallet.balance < amount:
                            error_msg = 'Insufficient balance for this transaction.'
                            if is_ajax:
                                return JsonResponse({
                                    'success': False,
                                    'message': error_msg
                                }, status=400)
                            messages.error(request, error_msg)
                            return self._render_wallet_page(request, target_wallet, form=form)
                        target_wallet.balance -= amount
                        success_message = f'Successfully withdrew ₹{amount:,.2f} from HQ account.'
                    
                    # Save wallet with updated balance
                    target_wallet.save()
                    
                    # Create transaction record
                    hq_transaction = HeadquartersTransactions.objects.create(
                        wallet=target_wallet,
                        transaction_type=transaction_type,
                        amount=amount,
                        description=composed_description or description_notes or None,
                        purpose=purpose,
                        code=code,
                        reference_number=reference_number,
                        proof_document=proof_document,
                        created_by=request.user
                    )
                    
                    full_message = f'{success_message} New balance: ₹{target_wallet.balance:,.2f}'
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': True,
                            'message': full_message,
                            'new_balance': str(target_wallet.balance)
                        })
                        
                    messages.success(request, full_message)
                    return redirect('hq:wallet')
                    
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error in wallet transaction: {str(e)}")
                error_msg = f'Failed to complete the transaction: {str(e)}. Please try again.'
                
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': error_msg
                    }, status=500)
                    
                messages.error(request, error_msg)
        
        # If form is invalid or error occurred
        if is_ajax:
            return JsonResponse({
                'success': False,
                'message': 'Please check your input.',
                'errors': form.errors
            }, status=400)
            
        return self._render_wallet_page(request, wallet, form=form)
    
    def _handle_transfer(self, request, wallet):
        """Handle branch transfer"""
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        # Get selected branch from POST data for form initialization
        selected_branch = None
        branch_id = request.POST.get('branch')
        if branch_id:
            try:
                selected_branch = Branch.objects.get(branch_id=branch_id)
            except Branch.DoesNotExist:
                selected_branch = None

        # Ensure a default CASH HQ account exists before binding transfer form
        if not HeadquartersWallet.objects.filter(type='CASH').exists():
            HeadquartersWallet.objects.get_or_create(type='CASH', defaults={'name': 'Cash', 'balance': 0.00})
        transfer_form = self.transfer_form_class(
            request.POST,
            request=request,
            wallet=wallet,
            selected_branch=selected_branch
        )
        
        if transfer_form.is_valid():
            try:
                branch = transfer_form.cleaned_data['branch']
                amount = transfer_form.cleaned_data['amount']
                accounts = transfer_form.cleaned_data.get('accounts')
                payment_mode = transfer_form.cleaned_data.get('payment_mode')
                bank_method = transfer_form.cleaned_data.get('transfer_bank_payment_method')
                purpose_account = transfer_form.cleaned_data.get('purpose_account')
                hq_account = transfer_form.cleaned_data.get('hq_account')

                # Use the Chart of Account head_of_account as the purpose
                purpose = purpose_account.head_of_account if purpose_account else "Fund Transfer"

                # Compose description depending on mode
                if payment_mode == 'bank' and accounts:
                    mode_desc = f"Bank - {bank_method.upper() if bank_method else ''} - {accounts.bank_name} ({accounts.account_number})"
                else:
                    mode_desc = "Cash"
                description_text = f"Transfer to {branch.branch_name}: {mode_desc}: {purpose}"
                
                with transaction.atomic():
                    # 1. Verify selected HQ account balance (double check)
                    if not hq_account or hq_account.balance < amount:
                        error_msg = 'Insufficient balance for this transfer.'
                        if is_ajax:
                            return JsonResponse({
                                'success': False,
                                'message': error_msg
                            }, status=400)
                        messages.error(request, error_msg)
                        return redirect('hq:wallet')
                    
                    # 2. Create HQ transaction record (debit) on selected HQ account
                    hq_transaction = HeadquartersTransactions.objects.create(
                        wallet=hq_account,
                        transaction_type='debit',
                        amount=amount,
                        description=description_text,
                        purpose=purpose,
                        code=purpose_account.code if purpose_account else None,
                        created_by=request.user
                    )
                    
                    # 3. Update selected HQ account balance
                    hq_account.balance -= amount
                    hq_account.save(update_fields=['balance'])
                    
                    # 4. Update branch wallet balance
                    # branch.wallet_balance = (branch.wallet_balance or 0) + amount
                    # branch.wallet_updated = timezone.now()
                    # branch.save(update_fields=['wallet_balance', 'wallet_updated'])

                    # Update BranchAccount balance depending on mode and capture destination account
                    dest_account = None
                    if payment_mode == 'bank' and accounts:
                        accounts.current_balance += amount
                        accounts.save(update_fields=['current_balance'])
                        dest_account = accounts
                    elif payment_mode == 'cash':
                        try:
                            from branch.models import BranchAccount
                            cash_acc = BranchAccount.objects.filter(branch=branch, type='CASH').first()
                            if cash_acc:
                                cash_acc.current_balance += amount
                                cash_acc.updated_at = timezone.now()
                                cash_acc.save(update_fields=['current_balance', 'updated_at'])
                                dest_account = cash_acc
                        except Exception:
                            pass
                    
                    # Create the fund transfer record
                    fund_transfer = FundTransfers.objects.create(
                        hq_transaction=hq_transaction,
                        branch_transaction=None,
                        transfer_to=str(branch.branch_id),
                        amount=amount,
                        purpose=purpose,
                        payment_mode=payment_mode,
                        bank_method=bank_method if payment_mode == 'bank' else None,
                        transfer_date=timezone.now(),
                        created_by=str(request.user.id),
                        branch_account=dest_account
                    )
                    
                    # Refresh branch data
                    branch.refresh_from_db()

                    # Clear session data
                    if 'selected_branch' in request.session:
                        del request.session['selected_branch']
                    
                    # Clear the form data from the session
                    if request.session.get('transfer_form_data'):
                        del request.session['transfer_form_data']
                    
                    success_msg = f'Successfully transferred ₹{amount:,.2f} to {branch.branch_name}. New balance: ₹{hq_account.balance:,.2f}'
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': True,
                            'message': success_msg,
                            'new_balance': str(hq_account.balance)
                        })
                        
                    messages.success(request, success_msg)
                    return redirect('hq:wallet')
                    
            except Exception as e:
                logger = logging.getLogger(__name__)
                logger.error(f"Error in fund transfer: {str(e)}")
                error_msg = f'Failed to complete the transfer: {str(e)}. Please try again.'
                
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': error_msg
                    }, status=500)
                    
                messages.error(request, error_msg)
                return redirect('hq:wallet')
        
        # If form is invalid, store the data in session for re-rendering
        if not is_ajax:
            request.session['transfer_form_data'] = request.POST.dict()
            if selected_branch:
                request.session['selected_branch'] = selected_branch.branch_id

        # If form is invalid or error occurred
        if is_ajax:
            return JsonResponse({
                'success': False,
                'message': 'Please check your input.',
                'errors': transfer_form.errors
            }, status=400)
            
        return self._render_wallet_page(request, wallet, transfer_form=transfer_form)
    
    def _render_wallet_page(self, request, wallet, form=None, transfer_form=None):
        """Helper method to render the wallet page with forms"""
        if form is None:
            form = self.balance_form_class(user=request.user)
        
        # Handle branch selection for transfer form
        selected_branch = None
        branch_id = request.session.get('selected_branch')
        if branch_id:
            try:
                selected_branch = Branch.objects.get(branch_id=branch_id)
            except Branch.DoesNotExist:
                selected_branch = None

        if transfer_form is None:
            transfer_form = self.transfer_form_class(request=request, wallet=wallet, selected_branch=selected_branch)
        
        # Get recent transactions and convert Decimal values to float
        hq_transactions = HeadquartersTransactions.objects.select_related('wallet') \
                                                      .order_by('-transaction_date')[:50]
        
        # Apply the same branch mapping fix here
        try:
            from branch.models import Branch
            
            fund_transfers = FundTransfers.objects.filter(
                hq_transaction__in=hq_transactions,
                transfer_to__isnull=False
            )
            
            hq_to_branch_display = {}
            for ft in fund_transfers:
                if ft.hq_transaction_id and ft.transfer_to:
                    try:
                        branch = Branch.objects.get(branch_id=ft.transfer_to)
                        hq_to_branch_display[ft.hq_transaction_id] = f"{branch.branch_name} ({branch.branch_id})"
                    except Branch.DoesNotExist:
                        hq_to_branch_display[ft.hq_transaction_id] = f"Unknown Branch ({ft.transfer_to})"
            
            for tx in hq_transactions:
                tx.branch_display = hq_to_branch_display.get(tx.transaction_id, "-")
                    
        except Exception as e:
            for tx in hq_transactions:
                tx.branch_display = "-"
        
        # Get recent fund transfers with related data
        recent_transfers = FundTransfers.objects.select_related(
            'hq_transaction', 'branch_transaction__branch'
        ).filter(
            hq_transaction__isnull=False  # Only show transfers initiated from HQ
        ).order_by('-transfer_date')[:10]
        
        # Calculate monthly income and expenses
        from django.db.models import Sum, Max, Min
        from datetime import datetime
        
        # Get the first day of current month
        today = datetime.now().date()
        first_day_of_month = today.replace(day=1)
        
        # Calculate monthly income (credits)
        monthly_income = HeadquartersTransactions.objects.filter(
            transaction_type='credit',
            transaction_date__date__gte=first_day_of_month
        ).aggregate(total=Sum('amount'))['total'] or 0.00
        
        # Calculate monthly expenses (debits)
        monthly_expenses = HeadquartersTransactions.objects.filter(
            transaction_type='debit',
            transaction_date__date__gte=first_day_of_month
        ).aggregate(total=Sum('amount'))['total'] or 0.00

        # Totals for CASH and BANK wallets
        cash_balance = HeadquartersWallet.objects.filter(type='CASH').aggregate(total=Sum('balance'))['total'] or 0.00
        account_balance = HeadquartersWallet.objects.filter(type='BANK').aggregate(total=Sum('balance'))['total'] or 0.00
            
        # Build wallet context: if a concrete wallet passed, use it; else compute summary
        if wallet is not None:
            wallet_ctx = {
                'wallet_id': wallet.wallet_id,
                'balance': float(wallet.balance) if wallet.balance is not None else 0.00,
                'last_updated': wallet.last_updated,
                'created_at': wallet.created_at
            }
        else:
            aggregates = HeadquartersWallet.objects.aggregate(
                total_balance=Sum('balance'),
                last_updated=Max('last_updated'),
                created_at=Min('created_at'),
            )
            wallet_ctx = {
                'wallet_id': 'SUMMARY',
                'balance': float(aggregates['total_balance'] or 0.00),
                'last_updated': aggregates['last_updated'],
                'created_at': aggregates['created_at'],
            }
        
        # Build HQ BANK accounts payload
        bank_qs = HeadquartersWallet.objects.filter(type='BANK')
        bank_accounts = []
        for acc in bank_qs:
            bank_accounts.append({
                'wallet_id': str(acc.wallet_id),
                'name': acc.name or '',
                'bank_name': acc.bank_name or '',
                'account_number': acc.account_number or '',
                'balance': float(acc.balance or 0),
                'last_updated': acc.last_updated.isoformat() if acc.last_updated else ''
            })

        context = {
            'wallet': wallet_ctx,
            'form': form,
            'transfer_form': transfer_form,
            'hqtransaction': hq_transactions,
            'recent_transfers': recent_transfers,
            'cash_balance': float(cash_balance),
            'account_balance': float(account_balance),
            'monthly_income': float(monthly_income) if monthly_income else 0.00,
            'monthly_expenses': float(monthly_expenses) if monthly_expenses else 0.00,
            'selected_branch_id': selected_branch.branch_id if selected_branch else None,
            'hq_bank_accounts_json': json.dumps(bank_accounts),
        }
        return render(request, self.template_name, context)


@require_permissions_for_class('view_loanapplication')
class EmiLoanListView(TemplateView):
    template_name = 'loan_servicing/emi_loan_list.html'

    def get_context_data(self, **kwargs):
        from django.core.paginator import Paginator
        context = super().get_context_data(**kwargs)
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        # Base queryset: only disbursed loans eligible for EMI servicing
        qs = LoanApplication.objects.filter(status='disbursed_fund_released') \
            .filter(Q(branch__in=user_branches) | Q(agent__in=user_agents)) \
            .select_related('customer', 'branch', 'agent') \
            .prefetch_related('loan_details__loan_category', 'loan_details__tenure', 'loan_details__interest_rate') \
            .order_by('-disbursed_at')

        # Read filters from query params
        request = self.request
        selected_branch_id = request.GET.get('branch_id') or ''
        selected_loan_ref_no = request.GET.get('loan_ref_no') or ''

        # Apply branch filter first (by business branch_id)
        if selected_branch_id:
            qs = qs.filter(branch__branch_id=selected_branch_id)

        # Prepare EMI options limited to selected branch (if any)
        emi_options = []
        if selected_branch_id:
            emi_options = list(
                qs.values_list('loan_ref_no', flat=True)
            )

        # KPI aggregates scoped to current filters
        from loan.models import LoanEMISchedule, EmiCollectionDetail
        today = timezone.localdate()
        emi_qs = LoanEMISchedule.objects.filter(loan_application__in=qs)

        total_loans = qs.count()
        upcoming_count = emi_qs.filter(paid=False, installment_date__gt=today).count()
        due_count = emi_qs.filter(paid=False, installment_date=today).count()
        overdue_count = emi_qs.filter(paid=False, installment_date__lt=today).count()
        total_outstanding = emi_qs.filter(paid=False).aggregate(total=Sum('installment_amount'))['total'] or 0

        # Total loan amount logic:
        # - If a particular loan is selected, show TOTAL scheduled amount for that loan (sum of all EMIs)
        # - Else, show sum of unpaid EMIs across the current filtered set
        if selected_loan_ref_no:
            total_loan_amount = (
                emi_qs.filter(loan_application__loan_ref_no=selected_loan_ref_no)
                .aggregate(total=Sum('installment_amount'))['total'] or 0
            )
        else:
            total_loan_amount = emi_qs.aggregate(total=Sum('installment_amount'))['total'] or 0

        paginator = Paginator(qs, 10)
        page_obj = paginator.get_page(request.GET.get('page') or 1)
        try:
            page_links = list(
                paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
            )
        except Exception:
            page_links = list(paginator.page_range)

        query_params = request.GET.copy()
        query_params.pop('page', None)
        query_string = query_params.urlencode()

        # Provide branches for the filter UI (only user's branches)
        context['branches'] = user_branches.order_by('branch_name')
        context['selected_branch_id'] = selected_branch_id
        context['selected_loan_ref_no'] = selected_loan_ref_no
        context['emi_options'] = emi_options
        context['loan_emi_list'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['page_links'] = page_links
        context['query_string'] = query_string
        context['kpis'] = {
            'total_loans': total_loans,
            'upcoming_count': upcoming_count,
            'due_count': due_count,
            'overdue_count': overdue_count,
            'total_outstanding': float(total_outstanding),
            'total_loan_amount': float(total_loan_amount),
        }
        return context

@require_permissions_for_class('loan.view_disbursementlog')
class EmiScheduleView(LoginRequiredMixin, TemplateView):
    template_name = 'loan_servicing/emi_scedule.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        loan_ref_no = self.kwargs.get('loan_ref_no')
        
        # Get branches and agents created by the logged-in HQ user
        user_branches = Branch.objects.filter(created_by=self.request.user)
        user_branch_ids = user_branches.values_list('branch_id', flat=True)
        user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
        
        # Fetch loan and its EMI schedule (only from user's branches/agents)
        loan_app = get_object_or_404(
            LoanApplication.objects.filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).select_related('customer', 'branch'), 
            loan_ref_no=loan_ref_no
        )
        base_qs = LoanEMISchedule.objects.filter(loan_application=loan_app).order_by('installment_date')

        # Filter by schedule status if provided
        status = (self.request.GET.get('status') or 'all').lower()
        today = timezone.localdate()
        if status == 'upcoming':
            schedules = base_qs.filter(paid=False, installment_date__gt=today)
        elif status == 'due':
            schedules = base_qs.filter(paid=False, installment_date=today)
        elif status == 'overdue':
            schedules = base_qs.filter(paid=False, installment_date__lt=today)
        else:
            status = 'all'
            schedules = base_qs

        # Simple aggregates
        total_installments = base_qs.count()
        unpaid_installments = base_qs.filter(paid=False).count()
        total_amount = base_qs.aggregate(total=Sum('installment_amount'))['total'] or 0
        # As requested: by default 0, otherwise sum of PAID EMIs
        paid_sum = base_qs.filter(paid=True).aggregate(total=Sum('installment_amount'))['total'] or 0
        collected_amount = float(paid_sum)

        # Counts for tabs
        upcoming_count = base_qs.filter(paid=False, installment_date__gt=today).count()
        due_count = base_qs.filter(paid=False, installment_date=today).count()
        overdue_count = base_qs.filter(paid=False, installment_date__lt=today).count()

        context.update({
            'loan': loan_app,
            'schedules': schedules,
            'total_installments': total_installments,
            'unpaid_installments': unpaid_installments,
            'total_amount': float(total_amount),
            'collected_amount': collected_amount,
            'status': status,
            'schedule_counts': {
                'all': total_installments,
                'upcoming': upcoming_count,
                'due': due_count,
                'overdue': overdue_count,
            }
        })
        return context


@login_required
@require_permission('loan.change_loancategory')
def loan_close_requests_list(request):
    """HQ view: list LoanCloseRequest from user's branches/agents with optional status filter."""
    from django.core.paginator import Paginator
    status_filter = (request.GET.get('status') or '').strip().lower()
    valid_status = {'pending', 'approved', 'rejected', 'cancelled'}

    # Get branches and agents created by the logged-in HQ user
    user_branches = Branch.objects.filter(created_by=request.user)
    user_branch_ids = user_branches.values_list('branch_id', flat=True)
    user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

    qs = (
        LoanCloseRequest.objects
        .filter(
            Q(branch__in=user_branches) | 
            Q(loan_application__branch__in=user_branches) | 
            Q(loan_application__agent__in=user_agents)
        )
        .select_related('loan_application__customer', 'loan_application', 'branch', 'requested_by')
        .order_by('-requested_at')
    )
    if status_filter in valid_status:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(request.GET.get('page') or 1)
    try:
        page_links = list(
            paginator.get_elided_page_range(page_obj.number, on_each_side=2, on_ends=1)
        )
    except Exception:
        page_links = list(paginator.page_range)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    # Build a simple list for the template to avoid heavy ORM in templates
    rows = []
    for r in page_obj.object_list:
        la = r.loan_application
        rows.append({
            'request_id': r.request_id,
            'loan_ref_no': getattr(la, 'loan_ref_no', ''),
            'customer': getattr(getattr(la, 'customer', None), 'full_name', '') if la else '',
            'branch': getattr(r.branch, 'branch_name', '') if r.branch else '',
            'requested_by': getattr(r.requested_by, 'first_name', '') + ' ' + getattr(r.requested_by, 'last_name', '') if r.requested_by else '',
            'status': r.status,
            'requested_at': r.requested_at,
            'approved_at': r.approved_at,
        })

    context = {
        'title': 'Loan Close Requests',
        'status_filter': status_filter if status_filter in valid_status else '',
        'requests': rows,
        'valid_status': sorted(list(valid_status)),
        'page_obj': page_obj,
        'page_links': page_links,
        'query_string': query_string,
    }
    return render(request, 'loan-close/loan_close_requests.html', context)


@login_required
@require_permission('loan.change_loancategory')
@require_http_methods(["POST"])
def loan_close_request_action(request, request_id):
    """HQ view: action on a LoanCloseRequest.
    Accepts form field 'action' = 'approve' (default) or 'reject'.
    """
    # Get branches and agents created by the logged-in HQ user
    user_branches = Branch.objects.filter(created_by=request.user)
    user_branch_ids = user_branches.values_list('branch_id', flat=True)
    user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)
    
    # Filter loan close request to only allow actions on user's branches/agents
    lcr = get_object_or_404(
        LoanCloseRequest.objects.filter(
            Q(branch__in=user_branches) | 
            Q(loan_application__branch__in=user_branches) | 
            Q(loan_application__agent__in=user_agents)
        ),
        request_id=request_id
    )

    # Only pending requests can be transitioned
    if lcr.status != 'pending':
        return HttpResponseForbidden("Request is not pending.")

    action = (request.POST.get('action') or 'approve').strip().lower()

    if action == 'approve':
        from django.db import transaction

        with transaction.atomic():
            lcr = LoanCloseRequest.objects.select_for_update().select_related('loan_application').get(request_id=request_id)
            if lcr.status != 'pending':
                return HttpResponseForbidden("Request is not pending.")

            lcr.status = 'approved'
            # Set approver fields on approval
            if isinstance(request.user, HeadquarterEmployee):
                lcr.approved_by = request.user
            lcr.approved_at = timezone.now()
            lcr.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

            la = lcr.loan_application
            if la:
                la_update_fields = ['status']
                la.status = 'closed'
                if not la.approved_at:
                    la.approved_at = lcr.approved_at
                    la_update_fields.append('approved_at')
                la.save(update_fields=la_update_fields)

        # Email notification to customer (if email exists), with PDF attachment
        try:
            la = lcr.loan_application
            customer = getattr(la, 'customer', None)
            recipient = getattr(customer, 'email', None)
            if recipient:
                subject = f"Loan Close Approved • {la.loan_ref_no}"
                context = {
                    'customer_name': getattr(customer, 'full_name', ''),
                    'loan_ref_no': la.loan_ref_no,
                    'request_id': lcr.request_id,
                    'approved_at': lcr.approved_at,
                    'branch_name': getattr(lcr.branch, 'branch_name', ''),
                }
                # HTML and text body
                html_content = render_to_string('loan/loan_close_email.html', context)
                text_content = (
                    f"Dear {context['customer_name']}, your loan close request "
                    f"{lcr.request_id} for {la.loan_ref_no} has been approved."
                )
                from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or 'no-reply@sundaram.local'
                msg = EmailMultiAlternatives(subject, text_content, from_email, [recipient])
                msg.attach_alternative(html_content, "text/html")

                # Generate PDF from template if Playwright available
                pdf_bytes = None
                try:
                    pdf_html = render_to_string('loan/loan-close-pdf/loan-close-pdf.html', context)
                    if async_playwright is not None:
                        async def _render_pdf(html):
                            async with async_playwright() as p:
                                browser = await p.chromium.launch()
                                page = await browser.new_page()
                                await page.set_content(html, wait_until="networkidle")
                                pdf = await page.pdf(format="A4", print_background=True)
                                await browser.close()
                                return pdf
                        pdf_bytes = asyncio.run(_render_pdf(pdf_html))
                except Exception:
                    logging.getLogger(__name__).warning("Failed to generate loan close PDF", exc_info=True)

                if pdf_bytes:
                    filename = f"Loan_Close_Certificate_{la.loan_ref_no}.pdf"
                    msg.attach(filename, pdf_bytes, 'application/pdf')

                msg.send(fail_silently=True)
        except Exception:
            logging.getLogger(__name__).warning("Failed to send loan close approval email", exc_info=True)

    elif action == 'reject':
        lcr.status = 'rejected'
        # Clear approver fields on rejection
        lcr.approved_by = None
        lcr.approved_at = None
        # Optional: capture remarks from modal
        remarks = (request.POST.get('remarks') or '').strip()
        if remarks:
            lcr.remarks = remarks
        lcr.save(update_fields=['status', 'approved_by', 'approved_at', 'remarks', 'updated_at'])
    else:
        return HttpResponseForbidden("Invalid action.")

    # Preserve current status filter on redirect
    status_filter = (request.POST.get('status') or request.GET.get('status') or '').strip().lower()
    redirect_url = reverse_lazy('hq:loan_close_requests')
    if status_filter in {'pending', 'approved', 'rejected', 'cancelled'}:
        redirect_url = f"{redirect_url}?status={status_filter}"
    return redirect(redirect_url)


@require_http_methods(["GET"])
def hq_dashboard_data(request):
    """JSON endpoint for HQ dashboard cards and charts.
    Query params:
      - timeRange: 'day' | 'month' | 'year' (default: 'month')
      - year: int (defaults to current year)
      - month: 1..12 (defaults to current month)
      - day: 1..31 (defaults to today)
    """
    from calendar import monthrange, month_abbr
    from headquater.models import Branch
    from django.db.models import Q
    now = timezone.now()
    tz = timezone.get_current_timezone()

    time_range = request.GET.get('timeRange', 'month')
    try:
        year = int(request.GET.get('year') or now.year)
    except Exception:
        year = now.year
    try:
        month = int(request.GET.get('month') or now.month)
    except Exception:
        month = now.month
    try:
        day = int(request.GET.get('day') or now.day)
    except Exception:
        day = now.day

    # Compute window [start, next_start) for filtering by submitted_at
    if time_range == 'year':
        start = timezone.datetime(year, 1, 1, 0, 0, 0, tzinfo=tz)
        next_start = timezone.datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=tz)
    elif time_range == 'day':
        start = timezone.datetime(year, month, day, 0, 0, 0, tzinfo=tz)
        # next day
        from datetime import timedelta
        next_start = start + timedelta(days=1)
    else:  # 'month' default
        start = timezone.datetime(year, month, 1, 0, 0, 0, tzinfo=tz)
        nm = 1 if month == 12 else month + 1
        ny = year + 1 if month == 12 else year
        next_start = timezone.datetime(ny, nm, 1, 0, 0, 0, tzinfo=tz)

    # Get branches and agents created by the logged-in HQ user
    user_branches = Branch.objects.filter(created_by=request.user)
    user_branch_ids = user_branches.values_list('branch_id', flat=True)
    user_agents = Agent.objects.filter(branch_id__in=user_branch_ids)

    base_qs = LoanApplication.objects.filter(submitted_at__gte=start, submitted_at__lt=next_start).filter(
        Q(branch__in=user_branches) | Q(agent__in=user_agents)
    )

    savings_base_qs = SavingsAccountApplication.objects.filter(
        submitted_at__gte=start,
        submitted_at__lt=next_start,
    ).filter(
        Q(branch__in=user_branches) | Q(agent__in=user_agents)
    )

    # Cards
    # NOTE: Disbursed must be counted by disbursement timestamp, not application submitted date.
    # Also scope to active branches only.
    disbursed_statuses = ['disbursed', 'disbursed_fund_released']
    applied = base_qs.count()
    pending = base_qs.filter(status='branch_approved').count()
    approved = base_qs.filter(status='hq_approved').count()
    disbursed = LoanApplication.objects.filter(
        branch__status=True,
        disbursed_at__isnull=False,
        disbursed_at__gte=start,
        disbursed_at__lt=next_start,
        status__in=disbursed_statuses,
    ).filter(
        Q(branch__in=user_branches) | Q(agent__in=user_agents)
    ).count()
    rejected = base_qs.filter(status='hq_rejected').count()

    savings_applied = savings_base_qs.count()
    savings_pending = savings_base_qs.filter(status='branch_approved').count()
    savings_approved = savings_base_qs.filter(status='hq_approved').count()
    savings_disbursed = savings_base_qs.filter(status='disbursed_fund_released').count()
    savings_rejected = savings_base_qs.filter(status='hq_rejected').count()
    

    # Compute previous period window for percentage deltas
    from datetime import timedelta
    if time_range == 'year':
        prev_start = timezone.datetime(year - 1, 1, 1, 0, 0, 0, tzinfo=tz)
        prev_next = timezone.datetime(year, 1, 1, 0, 0, 0, tzinfo=tz)
    elif time_range == 'day':
        prev_start = start - timedelta(days=1)
        prev_next = start
    else:
        # month
        pm = 12 if month == 1 else month - 1
        py = year - 1 if month == 1 else year
        prev_start = timezone.datetime(py, pm, 1, 0, 0, 0, tzinfo=tz)
        pnm = 1 if pm == 12 else pm + 1
        pny = py + 1 if pm == 12 else py
        prev_next = timezone.datetime(pny, pnm, 1, 0, 0, 0, tzinfo=tz)

    prev_qs = LoanApplication.objects.filter(submitted_at__gte=prev_start, submitted_at__lt=prev_next).filter(
        Q(branch__in=user_branches) | Q(agent__in=user_agents)
    )
    prev_applied = prev_qs.count()
    prev_pending = prev_qs.filter(status='branch_approved').count()
    prev_approved = prev_qs.filter(status='hq_approved').count()
    prev_disbursed = LoanApplication.objects.filter(
        branch__status=True,
        disbursed_at__isnull=False,
        disbursed_at__gte=prev_start,
        disbursed_at__lt=prev_next,
        status__in=disbursed_statuses,
    ).filter(
        Q(branch__in=user_branches) | Q(agent__in=user_agents)
    ).count()
    prev_rejected = prev_qs.filter(status='hq_rejected').count()

    savings_prev_qs = SavingsAccountApplication.objects.filter(
        submitted_at__gte=prev_start,
        submitted_at__lt=prev_next,
    ).filter(
        Q(branch__in=user_branches) | Q(agent__in=user_agents)
    )
    savings_prev_applied = savings_prev_qs.count()
    savings_prev_pending = savings_prev_qs.filter(status='branch_approved').count()
    savings_prev_approved = savings_prev_qs.filter(status='hq_approved').count()
    savings_prev_disbursed = savings_prev_qs.filter(status='disbursed_fund_released').count()
    savings_prev_rejected = savings_prev_qs.filter(status='hq_rejected').count()
    

    def pct_change(cur, prev):
        try:
            if prev == 0:
                return 100.0 if cur > 0 else 0.0
            return round(((cur - prev) / prev) * 100.0, 2)
        except Exception:
            return 0.0

    def fmt_pct(val: float) -> str:
        sign = '+' if val > 0 else ''
        if float(val).is_integer():
            return f"{sign}{int(val)}%"
        return f"{sign}{val}%"

    applied_pct = pct_change(applied, prev_applied)
    pending_pct = pct_change(pending, prev_pending)
    approved_pct = pct_change(approved, prev_approved)
    disbursed_pct = pct_change(disbursed, prev_disbursed)
    rejected_pct = pct_change(rejected, prev_rejected)

    savings_applied_pct = pct_change(savings_applied, savings_prev_applied)
    savings_pending_pct = pct_change(savings_pending, savings_prev_pending)
    savings_approved_pct = pct_change(savings_approved, savings_prev_approved)
    savings_disbursed_pct = pct_change(savings_disbursed, savings_prev_disbursed)
    savings_rejected_pct = pct_change(savings_rejected, savings_prev_rejected)
    

    # Build mutually exclusive distribution for donut chart
    others = applied - (pending + approved + disbursed + rejected)
    if others < 0:
        others = 0

    loan_stats = {
        'applied': applied,
        'pending': pending,
        'approved': approved,
        'disbursed': disbursed,
        'rejected': rejected,
    }

    savings_stats = {
        'applied': savings_applied,
        'pending': savings_pending,
        'approved': savings_approved,
        'disbursed': savings_disbursed,
        'rejected': savings_rejected,
    }
    status_distribution = [applied, pending, approved, disbursed, rejected]
    

    # Trend series according to selected range (status counts)
    labels = []
    applied_series = []
    approved_series = []
    disbursed_series = []

    # Financial trends: total loan amount, total EMI scheduled, total EMI collected
    finance_labels = []
    loan_amount_series = []
    emi_scheduled_series = []
    emi_collected_series = []

    from django.db.models import Sum, Q
    from loan.models import LoanEMISchedule, EmiCollectionDetail

    if time_range == 'year':
        # 12 months of the selected year
        for m in range(1, 13):
            m_start = timezone.datetime(year, m, 1, 0, 0, 0, tzinfo=tz)
            nm = 1 if m == 12 else m + 1
            ny = year + 1 if m == 12 else year
            m_next = timezone.datetime(ny, nm, 1, 0, 0, 0, tzinfo=tz)
            labels.append(month_abbr[m])
            finance_labels.append(month_abbr[m])
            # status trends
            applied_series.append(LoanApplication.objects.filter(submitted_at__gte=m_start, submitted_at__lt=m_next).filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).count())
            approved_series.append(LoanApplication.objects.filter(submitted_at__gte=m_start, submitted_at__lt=m_next, status='hq_approved').filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).count())
            disbursed_series.append(
                LoanApplication.objects.filter(
                    branch__status=True,
                    disbursed_at__isnull=False,
                    disbursed_at__gte=m_start,
                    disbursed_at__lt=m_next,
                    status__in=disbursed_statuses,
                ).filter(
                    Q(branch__in=user_branches) | Q(agent__in=user_agents)
                ).count()
            )

            # financial trends
            loan_sum = LoanApplication.objects.filter(submitted_at__gte=m_start, submitted_at__lt=m_next).filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).aggregate(total=Sum('loan_details__loan_amount'))['total'] or 0
            loan_amount_series.append(float(loan_sum))
            emi_sum = LoanEMISchedule.objects.filter(installment_date__gte=m_start, installment_date__lt=m_next).filter(
                Q(loan_application__branch__in=user_branches) | Q(loan_application__agent__in=user_agents)
            ).aggregate(total=Sum('installment_amount'))['total'] or 0
            emi_scheduled_series.append(float(emi_sum))
            emi_col_sum = EmiCollectionDetail.objects.filter(
                verified_at__isnull=False,
                verified_at__gte=m_start,
                verified_at__lt=m_next,
                collected=True,
                status='verified',
            ).filter(
                (Q(collected_by_agent__in=user_agents) | Q(collected_by_branch__branch__in=user_branches)) &
                (Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False))
            ).aggregate(total=Sum('amount_received'))['total'] or 0
            emi_collected_series.append(float(emi_col_sum))
    elif time_range == 'day':
        # 24 hours of the selected day
        from datetime import timedelta
        for h in range(24):
            h_start = start + timedelta(hours=h)
            h_next = h_start + timedelta(hours=1)
            labels.append(f"{h:02d}")
            finance_labels.append(f"{h:02d}")
            applied_series.append(LoanApplication.objects.filter(submitted_at__gte=h_start, submitted_at__lt=h_next).filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).count())
            approved_series.append(LoanApplication.objects.filter(submitted_at__gte=h_start, submitted_at__lt=h_next, status='hq_approved').filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).count())
            disbursed_series.append(
                LoanApplication.objects.filter(
                    branch__status=True,
                    disbursed_at__isnull=False,
                    disbursed_at__gte=h_start,
                    disbursed_at__lt=h_next,
                    status__in=disbursed_statuses,
                ).filter(
                    Q(branch__in=user_branches) | Q(agent__in=user_agents)
                ).count()
            )

            loan_sum = LoanApplication.objects.filter(submitted_at__gte=h_start, submitted_at__lt=h_next).filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).aggregate(total=Sum('loan_details__loan_amount'))['total'] or 0
            loan_amount_series.append(float(loan_sum))
            emi_sum = LoanEMISchedule.objects.filter(installment_date__gte=h_start, installment_date__lt=h_next).filter(
                Q(loan_application__branch__in=user_branches) | Q(loan_application__agent__in=user_agents)
            ).aggregate(total=Sum('installment_amount'))['total'] or 0
            emi_scheduled_series.append(float(emi_sum))
            emi_col_sum = EmiCollectionDetail.objects.filter(
                verified_at__isnull=False,
                verified_at__gte=h_start,
                verified_at__lt=h_next,
                collected=True,
                status='verified',
            ).filter(
                (Q(collected_by_agent__in=user_agents) | Q(collected_by_branch__branch__in=user_branches)) &
                (Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False))
            ).aggregate(total=Sum('amount_received'))['total'] or 0
            emi_collected_series.append(float(emi_col_sum))
    else:
        # 'month': days in selected month
        from calendar import monthrange as mr
        days_in_month = mr(year, month)[1]
        from datetime import timedelta
        for d in range(1, days_in_month + 1):
            d_start = timezone.datetime(year, month, d, 0, 0, 0, tzinfo=tz)
            d_next = d_start + timedelta(days=1)
            labels.append(str(d))
            finance_labels.append(str(d))
            applied_series.append(LoanApplication.objects.filter(submitted_at__gte=d_start, submitted_at__lt=d_next).filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).count())
            approved_series.append(LoanApplication.objects.filter(submitted_at__gte=d_start, submitted_at__lt=d_next, status='hq_approved').filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).count())
            disbursed_series.append(
                LoanApplication.objects.filter(
                    branch__status=True,
                    disbursed_at__isnull=False,
                    disbursed_at__gte=d_start,
                    disbursed_at__lt=d_next,
                    status__in=disbursed_statuses,
                ).filter(
                    Q(branch__in=user_branches) | Q(agent__in=user_agents)
                ).count()
            )

            loan_sum = LoanApplication.objects.filter(submitted_at__gte=d_start, submitted_at__lt=d_next).filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).aggregate(total=Sum('loan_details__loan_amount'))['total'] or 0
            loan_amount_series.append(float(loan_sum))
            emi_sum = LoanEMISchedule.objects.filter(installment_date__gte=d_start, installment_date__lt=d_next).filter(
                Q(loan_application__branch__in=user_branches) | Q(loan_application__agent__in=user_agents)
            ).aggregate(total=Sum('installment_amount'))['total'] or 0
            emi_scheduled_series.append(float(emi_sum))
            emi_col_sum = EmiCollectionDetail.objects.filter(
                verified_at__isnull=False,
                verified_at__gte=d_start,
                verified_at__lt=d_next,
                collected=True,
                status='verified',
            ).filter(
                (Q(collected_by_agent__in=user_agents) | Q(collected_by_branch__branch__in=user_branches)) &
                (Q(collected_by_agent__isnull=False) | Q(collected_by_branch__isnull=False))
            ).aggregate(total=Sum('amount_received'))['total'] or 0
            emi_collected_series.append(float(emi_col_sum))

    # Maintain backward compatibility fields (primary trend shows Applied counts)
    monthly_trends = [{ 'month': labels[i], 'count': applied_series[i] } for i in range(len(labels))]

    payload = {
        'loanStats': loan_stats,
        'savingsStats': savings_stats,
        'monthlyTrends': monthly_trends,
        'statusDistribution': status_distribution,
        'trendsByStatus': {
            'labels': labels,
            'applied': applied_series,
            'approved': approved_series,
            'disbursed': disbursed_series,
        },
        'trendsFinance': {
            'labels': finance_labels,
            'loan_amounts': loan_amount_series,
            'emi_scheduled': emi_scheduled_series,
            'emi_collected': emi_collected_series,
        },
        'totalApplications': applied,
        'recentLoans': [
            {
                'loan_ref_no': la.loan_ref_no,
                'customer': (la.customer.full_name if la.customer else ''),
                'amount': float((la.loan_details.first().loan_amount) if la.loan_details.exists() else 0),
                'date': (la.submitted_at.strftime('%Y-%m-%d') if la.submitted_at else ''),
                'status': la.status,
            }
            for la in LoanApplication.objects.filter(
                Q(branch__in=user_branches) | Q(agent__in=user_agents)
            ).order_by('-submitted_at')[:5]
        ],
        'recentBranches': [
            {
                'branch_id': b.branch_id,
                'branch': b.branch_name,
                'city': b.city,
                'date': (b.created_at.strftime('%Y-%m-%d') if b.created_at else ''),
                'status': 'Active' if b.status else 'Inactive',
            }
            for b in (user_branches.filter(status=True)
                                 .annotate(app_count=Count('loan_applications'))
                                 .order_by('-app_count', '-created_at')[:5])
        ],
        'loanStatsDeltaPct': {
            'applied': applied_pct,
            'pending': pending_pct,
            'approved': approved_pct,
            'disbursed': disbursed_pct,
            'rejected': rejected_pct,
        },
        'loanStatsDeltaStr': {
            'applied': fmt_pct(applied_pct),
            'pending': fmt_pct(pending_pct),
            'approved': fmt_pct(approved_pct),
            'disbursed': fmt_pct(disbursed_pct),
            'rejected': fmt_pct(rejected_pct),
        },
        'savingsStatsDeltaPct': {
            'applied': savings_applied_pct,
            'pending': savings_pending_pct,
            'approved': savings_approved_pct,
            'disbursed': savings_disbursed_pct,
            'rejected': savings_rejected_pct,
        },
        'savingsStatsDeltaStr': {
            'applied': fmt_pct(savings_applied_pct),
            'pending': fmt_pct(savings_pending_pct),
            'approved': fmt_pct(savings_approved_pct),
            'disbursed': fmt_pct(savings_disbursed_pct),
            'rejected': fmt_pct(savings_rejected_pct),
        },
    }
    return JsonResponse(payload)


def loan_close_email(request):
    return render(request, 'loan-close-pdf/loan-close-pdf.html')


@login_required
@require_permission('loan.change_loancategory')
def chartOf_accountmanagement(request):
    # Preset modal state and instance for both GET and POST flows
    add_mode = request.GET.get('add')
    edit_id = request.GET.get('edit')
    instance = None
    if edit_id:
        instance = get_object_or_404(ChartOfAccount, pk=edit_id)
    if request.method == 'POST':
        # Handle delete first
        delete_id = request.POST.get('delete_id')
        if delete_id:
            obj = get_object_or_404(ChartOfAccount, pk=delete_id)
            if not obj.is_editable:
                messages.error(request, "This account cannot be deleted.")
            else:
                code = obj.code
                obj.delete()
                messages.success(request, f"Chart of Account '{code}' has been deleted successfully.")
            return redirect('hq:chartOf_accountmanagement')

        post_id = request.POST.get('account_id')
        if post_id:
            instance = get_object_or_404(ChartOfAccount, pk=post_id)
        form = ChartOfAccountForm(request.POST, instance=instance)

        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.sl_no:
                last_sl_no = ChartOfAccount.objects.filter(main_type=obj.main_type).order_by('-sl_no').first()
                obj.sl_no = last_sl_no.sl_no + 1 if last_sl_no else 1
            obj.save()
            messages.success(request, f"Chart of Account '{obj.code}' has been {'updated' if post_id else 'created'} successfully.")
            return redirect('hq:chartOf_accountmanagement')

    # GET flow
    accounts = ChartOfAccount.objects.all().order_by('main_type', 'sl_no')
    form = ChartOfAccountForm(instance=instance) if (add_mode or instance) else ChartOfAccountForm()

    show_modal = bool(add_mode or instance)
    modal_title = 'Edit Chart of Account' if instance else 'Create Chart of Account'
    modal_action = 'Update' if instance else 'Create'
    context = {
        'accounts': accounts,
        'form': form,
        'show_modal': show_modal,
        'modal_title': modal_title,
        'modal_action': modal_action,
        'edit_account_id': instance.id if instance else None,
    }
    return render(request, 'loan-manage/chart_of_accountManagement.html', context)
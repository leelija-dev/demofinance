
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Sum
from django.utils.decorators import method_decorator
from django.template.loader import render_to_string
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView
from django.conf import settings

from decimal import Decimal
from datetime import timedelta
import threading

from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections

from .decorators import require_permissions_for_class, require_permission
from .forms import SavingTypeForm, OneTimeDepositForm, DailyProductForm

from savings.models import SavingType, OneTimeDeposit, DailyProduct, SavingsAccountApplication, SavingsCollection, SavingsAgentAssign
from loan.models import DocumentRequest
from headquater.models import Branch
from agent.models import Agent

from branch.models import BranchEmployee, BranchAccount, BranchTransaction

from savings.views import _get_rd_interest_as_of


def _send_savings_surrender_approved_email_in_background(application_id: str, principal_amount: str) -> None:
    close_old_connections()
    try:
        app = (
            SavingsAccountApplication.objects
            .select_related('customer', 'agent', 'branch')
            .filter(application_id=application_id)
            .first()
        )
        if app is None:
            return

        customer = app.customer

        recipient_list: list[str] = []
        if getattr(customer, 'email', None):
            email = (customer.email or '').strip()
            if email:
                recipient_list.append(email)

        if getattr(app, 'agent', None) and getattr(app.agent, 'email', None):
            email = (app.agent.email or '').strip()
            if email and email not in recipient_list:
                recipient_list.append(email)

        if getattr(app, 'branch', None) and getattr(app.branch, 'email', None):
            email = (app.branch.email or '').strip()
            if email and email not in recipient_list:
                recipient_list.append(email)

        hq_email = (getattr(settings, 'HQ_NOTIFICATION_EMAIL', '') or '').strip()
        if hq_email and hq_email not in recipient_list:
            recipient_list.append(hq_email)

        if not recipient_list:
            return

        subject = f"Savings Surrender Approved - {app.account_id or app.application_id}"
        message_text = (
            "SUNDARAM\n"
            "========\n\n"
            "Savings surrender request approved.\n\n"
            f"Application ID: {app.application_id}\n"
            f"Account ID: {app.account_id or 'N/A'}\n"
            f"Customer Name: {getattr(customer, 'full_name', 'N/A') or 'N/A'}\n"
            f"Payout Amount (Principal Only): ₹{principal_amount}\n"
            f"Approved On: {timezone.now().date().strftime('%d/%m/%Y')}\n"
        )

        message_html = (
            "<div style=\"font-family:Arial,sans-serif;line-height:1.5;\">"
            "<h2 style=\"margin:0 0 8px 0;\">SUNDARAM</h2>"
            "<p style=\"margin:0 0 12px 0;\">Savings surrender request approved.</p>"
            "<table style=\"border-collapse:collapse;\">"
            f"<tr><td style=\"padding:4px 10px 4px 0;\"><b>Application ID</b></td><td style=\"padding:4px 0;\">{app.application_id}</td></tr>"
            f"<tr><td style=\"padding:4px 10px 4px 0;\"><b>Account ID</b></td><td style=\"padding:4px 0;\">{app.account_id or 'N/A'}</td></tr>"
            f"<tr><td style=\"padding:4px 10px 4px 0;\"><b>Customer</b></td><td style=\"padding:4px 0;\">{getattr(customer, 'full_name', 'N/A') or 'N/A'}</td></tr>"
            f"<tr><td style=\"padding:4px 10px 4px 0;\"><b>Payout</b></td><td style=\"padding:4px 0;\">₹{principal_amount} (Principal Only)</td></tr>"
            f"<tr><td style=\"padding:4px 10px 4px 0;\"><b>Approved On</b></td><td style=\"padding:4px 0;\">{timezone.now().date().strftime('%d/%m/%Y')}</td></tr>"
            "</table>"
            "<p style=\"margin-top:16px;color:#666;font-size:12px;\">This is an automated notification from Sundaram Savings Management System.</p>"
            "</div>"
        )

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        for recipient in recipient_list:
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=message_text,
                    from_email=from_email,
                    to=[recipient],
                    reply_to=[from_email],
                )
                email.attach_alternative(message_html, 'text/html')
                email.send(fail_silently=False)
            except Exception:
                continue
    finally:
        close_old_connections()


def _send_savings_hq_approved_email_in_background(application_id: str) -> None:
    close_old_connections()
    try:
        app = (
            SavingsAccountApplication.objects
            .select_related('customer', 'agent', 'branch')
            .filter(application_id=application_id)
            .first()
        )
        if app is None:
            return

        customer = app.customer

        recipient_list: list[str] = []
        if getattr(customer, 'email', None):
            email = (customer.email or '').strip()
            if email:
                recipient_list.append(email)

        if getattr(app, 'agent', None) and getattr(app.agent, 'email', None):
            email = (app.agent.email or '').strip()
            if email and email not in recipient_list:
                recipient_list.append(email)

        if getattr(app, 'branch', None) and getattr(app.branch, 'email', None):
            email = (app.branch.email or '').strip()
            if email and email not in recipient_list:
                recipient_list.append(email)

        hq_email = (getattr(settings, 'HQ_NOTIFICATION_EMAIL', '') or '').strip()
        if hq_email and hq_email not in recipient_list:
            recipient_list.append(hq_email)

        if not recipient_list:
            return

        tenure_unit = None
        try:
            if (app.product_type or '').lower() == 'fd' and app.product_id:
                tenure_unit = OneTimeDeposit.objects.filter(one_time_deposit_id=app.product_id).values_list('tenure_unit', flat=True).first()
            elif (app.product_type or '').lower() == 'rd' and app.product_id:
                tenure_unit = DailyProduct.objects.filter(daily_product_id=app.product_id).values_list('tenure_unit', flat=True).first()
        except Exception:
            tenure_unit = None

        logo_base64 = None

        product_type = (app.product_type or '').strip().lower()
        subject = f"Savings Account Approved - {app.account_id or app.application_id}"

        context = {
            'purpose_flag': 'savings_hq_approved',
            'sub_header': 'Savings Account Approved Successfully',
            'application_id': app.application_id,
            'account_id': app.account_id,
            'customer_name': getattr(customer, 'full_name', 'N/A') or 'N/A',
            'customer_contact': getattr(customer, 'contact', 'N/A') or 'N/A',
            'product_type': product_type.upper() if product_type else 'N/A',
            'product_id': app.product_id or 'N/A',
            'installment_amount': app.installment_amount,
            'interest_rate': app.interest_rate,
            'tenure': app.tenure,
            'tenure_unit': tenure_unit,
            'account_opened_at': app.account_opened_at,
            'hq_approved_at': app.hq_approved_at,
            'maturity_date': app.maturity_date,
            'maturity_amount': app.maturity_amount,
            'branch_name': getattr(app.branch, 'branch_name', None) or getattr(app.branch, 'name', 'N/A') if getattr(app, 'branch', None) else 'N/A',
            'agent_name': getattr(app.agent, 'name', 'N/A') if getattr(app, 'agent', None) else 'N/A',
            'logo_base64': logo_base64,
        }

        message_text = (
            "SUNDARAM\n"
            "========\n\n"
            "Savings account approved successfully.\n\n"
            f"Application ID: {context['application_id']}\n"
            f"Account ID: {context['account_id'] or 'N/A'}\n"
            f"Customer Name: {context['customer_name']}\n"
            f"Contact Number: {context['customer_contact']}\n"
            f"Product Type: {context['product_type']}\n"
        )

        message_html = None
        try:
            message_html = render_to_string('savings/savings_application_email.html', context)
        except Exception:
            message_html = None

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        for recipient in recipient_list:
            try:
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=message_text,
                    from_email=from_email,
                    to=[recipient],
                    reply_to=[from_email],
                )
                if message_html:
                    email.attach_alternative(message_html, 'text/html')
                email.send(fail_silently=False)
            except Exception:
                continue
    finally:
        close_old_connections()


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsBranchApprovedListView(LoginRequiredMixin, TemplateView):
    template_name = 'savings/savings_branch_approved.html'

    def get(self, request, *args, **kwargs):
        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('savings/partials/savings_branch_approved_rows.html', context, request=request)
            return HttpResponse(html)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = (
            SavingsAccountApplication.objects
            .filter(status__in=['branch_approved', 'branch_resubmitted', 'document_requested_by_hq', 'resubmitted'])
            .select_related('customer', 'branch', 'agent')
            .order_by('-submitted_at')
        )

        paginator = Paginator(qs, 15)
        page_number = self.request.GET.get('page') or 1
        page_obj = paginator.get_page(page_number)
        applications = list(page_obj.object_list)

        fd_ids = [a.product_id for a in applications if a.product_type == 'fd' and a.product_id]
        rd_ids = [a.product_id for a in applications if a.product_type == 'rd' and a.product_id]

        fd_unit_by_id = dict(
            OneTimeDeposit.objects.filter(one_time_deposit_id__in=fd_ids).values_list('one_time_deposit_id', 'tenure_unit')
        )
        rd_unit_by_id = dict(
            DailyProduct.objects.filter(daily_product_id__in=rd_ids).values_list('daily_product_id', 'tenure_unit')
        )

        for a in applications:
            if a.product_type == 'fd':
                a.tenure_unit = fd_unit_by_id.get(a.product_id)
            elif a.product_type == 'rd':
                a.tenure_unit = rd_unit_by_id.get(a.product_id)

        context['applications'] = applications
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        return context



@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsSurrenderRequestsListView(LoginRequiredMixin, TemplateView):

    template_name = 'savings/surrender_requests.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('savings/partials/surrender_requests_rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        branch_id = (self.request.GET.get('branch_id') or '').strip()
        product_type = (self.request.GET.get('product_type') or '').strip().lower()
        q = (self.request.GET.get('q') or '').strip()

        qs = (

            SavingsAccountApplication.objects

            .filter(account_id__isnull=False, status='hq_approved', surrender_status='processing')

            .select_related('customer', 'branch', 'agent')

            .order_by('-last_update', '-submitted_at')

        )

        if product_type in {'rd', 'fd'}:
            qs = qs.filter(product_type=product_type)

        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        if q:
            qs = qs.filter(
                Q(account_id__icontains=q)
                | Q(application_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__customer_id__icontains=q)
                | Q(branch__branch_name__icontains=q)
                | Q(agent__full_name__icontains=q)
                | Q(agent__agent_id__icontains=q)
            )

        paginator = Paginator(qs, 15)

        page_number = self.request.GET.get('page') or 1

        page_obj = paginator.get_page(page_number)

        accounts = list(page_obj.object_list)

        context['accounts'] = accounts

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['branches'] = Branch.objects.all().order_by('branch_name')
        context['selected_branch_id'] = branch_id
        context['selected_product_type'] = product_type
        context['q'] = q

        return context



@require_permissions_for_class('savings.change_savingsaccountapplication')
class HQSavingsSurrenderDecisionView(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):

        application_id = (kwargs.get('application_id') or '').strip()

        decision = (request.POST.get('decision') or '').strip().lower()

        if decision not in {'approve', 'reject'}:
            messages.error(request, 'Invalid decision.', extra_tags='permerror')
            return redirect('hq:hq_savings_surrender_requests')



        with transaction.atomic():

            account = (

                SavingsAccountApplication.objects

                .select_for_update()

                .filter(application_id=application_id)

                .first()

            )

            if account is None:
                messages.error(request, 'Savings account not found.', extra_tags='permerror')
                return redirect('hq:hq_savings_surrender_requests')



            current_status = (account.surrender_status or 'none').strip()

            if current_status != 'processing':
                messages.error(request, 'Surrender request is not in processing state.', extra_tags='permerror')
                return redirect('hq:hq_savings_surrender_requests')




            if decision == 'reject':

                account.surrender_status = 'rejected'

                account.save(update_fields=['surrender_status', 'last_update'])

                messages.success(request, 'Surrender request rejected.')

                return redirect('hq:hq_savings_surrender_requests')


            account.surrender_status = 'approved'
            account.save(update_fields=['surrender_status', 'last_update'])
            messages.success(request, 'Surrender approved. Branch can withdraw/close the account.')



        return redirect('hq:hq_savings_surrender_requests')


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsSurrenderAccountDetailView(LoginRequiredMixin, TemplateView):

    template_name = 'savings/surrender_account_detail.html'


    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('savings/partials/surrender_account_detail_rows.html', context, request=request)

            return HttpResponse(html)

        return super().get(request, *args, **kwargs)


    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        application_id = (kwargs.get('application_id') or '').strip()

        account = (

            SavingsAccountApplication.objects

            .select_related('customer', 'agent', 'branch')

            .filter(application_id=application_id)

            .first()

        )

        if account is None:

            raise PermissionDenied


        collections_qs = (

            SavingsCollection.objects

            .filter(account=account)

            .select_related('collected_by_branch_employee', 'collected_by_agent', 'branch', 'agent')

            .order_by('-is_expected', 'installment_no', 'collection_date', 'created_at')

        )

        paginator = Paginator(collections_qs, 15)

        page_number = self.request.GET.get('page') or 1

        page_obj = paginator.get_page(page_number)

        collections = list(page_obj.object_list)

        total_amount = (

            collections_qs

            .filter(is_collected=True)

            .aggregate(total=Sum('amount'))

            .get('total')

            or Decimal('0')

        )

        today = timezone.now().date()

        rd_summary = None

        if account.product_type == 'rd':

            rd_summary = _get_rd_interest_as_of(account, today)

        fd_principal = None

        if account.product_type == 'fd':

            fd_principal = (

                collections_qs

                .filter(collection_type='fd_deposit', is_collected=True)

                .aggregate(total=Sum('amount'))

                .get('total')

            )


        context['account'] = account

        referer = (self.request.META.get('HTTP_REFERER') or '').strip()
        context['back_url'] = referer if referer else reverse('hq:hq_savings_surrender_requests')

        context['collections'] = collections

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['total_amount'] = total_amount

        context['today'] = today

        context['rd_summary'] = rd_summary

        context['fd_principal'] = fd_principal

        return context


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsAllOpenedAccountsListView(LoginRequiredMixin, TemplateView):
    template_name = 'savings/savings_accounts_all.html'

    def get(self, request, *args, **kwargs):
        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('savings/partials/savings_accounts_rows.html', context, request=request)
            return HttpResponse(html)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        product_type = (self.request.GET.get('product_type') or '').strip().lower()
        branch_id = (self.request.GET.get('branch_id') or '').strip()
        agent_id = (self.request.GET.get('agent_id') or '').strip()
        account_status = (self.request.GET.get('account_status') or '').strip().lower()
        q = (self.request.GET.get('q') or '').strip()

        qs = SavingsAccountApplication.objects.filter(account_id__isnull=False)

        if product_type in {'rd', 'fd'}:
            qs = qs.filter(product_type=product_type)

        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        if agent_id:
            qs = qs.filter(agent_id=agent_id)

        if account_status in {'active', 'inactive'}:
            inactive_q = Q(status='inactive') | Q(withdraw_date__isnull=False) | Q(withdraw_amount__isnull=False)
            if account_status == 'inactive':
                qs = qs.filter(inactive_q)
            else:
                qs = qs.exclude(inactive_q)

        if q:
            qs = qs.filter(
                Q(account_id__icontains=q)
                | Q(application_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__customer_id__icontains=q)
                | Q(branch__branch_name__icontains=q)
                | Q(agent__full_name__icontains=q)
                | Q(agent__agent_id__icontains=q)
            )

        qs = (
            qs.select_related('customer', 'agent', 'branch')
            .order_by('-hq_approved_at', '-submitted_at')
        )

        paginator = Paginator(qs, 15)
        page_number = self.request.GET.get('page') or 1
        page_obj = paginator.get_page(page_number)
        accounts = list(page_obj.object_list)

        context['accounts'] = accounts
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['accounts_title'] = 'All Opened Accounts'
        context['accounts_page_id'] = 'hqSavingsAllOpenedAccounts'
        context['from_source'] = 'accounts_all'
        context['branches'] = Branch.objects.all().order_by('branch_name')
        agents_qs = Agent.objects.filter(status='active').order_by('full_name')
        if branch_id:
            agents_qs = agents_qs.filter(branch_id=branch_id)
        context['agents'] = agents_qs
        context['selected_product_type'] = product_type
        context['selected_branch_id'] = branch_id
        context['selected_agent_id'] = agent_id
        context['selected_account_status'] = account_status
        context['q'] = q
        return context


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsRDAccountsListView(LoginRequiredMixin, TemplateView):
    template_name = 'savings/savings_accounts_rd.html'

    def get(self, request, *args, **kwargs):
        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('savings/partials/savings_accounts_rows.html', context, request=request)
            return HttpResponse(html)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = (
            SavingsAccountApplication.objects
            .filter(account_id__isnull=False, product_type='rd')
            .select_related('customer', 'agent', 'branch')
            .order_by('-hq_approved_at', '-submitted_at')
        )

        paginator = Paginator(qs, 15)
        page_number = self.request.GET.get('page') or 1
        page_obj = paginator.get_page(page_number)
        accounts = list(page_obj.object_list)

        context['accounts'] = accounts
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['accounts_title'] = 'RD Accounts'
        context['accounts_page_id'] = 'hqSavingsRDAccounts'
        context['from_source'] = 'accounts_rd'
        return context


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsFDAccountsListView(LoginRequiredMixin, TemplateView):
    template_name = 'savings/savings_accounts_fd.html'

    def get(self, request, *args, **kwargs):
        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('savings/partials/savings_accounts_rows.html', context, request=request)
            return HttpResponse(html)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = (
            SavingsAccountApplication.objects
            .filter(account_id__isnull=False, product_type='fd')
            .select_related('customer', 'agent', 'branch')
            .order_by('-hq_approved_at', '-submitted_at')
        )

        paginator = Paginator(qs, 15)
        page_number = self.request.GET.get('page') or 1
        page_obj = paginator.get_page(page_number)
        accounts = list(page_obj.object_list)

        context['accounts'] = accounts
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['accounts_title'] = 'FD Accounts'
        context['accounts_page_id'] = 'hqSavingsFDAccounts'
        context['from_source'] = 'accounts_fd'
        return context


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsHQApprovedListView(LoginRequiredMixin, TemplateView):
    template_name = 'savings/savings_hq_approved.html'

    def get(self, request, *args, **kwargs):
        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('savings/partials/savings_hq_approved_rows.html', context, request=request)
            return HttpResponse(html)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        product_type = (self.request.GET.get('product_type') or '').strip().lower()
        branch_id = (self.request.GET.get('branch_id') or '').strip()
        agent_id = (self.request.GET.get('agent_id') or '').strip()
        q = (self.request.GET.get('q') or '').strip()

        qs = (
            SavingsAccountApplication.objects
            .filter(status='hq_approved')
            .select_related('customer', 'branch', 'agent')
            .order_by('-hq_approved_at', '-submitted_at')
        )

        if product_type in {'rd', 'fd'}:
            qs = qs.filter(product_type=product_type)

        if branch_id:
            qs = qs.filter(branch_id=branch_id)

        if agent_id:
            qs = qs.filter(agent_id=agent_id)

        if q:
            qs = qs.filter(
                Q(account_id__icontains=q)
                | Q(application_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__customer_id__icontains=q)
                | Q(branch__branch_name__icontains=q)
                | Q(agent__full_name__icontains=q)
                | Q(agent__agent_id__icontains=q)
            )

        paginator = Paginator(qs, 15)
        page_number = self.request.GET.get('page') or 1
        page_obj = paginator.get_page(page_number)
        applications = list(page_obj.object_list)

        fd_ids = [a.product_id for a in applications if a.product_type == 'fd' and a.product_id]
        rd_ids = [a.product_id for a in applications if a.product_type == 'rd' and a.product_id]

        fd_unit_by_id = dict(
            OneTimeDeposit.objects.filter(one_time_deposit_id__in=fd_ids).values_list('one_time_deposit_id', 'tenure_unit')
        )
        rd_unit_by_id = dict(
            DailyProduct.objects.filter(daily_product_id__in=rd_ids).values_list('daily_product_id', 'tenure_unit')
        )

        for a in applications:
            if a.product_type == 'fd':
                a.tenure_unit = fd_unit_by_id.get(a.product_id)
            elif a.product_type == 'rd':
                a.tenure_unit = rd_unit_by_id.get(a.product_id)

        context['applications'] = applications
        context['page_obj'] = page_obj
        context['paginator'] = paginator

        context['branches'] = Branch.objects.all().order_by('branch_name')
        agents_qs = Agent.objects.filter(status='active').order_by('full_name')
        if branch_id:
            agents_qs = agents_qs.filter(branch_id=branch_id)
        context['agents'] = agents_qs

        context['selected_product_type'] = product_type
        context['selected_branch_id'] = branch_id
        context['selected_agent_id'] = agent_id
        context['q'] = q
        return context


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsRejectedListView(LoginRequiredMixin, TemplateView):
    template_name = 'savings/savings_rejected.html'

    def get(self, request, *args, **kwargs):
        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('savings/partials/savings_rejected_rows.html', context, request=request)
            return HttpResponse(html)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = (
            SavingsAccountApplication.objects
            .filter(status='hq_rejected')
            .select_related('customer', 'branch', 'agent')
            .order_by('-last_update', '-submitted_at')
        )

        paginator = Paginator(qs, 15)
        page_number = self.request.GET.get('page') or 1
        page_obj = paginator.get_page(page_number)
        applications = list(page_obj.object_list)

        fd_ids = [a.product_id for a in applications if a.product_type == 'fd' and a.product_id]
        rd_ids = [a.product_id for a in applications if a.product_type == 'rd' and a.product_id]

        fd_unit_by_id = dict(
            OneTimeDeposit.objects.filter(one_time_deposit_id__in=fd_ids).values_list('one_time_deposit_id', 'tenure_unit')
        )
        rd_unit_by_id = dict(
            DailyProduct.objects.filter(daily_product_id__in=rd_ids).values_list('daily_product_id', 'tenure_unit')
        )

        for a in applications:
            if a.product_type == 'fd':
                a.tenure_unit = fd_unit_by_id.get(a.product_id)
            elif a.product_type == 'rd':
                a.tenure_unit = rd_unit_by_id.get(a.product_id)

        context['applications'] = applications
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        return context


@require_permissions_for_class('savings.view_savingsaccountapplication')
class HQSavingsApplicationDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'savings/savings_application_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application_id = kwargs.get('application_id')

        app = (
            SavingsAccountApplication.objects
            .filter(application_id=application_id)
            .select_related('customer', 'agent', 'branch', 'customer__address')
            .first()
        )
        if not app:
            raise PermissionDenied

        tenure_unit = None
        if app.product_type == 'fd' and app.product_id:
            tenure_unit = OneTimeDeposit.objects.filter(one_time_deposit_id=app.product_id).values_list('tenure_unit', flat=True).first()
        elif app.product_type == 'rd' and app.product_id:
            tenure_unit = DailyProduct.objects.filter(daily_product_id=app.product_id).values_list('tenure_unit', flat=True).first()
        app.tenure_unit = tenure_unit

        documents = None
        try:
            documents = app.documents
        except Exception:
            documents = None

        pending_requested_doc_types = set(
            DocumentRequest.objects
            .filter(savings_application=app, is_resolved=False)
            .values_list('document_type', flat=True)
        )

        from_source = (self.request.GET.get('from') or '').strip().lower()
        hide_request_document = from_source in {'hq_approved', 'rejected', 'accounts_all', 'accounts_rd', 'accounts_fd'}

        back_url = reverse('hq:hq_savings_branch_approved')
        if from_source == 'hq_approved':
            back_url = reverse('hq:hq_savings_hq_approved')
        elif from_source == 'rejected':
            back_url = reverse('hq:hq_savings_rejected')
        elif from_source == 'accounts_all':
            back_url = reverse('hq:hq_savings_accounts_all')
        elif from_source == 'accounts_rd':
            back_url = reverse('hq:hq_savings_accounts_rd')
        elif from_source == 'accounts_fd':
            back_url = reverse('hq:hq_savings_accounts_fd')

        context['application'] = app
        context['documents'] = documents
        context['pending_requested_doc_types'] = pending_requested_doc_types
        context['is_hq_view'] = True
        context['hide_request_document'] = hide_request_document
        context['back_url'] = back_url
        return context


@require_permissions_for_class('savings.change_savingsaccountapplication')
class HQApproveSavingsApplicationView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        application_id = kwargs.get('application_id')
        app = get_object_or_404(SavingsAccountApplication, application_id=application_id)

        if app.status not in ['branch_approved', 'branch_resubmitted']:
            return redirect('hq:hq_savings_application_detail', application_id=application_id)

        with transaction.atomic():
            app = SavingsAccountApplication.objects.select_for_update().get(application_id=application_id)

            if not app.account_id:
                prefix = 'RD-' if app.product_type == 'rd' else 'FD-'
                short_uuid = str(__import__('uuid').uuid4())[:8].upper()
                app.account_id = f"{prefix}{short_uuid}"

            now = timezone.now()
            if not app.account_opened_at:
                app.account_opened_at = now
            if not app.hq_approved_at:
                app.hq_approved_at = now
            if not app.hq_approved_by_id:
                app.hq_approved_by = request.user

            app.status = 'hq_approved'
            app.save(update_fields=['account_id', 'account_opened_at', 'hq_approved_at', 'hq_approved_by', 'status', 'last_update'])

            if app.product_type == 'fd':
                product = OneTimeDeposit.objects.filter(one_time_deposit_id=app.product_id, is_active=True).first()
                if product and product.payable_amount is not None:
                    unit_days = 30
                    if product.tenure_unit in ['daily', 'days']:
                        unit_days = 1
                    elif product.tenure_unit in ['weekly', 'weeks']:
                        unit_days = 7
                    elif product.tenure_unit in ['yearly', 'years']:
                        unit_days = 365

                    start_date = app.hq_approved_at.date()
                    app.maturity_date = start_date + timedelta(days=unit_days * int(product.tenure or 0))
                    app.maturity_amount = Decimal(str(product.payable_amount)).quantize(Decimal('0.01'))
                    app.save(update_fields=['maturity_date', 'maturity_amount', 'last_update'])

            if app.product_type == 'rd':
                app.ensure_expected_collections_schedule()

                if app.agent_id:
                    latest_assignment = (
                        SavingsAgentAssign.objects
                        .filter(account=app, is_active=True)
                        .first()
                    )

                    if latest_assignment is None or latest_assignment.agent_id != app.agent_id:
                        SavingsAgentAssign.objects.create(
                            account=app,
                            agent=app.agent,
                            assigned_by=None,
                            is_active=True,
                        )

                    SavingsCollection.objects.filter(
                        account=app,
                        agent__isnull=True,
                    ).update(agent=app.agent)
        transaction.on_commit(
            lambda: threading.Thread(
                target=_send_savings_hq_approved_email_in_background,
                args=(application_id,),
                daemon=True,
            ).start()
        )
        return redirect('hq:hq_savings_branch_approved')


@require_permissions_for_class('savings.change_savingsaccountapplication')
@method_decorator(csrf_exempt, name='dispatch')
class HQSavingsDocumentRequestAPI(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        import json

        data = json.loads(request.body.decode('utf-8'))
        application_id = data.get('application_id')
        document_type = data.get('document_type')
        reason = data.get('reason')
        comment = data.get('comment', '')

        if not (application_id and document_type and reason):
            return JsonResponse({'success': False, 'error': 'Missing required fields.'}, status=400)

        try:
            savings_app = SavingsAccountApplication.objects.get(application_id=application_id)
            DocumentRequest.objects.create(
                savings_application=savings_app,
                document_type=document_type,
                reason=reason,
                comment=comment,
                requested_by=None,
                requested_by_hq=request.user if request.user.is_authenticated else None,
                branch=savings_app.branch,
            )
            savings_app.status = 'document_requested_by_hq'
            savings_app.save(update_fields=['status', 'last_update'])
            return JsonResponse({'success': True, 'new_status': 'document_requested_by_hq'})
        except SavingsAccountApplication.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Savings application not found.'}, status=404)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@require_permission('savings.change_savingtype')
def saving_management(request):
    saving_types = SavingType.objects.all().order_by('name')
    one_time_deposits = OneTimeDeposit.objects.all().order_by('deposit_amount', 'tenure', 'tenure_unit', 'payable_amount')
    daily_products = DailyProduct.objects.all().order_by('deposit_amount', 'interest_rate', 'tenure', 'tenure_unit')

    show_type_modal = False
    show_one_time_modal = False
    show_daily_modal = False

    type_form = SavingTypeForm()
    one_time_form = OneTimeDepositForm()
    daily_form = DailyProductForm()

    type_modal_action = ''
    type_modal_title = ''
    one_time_modal_action = ''
    one_time_modal_title = ''
    daily_modal_action = ''
    daily_modal_title = ''

    edit_type_id = request.GET.get('edit_type')
    edit_one_time_id = request.GET.get('edit_one_time')
    edit_daily_id = request.GET.get('edit_daily')

    form_kind = (request.POST.get('form_kind') or '').strip()

    if request.method == 'POST' and form_kind == 'type':
        if request.POST.get('type_id'):
            inst = get_object_or_404(SavingType, type_id=request.POST['type_id'])
            type_form = SavingTypeForm(request.POST, instance=inst)
            type_modal_action = 'Edit'
            type_modal_title = 'Edit Saving Type'
        else:
            type_form = SavingTypeForm(request.POST)
            type_modal_action = 'Add'
            type_modal_title = 'Add Saving Type'
        show_type_modal = True
        if type_form.is_valid():
            obj = type_form.save(commit=False)
            if hasattr(obj, 'created_by'):
                obj.created_by = request.user
            obj.save()
            messages.success(request, f"Saving type {type_modal_action.lower()}ed successfully!")
            return redirect('hq:saving_management')
        messages.error(request, 'Failed to save saving type. Please check the form.')

    if request.method == 'POST' and form_kind == 'one_time':
        if request.POST.get('one_time_deposit_id'):
            inst = get_object_or_404(OneTimeDeposit, one_time_deposit_id=request.POST['one_time_deposit_id'])
            one_time_form = OneTimeDepositForm(request.POST, instance=inst)
            one_time_modal_action = 'Edit'
            one_time_modal_title = 'Edit One Time Deposit'
        else:
            one_time_form = OneTimeDepositForm(request.POST)
            one_time_modal_action = 'Add'
            one_time_modal_title = 'Add One Time Deposit'
        show_one_time_modal = True
        if one_time_form.is_valid():
            obj = one_time_form.save(commit=False)
            if hasattr(obj, 'created_by'):
                obj.created_by = request.user
            obj.save()
            messages.success(request, f"One time deposit {one_time_modal_action.lower()}ed successfully!")
            return redirect('hq:saving_management')
        messages.error(request, 'Failed to save one time deposit. Please check the form.')

    if request.method == 'POST' and form_kind == 'daily':
        if request.POST.get('daily_product_id'):
            inst = get_object_or_404(DailyProduct, daily_product_id=request.POST['daily_product_id'])
            daily_form = DailyProductForm(request.POST, instance=inst)
            daily_modal_action = 'Edit'
            daily_modal_title = 'Edit Daily Product'
        else:
            daily_form = DailyProductForm(request.POST)
            daily_modal_action = 'Add'
            daily_modal_title = 'Add Daily Product'
        show_daily_modal = True
        if daily_form.is_valid():
            obj = daily_form.save(commit=False)
            if hasattr(obj, 'created_by'):
                obj.created_by = request.user
            obj.save()
            messages.success(request, f"Daily product {daily_modal_action.lower()}ed successfully!")
            return redirect('hq:saving_management')
        messages.error(request, 'Failed to save daily product. Please check the form.')

    if edit_type_id:
        inst = get_object_or_404(SavingType, type_id=edit_type_id)
        type_form = SavingTypeForm(instance=inst)
        type_modal_action = 'Edit'
        type_modal_title = 'Edit Saving Type'
        show_type_modal = True
    elif request.GET.get('add_type') == '1':
        type_form = SavingTypeForm()
        type_modal_action = 'Add'
        type_modal_title = 'Add Saving Type'
        show_type_modal = True

    if edit_one_time_id:
        inst = get_object_or_404(OneTimeDeposit, one_time_deposit_id=edit_one_time_id)
        one_time_form = OneTimeDepositForm(instance=inst)
        one_time_modal_action = 'Edit'
        one_time_modal_title = 'Edit One Time Deposit'
        show_one_time_modal = True
    elif request.GET.get('add_one_time') == '1':
        one_time_form = OneTimeDepositForm()
        one_time_modal_action = 'Add'
        one_time_modal_title = 'Add One Time Deposit'
        show_one_time_modal = True

    if edit_daily_id:
        inst = get_object_or_404(DailyProduct, daily_product_id=edit_daily_id)
        daily_form = DailyProductForm(instance=inst)
        daily_modal_action = 'Edit'
        daily_modal_title = 'Edit Daily Product'
        show_daily_modal = True
    elif request.GET.get('add_daily') == '1':
        daily_form = DailyProductForm()
        daily_modal_action = 'Add'
        daily_modal_title = 'Add Daily Product'
        show_daily_modal = True

    context = {
        'saving_types': saving_types,
        'one_time_deposits': one_time_deposits,
        'daily_products': daily_products,

        'show_type_modal': show_type_modal,
        'type_form': type_form,
        'type_modal_action': type_modal_action,
        'type_modal_title': type_modal_title,
        'edit_type_id': edit_type_id,

        'show_one_time_modal': show_one_time_modal,
        'one_time_form': one_time_form,
        'one_time_modal_action': one_time_modal_action,
        'one_time_modal_title': one_time_modal_title,
        'edit_one_time_id': edit_one_time_id,

        'show_daily_modal': show_daily_modal,
        'daily_form': daily_form,
        'daily_modal_action': daily_modal_action,
        'daily_modal_title': daily_modal_title,
        'edit_daily_id': edit_daily_id,
    }
    return render(request, 'saving-manage/saving_management.html', context)

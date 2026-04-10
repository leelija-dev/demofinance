from django.shortcuts import render, redirect, get_object_or_404



from django.http import Http404

from django.http import JsonResponse

from django.urls import reverse

from django.conf import settings



from django.db import transaction

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import re



from django.utils import timezone

from zoneinfo import ZoneInfo

import asyncio
from playwright.async_api import async_playwright
import subprocess
import sys

import threading

from datetime import date

from datetime import datetime



from django.db.models import Q

from django.db.models import Sum

from django.db.models import Max

from django.db.models import Count



from django.core.paginator import Paginator

from django.template.loader import render_to_string

from django.http import HttpResponse

from django.db import close_old_connections



from django.views.generic import TemplateView

from django.views import View

from django.core.mail import send_mail

from django.views.decorators.csrf import csrf_exempt

from django.utils.decorators import method_decorator



from rest_framework.parsers import MultiPartParser, FormParser

from rest_framework.permissions import AllowAny

from rest_framework.response import Response

from rest_framework.views import APIView

from rest_framework import status



from agent.decorators import AgentSessionRequiredMixin

from agent.models import Agent



from branch.decorators import branch_permission_required

from branch.models import BranchEmployee, BranchTransaction, BranchAccount



from loan.models import CustomerAddress, CustomerDetail, CustomerDocument, DocumentRequest, DocumentReupload



from .models import SavingsAccountApplication, SavingType, OneTimeDeposit, DailyProduct, SavingsCollection, SavingsAgentAssign



def _generate_pdf_for_savings_application(html_content: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_generate_pdf_for_savings_application_async(html_content))
    finally:
        loop.close()


async def _generate_pdf_for_savings_application_async(html_content: str):
    browser = None
    try:
        async with async_playwright() as p:
            for attempt in (1, 2):
                try:
                    browser = await p.chromium.launch(headless=True)
                    break
                except Exception:
                    if attempt == 1:
                        cmd = [sys.executable, '-m', 'playwright', 'install', 'chromium']

                        def _run():
                            return subprocess.run(cmd, check=True, capture_output=True)

                        await asyncio.to_thread(_run)
                        continue
                    raise

            page = await browser.new_page()
            page.set_default_timeout(30000)
            await page.set_content(html_content, wait_until='domcontentloaded')
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
    finally:
        if browser:
            try:
                await browser.close()
            except Exception:
                pass


def _send_savings_application_email_in_background(application_id: str):
    close_old_connections()
    try:
        savings_app = (
            SavingsAccountApplication.objects
            .select_related('customer', 'agent', 'branch')
            .filter(application_id=application_id)
            .first()
        )
        if savings_app is None:
            return

        customer = savings_app.customer
        product_type = (savings_app.product_type or '').strip().lower()
        product_id = (savings_app.product_id or '').strip()

        recipient_list = []
        if getattr(customer, 'email', None):
            recipient_list.append(customer.email)
        if getattr(savings_app, 'agent', None) and getattr(savings_app.agent, 'email', None):
            recipient_list.append(savings_app.agent.email)
        if getattr(savings_app, 'branch', None) and getattr(savings_app.branch, 'email', None):
            recipient_list.append(savings_app.branch.email)
        hq_email = getattr(settings, 'HQ_NOTIFICATION_EMAIL', None)
        if hq_email:
            recipient_list.append(hq_email)

        recipient_list = [r for r in recipient_list if r]
        if not recipient_list:
            return

        from django.core.mail import EmailMultiAlternatives

        subject = f"New Savings Application Received - Ref: {savings_app.application_id}"
        message_text = (
            "SUNDARAM\n"
            "=========\n\n"
            "A new savings application has been submitted.\n\n"
            f"Application ID: {savings_app.application_id}\n"
            f"Customer Name: {customer.full_name}\n"
            f"Contact Number: {customer.contact}\n"
            f"Product Type: {product_type.upper()}\n"
            f"Product ID: {product_id}\n"
        )

        pdf_content = None
        try:
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
            except Exception:
                logo_base64 = None

            addr_obj = CustomerAddress.objects.filter(customer=customer).first()

            tenure_unit = None
            try:
                if product_type == 'fd' and product_id:
                    tenure_unit = OneTimeDeposit.objects.filter(one_time_deposit_id=product_id).values_list('tenure_unit', flat=True).first()
                elif product_type == 'rd' and product_id:
                    tenure_unit = DailyProduct.objects.filter(daily_product_id=product_id).values_list('tenure_unit', flat=True).first()
            except Exception:
                tenure_unit = None

            pdf_context = {
                'customer': customer,
                'savings_application': savings_app,
                'address': addr_obj,
                'tenure_unit': tenure_unit,
                'generated_date': timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).strftime('%B %d, %Y at %I:%M %p'),
                'logo_base64': logo_base64,
            }
            html_content = render_to_string('savings-application-pdf/savings-application-pdf.html', pdf_context)
            pdf_content = _generate_pdf_for_savings_application(html_content)
        except Exception:
            pdf_content = None

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com')
        for recipient in recipient_list:
            try:
                email = EmailMultiAlternatives(subject, message_text, from_email, [recipient])
                if pdf_content:
                    filename = f"savings_application_{savings_app.application_id}.pdf"
                    email.attach(filename, pdf_content, 'application/pdf')
                email.send(fail_silently=False)
            except Exception:
                pass
    finally:
        close_old_connections()



class SavingsApplicationPDFDownloadAPI(APIView):

    permission_classes = [AllowAny]

    def get(self, request, application_id: str, *args, **kwargs):

        savings_app = (
            SavingsAccountApplication.objects
            .select_related('customer', 'agent', 'branch')
            .filter(application_id=application_id)
            .first()
        )

        if savings_app is None:
            return HttpResponse('Savings application not found.', status=404)

        # Session-based authorization
        agent_id = request.session.get('agent_id')
        branch_employee_id = request.session.get('logged_user_id')

        if agent_id:
            if not savings_app.agent or savings_app.agent.agent_id != agent_id:
                return HttpResponse('Not permitted.', status=403)
        elif branch_employee_id:
            try:
                be = BranchEmployee.objects.select_related('branch').get(id=branch_employee_id, is_active=True)
            except BranchEmployee.DoesNotExist:
                return HttpResponse('Not permitted.', status=403)

            if not savings_app.branch or be.branch_id != savings_app.branch_id:
                return HttpResponse('Not permitted.', status=403)
        else:
            return HttpResponse('Authentication required.', status=403)

        customer = savings_app.customer
        product_type = (savings_app.product_type or '').strip().lower()
        product_id = (savings_app.product_id or '').strip()

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
        except Exception:
            logo_base64 = None

        addr_obj = CustomerAddress.objects.filter(customer=customer).first()

        tenure_unit = None
        try:
            if product_type == 'fd' and product_id:
                tenure_unit = OneTimeDeposit.objects.filter(one_time_deposit_id=product_id).values_list('tenure_unit', flat=True).first()
            elif product_type == 'rd' and product_id:
                tenure_unit = DailyProduct.objects.filter(daily_product_id=product_id).values_list('tenure_unit', flat=True).first()
        except Exception:
            tenure_unit = None

        pdf_context = {
            'customer': customer,
            'savings_application': savings_app,
            'address': addr_obj,
            'tenure_unit': tenure_unit,
            'generated_date': timezone.now().astimezone(ZoneInfo('Asia/Kolkata')).strftime('%B %d, %Y at %I:%M %p'),
            'logo_base64': logo_base64,
        }
        html_content = render_to_string('savings-application-pdf/savings-application-pdf.html', pdf_context)
        pdf_bytes = _generate_pdf_for_savings_application(html_content)

        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = f"savings_application_{savings_app.application_id}.pdf"
        resp['Content-Disposition'] = f'attachment; filename="{filename}"'
        return resp





def _apply_rd_daily_interest(account: SavingsAccountApplication, up_to_date: date) -> None:

    if account.product_type != 'rd':

        return



    if up_to_date is None:

        return



    last_date = account.rd_last_interest_date

    if last_date is None:

        last_date = (account.hq_approved_at or account.account_opened_at or timezone.now()).date()



    if up_to_date < last_date:

        raise ValueError('collection_date cannot be earlier than last interest date')



    days = (up_to_date - last_date).days

    if days <= 0:

        return



    rate = account.interest_rate

    if rate is None:

        return



    principal = Decimal(account.rd_principal_balance or 0)

    if principal <= 0:

        account.rd_last_interest_date = up_to_date



        return



    daily_rate = (Decimal(rate) / Decimal('100')) / Decimal('365')

    interest_add = (principal * daily_rate * Decimal(days)).quantize(Decimal('0.01'))

    account.rd_interest_accrued = (Decimal(account.rd_interest_accrued or 0) + interest_add).quantize(Decimal('0.01'))

    account.rd_last_interest_date = up_to_date





def _quantize_2(amount: Decimal) -> Decimal:

    return Decimal(amount or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)





def _quantize_0(amount: Decimal) -> Decimal:

    return Decimal(amount or 0).quantize(Decimal('1'), rounding=ROUND_HALF_UP)





def _get_rd_interest_as_of(account: SavingsAccountApplication, as_of_date: date):

    if account.product_type != 'rd':

        return None



    if as_of_date is None:

        as_of_date = timezone.now().date()



    principal = _quantize_2(Decimal(account.rd_principal_balance or 0))

    accrued = _quantize_2(Decimal(account.rd_interest_accrued or 0))



    rate = account.interest_rate

    last_date = account.rd_last_interest_date

    if last_date is None:

        last_date = (account.hq_approved_at or account.account_opened_at or timezone.now()).date()



    pending = Decimal('0')

    if rate is not None and principal > 0 and as_of_date >= last_date:

        days = (as_of_date - last_date).days

        if days > 0:

            daily_rate = (Decimal(rate) / Decimal('100')) / Decimal('365')

            pending = _quantize_2(principal * daily_rate * Decimal(days))



    total_interest = _quantize_2(accrued + pending)

    payable = _quantize_2(principal + total_interest)



    return {

        'principal': principal,

        'interest_accrued': accrued,

        'interest_pending': pending,

        'interest_total': total_interest,

        'payable': payable,

        'as_of_date': as_of_date,

    }





def _build_rd_daily_statement(*, tenure: int, daily_deposit: Decimal, rate: Decimal, deposits_by_no: dict[int, Decimal]):

    tenure = int(tenure or 0)

    if tenure <= 0:

        return []



    if daily_deposit is None:

        daily_deposit = Decimal('0')

    if rate is None:

        rate = Decimal('0')



    daily_rate = (Decimal(rate) / Decimal('100')) / Decimal('365')



    cum = Decimal('0')

    cu_int = Decimal('0')

    rows = []



    for i in range(1, tenure + 1):

        deposit = Decimal(deposits_by_no.get(i, daily_deposit) or 0)

        cum += deposit

        cum = _quantize_2(cum)



        interest = _quantize_2(cum * daily_rate)

        cu_int = _quantize_2(cu_int + interest)

        payable = _quantize_0(cum + cu_int)



        rows.append({

            'no': i,

            'deposit': deposit,

            'cum': cum,

            'interest': interest,

            'cu_int': cu_int,

            'payable': payable,

        })



    return rows





class NewSavingsApplication(AgentSessionRequiredMixin, TemplateView):

    template_name = 'savings/new-application.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context['base_template'] = 'agent/base.html'

        context['dashboard_url_name'] = 'agent:dashboard'

        return context



@method_decorator(branch_permission_required(), name='dispatch')
class BranchSavingsWithdrawCloseListView(TemplateView):

    template_name = 'savings/withdraw_close.html'

    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('savings/partials/withdraw_close_rows.html', context, request=request)
            return HttpResponse(html)

        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')
        if not logged_user_id:
            raise Http404

        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)
        except BranchEmployee.DoesNotExist:
            raise Http404

        branch = branch_employee.branch

        accounts = (
            SavingsAccountApplication.objects
            .filter(account_id__isnull=False, status='hq_approved', surrender_status='approved')
            .filter(Q(branch=branch) | Q(branch__isnull=True, agent__branch=branch))
            .select_related('customer', 'agent', 'branch')
        )

        product_type = (self.request.GET.get('product_type') or '').strip()
        if product_type:
            accounts = accounts.filter(product_type=product_type)

        agent_id = (self.request.GET.get('agent_id') or '').strip()
        if agent_id:
            accounts = accounts.filter(agent__agent_id=agent_id)

        q = (self.request.GET.get('q') or '').strip()
        if q:
            accounts = accounts.filter(
                Q(account_id__icontains=q)
                | Q(application_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__customer_id__icontains=q)
            )

        accounts = accounts.order_by('-last_update', '-hq_approved_at', '-submitted_at')

        page_number_raw = (self.request.GET.get('page') or '1').strip()
        try:
            page_number = int(page_number_raw)
        except ValueError:
            page_number = 1
        if page_number < 1:
            page_number = 1

        paginator = Paginator(accounts, 15)
        page_obj = paginator.get_page(page_number)

        today = timezone.now().date()
        for acc in page_obj.object_list:
            tenure_completed = False
            if acc.maturity_date:
                tenure_completed = acc.maturity_date <= today

            payable_principal = Decimal('0.00')
            payable_interest = Decimal('0.00')
            payable_total = Decimal('0.00')

            if (acc.product_type or '').strip().lower() == 'rd':
                rd_summary = _get_rd_interest_as_of(acc, today)
                if rd_summary:
                    payable_principal = Decimal(rd_summary.get('principal') or 0)
                    payable_interest = Decimal(rd_summary.get('interest_total') or 0)
                    payable_total = Decimal(rd_summary.get('payable') or 0)
            elif (acc.product_type or '').strip().lower() == 'fd':
                fd_principal = (
                    SavingsCollection.objects
                    .filter(account=acc, collection_type='fd_deposit', is_collected=True)
                    .aggregate(total=Sum('amount'))
                    .get('total')
                    or Decimal('0')
                )
                payable_principal = Decimal(fd_principal or 0)
                if tenure_completed and acc.maturity_amount is not None:
                    payable_total = Decimal(acc.maturity_amount or 0)
                    payable_interest = (payable_total - payable_principal)
                else:
                    payable_total = payable_principal
                    payable_interest = Decimal('0.00')

            if not tenure_completed:
                payable_total = payable_principal

            try:
                payable_principal = Decimal(payable_principal).quantize(Decimal('0.01'))
            except Exception:
                payable_principal = Decimal('0.00')
            try:
                payable_interest = Decimal(payable_interest).quantize(Decimal('0.01'))
            except Exception:
                payable_interest = Decimal('0.00')
            try:
                payable_total = Decimal(payable_total).quantize(Decimal('0.01'))
            except Exception:
                payable_total = Decimal('0.00')

            acc.payable_principal = payable_principal
            acc.payable_interest = payable_interest
            acc.payable_total = payable_total

            acc.tenure_completed = tenure_completed

        has_cash_account = BranchAccount.objects.filter(branch=branch, type='CASH').exists()
        has_bank_account = BranchAccount.objects.filter(branch=branch, type='BANK').exists()

        all_payment_modes = list(getattr(SavingsCollection, 'PAYMENT_MODES', []))
        if has_cash_account and has_bank_account:
            payment_modes = all_payment_modes
        elif has_cash_account:
            payment_modes = [pm for pm in all_payment_modes if pm and pm[0] == 'cash']
        elif has_bank_account:
            payment_modes = [pm for pm in all_payment_modes if pm and pm[0] != 'cash']
        else:
            payment_modes = all_payment_modes

        agents = (
            Agent.objects
            .filter(branch=branch, status='active')
            .only('agent_id', 'full_name')
            .order_by('full_name')
        )

        context['accounts'] = page_obj.object_list
        context['page_obj'] = page_obj
        context['paginator'] = paginator
        context['agents'] = agents
        context['payment_modes'] = payment_modes
        context['filter_product_type'] = product_type
        context['filter_agent_id'] = agent_id
        context['filter_q'] = q
        return context



class AgentSavingsCloseRequestAPI(AgentSessionRequiredMixin, APIView):

    def post(self, request, *args, **kwargs):

        agent_id = request.session.get('agent_id')

        if not agent_id:

            return Response({'success': False, 'detail': 'Authentication required.', 'message': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)



        try:

            agent = Agent.objects.get(agent_id=agent_id, status='active')

        except Agent.DoesNotExist:

            return Response({'success': False, 'detail': 'Agent not found.', 'message': 'Agent not found.'}, status=status.HTTP_404_NOT_FOUND)



        application_id = (request.data.get('application_id') or '').strip()

        note = (request.data.get('note') or '').strip()

        if not application_id:

            return Response({'success': False, 'detail': 'Missing application_id.', 'message': 'Missing application_id.'}, status=status.HTTP_400_BAD_REQUEST)



        with transaction.atomic():

            account = (

                SavingsAccountApplication.objects

                .select_for_update()

                .filter(application_id=application_id, account_id__isnull=False, status='hq_approved')

                .first()

            )

            if not account:

                return Response({'success': False, 'detail': 'Account not found.', 'message': 'Account not found.'}, status=status.HTTP_404_NOT_FOUND)



            is_assigned = (

                SavingsAgentAssign.objects

                .filter(account=account, agent=agent, is_active=True)

                .exists()

            ) or (account.agent_id == agent.agent_id)

            if not is_assigned:

                return Response({'success': False, 'detail': 'Not allowed.', 'message': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)



            current_status = (account.surrender_status or 'none').strip()

            if current_status and current_status != 'none':

                return Response(

                    {

                        'success': False,

                        'detail': 'Close request already created.',

                        'message': 'Close request already created.',

                        'surrender_status': current_status,

                        'surrender_status_display': account.get_surrender_status_display(),

                    },

                    status=status.HTTP_409_CONFLICT,

                )



            account.surrender_status = 'requested'

            if note:

                account.surrender_note = note

            account.save(update_fields=['surrender_status', 'surrender_note', 'last_update'])



        branch_email = ((account.branch.email if account.branch_id else None) or '').strip()

        if branch_email:

            subject = f"Savings Close Request - {account.account_id or account.application_id}"

            body = "\n".join(

                [

                    f"Application ID: {account.application_id}",

                    f"Account ID: {account.account_id or ''}",

                    f"Customer: {getattr(account.customer, 'full_name', '')} ({getattr(account.customer, 'customer_id', '')})",

                    f"Product: {account.get_product_type_display() if hasattr(account, 'get_product_type_display') else (account.product_type or '')}",

                    "",

                    "Request:",

                    note or "-",

                ]

            )

            try:

                send_mail(subject, body, getattr(settings, 'DEFAULT_FROM_EMAIL', None), [branch_email], fail_silently=True)

            except Exception:

                pass



        return Response(

            {

                'success': True,

                'detail': 'Close request submitted.',

                'message': 'Close request submitted.',

                'application_id': account.application_id,

                'surrender_status': account.surrender_status,

                'surrender_status_display': account.get_surrender_status_display(),

            },

            status=status.HTTP_200_OK,

        )





class PendingSavingsApplications(AgentSessionRequiredMixin, TemplateView):

    template_name = 'savings/pending-applications.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        agent = None

        if agent_id:

            try:

                agent = Agent.objects.get(agent_id=agent_id)

            except Agent.DoesNotExist:

                None



        qs = SavingsAccountApplication.objects.filter(status='pending').filter(
            Q(surrender_status__isnull=True) | Q(surrender_status__in=['', 'none'])
        )

        if agent is not None:

            qs = qs.filter(agent=agent)



        qs = qs.select_related('customer', 'agent', 'branch').order_by('-submitted_at')

        paginator = Paginator(qs, 25)

        page_number = self.request.GET.get('page')

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

        context['filter_agent_id'] = agent_id

        context['filter_q'] = q

        context['agents'] = (
            Agent.objects
            .filter(branch=branch, status='active')
            .only('agent_id', 'full_name')
            .order_by('full_name')
        )

        return context





class AgentMySavingsApplicationsView(AgentSessionRequiredMixin, TemplateView):

    template_name = 'agent/agent-savings-applications.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').select_related('branch').first()

        if agent is None:

            raise Http404



        branch = agent.branch



        qs = (

            SavingsAccountApplication.objects

            .filter(agent=agent)

            .select_related('customer', 'agent', 'branch')

            .order_by('-submitted_at')

        )



        paginator = Paginator(qs, 25)

        page_number = self.request.GET.get('page')

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





class AgentSavingsApplicationDetailView(AgentSessionRequiredMixin, TemplateView):

    template_name = 'agent/agent-application-detail.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').select_related('branch').first()

        if agent is None:

            raise Http404



        application_id = kwargs.get('application_id')

        app = (

            SavingsAccountApplication.objects

            .filter(application_id=application_id, agent=agent)

            .select_related('customer', 'agent', 'branch', 'customer__address')

            .first()

        )

        if not app:

            raise Http404



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



        pending_requested_doc_types = list(

            DocumentRequest.objects.filter(

                savings_application=app,

                is_resolved=False,

            ).values_list('document_type', flat=True)

        )



        pending_review_requests = []

        pending_upload_requests = []



        field_map = {

            'id_proof': 'id_proof',

            'id_proof_back': 'id_proof_back',

            'income_proof': 'income_proof',

            'photo': 'photo',

            'signature': 'signature',

            'collateral': 'collateral',

            'residential_proof': 'residential_proof_file',

            'residential_proof_file': 'residential_proof_file',

        }



        doc_requests_qs = (

            DocumentRequest.objects

            .filter(savings_application=app, is_resolved=False)

            .order_by('-requested_at')

        )



        for req in doc_requests_qs:

            latest_reupload = (

                DocumentReupload.objects

                .filter(document_request=req)

                .order_by('-uploaded_at')

                .first()

            )

            file_url = None

            uploaded_at = None

            if latest_reupload and getattr(latest_reupload, 'uploaded_file', None):

                try:

                    file_url = latest_reupload.uploaded_file.url

                except Exception:

                    file_url = None

                uploaded_at = getattr(latest_reupload, 'uploaded_at', None)



            item = {

                'id': req.id,

                'document_type': req.document_type,

                'document_label': req.get_document_type_display() or req.document_type,

                'requested_at': req.requested_at,

                'file_url': file_url,

                'uploaded_at': uploaded_at,

            }

            if file_url:

                pending_review_requests.append(item)

            else:

                pending_upload_requests.append(item)



        pending_review_requests = []

        pending_upload_requests = []



        field_map = {

            'id_proof': 'id_proof',

            'id_proof_back': 'id_proof_back',

            'income_proof': 'income_proof',

            'photo': 'photo',

            'signature': 'signature',

            'collateral': 'collateral',

            'residential_proof': 'residential_proof_file',

            'residential_proof_file': 'residential_proof_file',

        }



        doc_requests_qs = (

            DocumentRequest.objects

            .filter(savings_application=app, is_resolved=False)

            .order_by('-requested_at')

        )



        for req in doc_requests_qs:

            latest_reupload = (

                DocumentReupload.objects

                .filter(document_request=req)

                .order_by('-uploaded_at')

                .first()

            )



            file_url = None

            if latest_reupload and getattr(latest_reupload, 'uploaded_file', None):

                try:

                    file_url = latest_reupload.uploaded_file.url

                except Exception:

                    file_url = None



            item = {

                'id': req.id,

                'document_type': req.document_type,

                'document_label': req.get_document_type_display() or req.document_type,

                'requested_at': req.requested_at,

                'file_url': file_url,

            }

            if file_url:

                pending_review_requests.append(item)

            else:

                pending_upload_requests.append(item)



        pending_review_requests = []

        pending_upload_requests = []



        field_map = {

            'id_proof': 'id_proof',

            'id_proof_back': 'id_proof_back',

            'income_proof': 'income_proof',

            'photo': 'photo',

            'signature': 'signature',

            'collateral': 'collateral',

            'residential_proof': 'residential_proof_file',

            'residential_proof_file': 'residential_proof_file',

        }



        doc_requests_qs = (

            DocumentRequest.objects

            .filter(savings_application=app, is_resolved=False)

            .order_by('-requested_at')

        )



        for req in doc_requests_qs:

            latest_reupload = (

                DocumentReupload.objects

                .filter(document_request=req)

                .order_by('-uploaded_at')

                .first()

            )



            file_url = None

            if latest_reupload and getattr(latest_reupload, 'uploaded_file', None):

                try:

                    file_url = latest_reupload.uploaded_file.url

                except Exception:

                    file_url = None



            item = {

                'id': req.id,

                'document_type': req.document_type,

                'document_label': req.get_document_type_display() or req.document_type,

                'requested_at': req.requested_at,

                'file_url': file_url,

            }

            if file_url:

                pending_review_requests.append(item)

            else:

                pending_upload_requests.append(item)



        context['application'] = app

        context['documents'] = documents

        context['pending_requested_doc_types'] = pending_requested_doc_types

        context['pending_review_requests'] = pending_review_requests

        context['pending_upload_requests'] = pending_upload_requests

        return context





@method_decorator(branch_permission_required(), name='dispatch')

class BranchReviewSavingsDocumentRequestView(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch

        document_request_id = kwargs.get('document_request_id')



        try:

            doc_request = (

                DocumentRequest.objects

                .select_related('savings_application')

                .get(id=document_request_id, savings_application__isnull=False, is_resolved=False)

            )

        except DocumentRequest.DoesNotExist:

            raise Http404



        savings_app = doc_request.savings_application

        if not savings_app:

            raise Http404



        allowed = SavingsAccountApplication.objects.filter(

            application_id=savings_app.application_id,

        ).filter(

            Q(branch=branch) | Q(branch__isnull=True, agent__branch=branch)

        ).exists()

        if not allowed:

            raise Http404



        latest_reupload = (

            DocumentReupload.objects

            .filter(document_request=doc_request)

            .order_by('-uploaded_at')

            .first()

        )

        if not latest_reupload:

            return redirect('branch:savings_application_detail', application_id=savings_app.application_id)



        doc_request.mark_as_resolved()



        has_pending = DocumentRequest.objects.filter(

            savings_application=savings_app,

            is_resolved=False,

        ).exists()

        if not has_pending and savings_app.status == 'resubmitted':

            savings_app.status = 'branch_document_accepted'

            savings_app.save(update_fields=['status', 'last_update'])



        return redirect('branch:savings_application_detail', application_id=savings_app.application_id)





class AgentSavingsDocumentRequestsView(AgentSessionRequiredMixin, TemplateView):

    template_name = 'agent/agent-document-requests.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').select_related('branch').first()

        if agent is None:

            raise Http404



        reuploaded_request_ids = (

            DocumentReupload.objects

            .filter(document_request__savings_application__agent=agent)

            .values_list('document_request_id', flat=True)

        )



        context['document_requests'] = (

            DocumentRequest.objects

            .filter(savings_application__agent=agent, savings_application__isnull=False, is_resolved=False)

            .exclude(id__in=reuploaded_request_ids)

            .select_related('savings_application', 'savings_application__customer')

            .order_by('-requested_at')

        )

        context['agent'] = agent

        return context





class AgentSavingsDocumentUploadAPI(AgentSessionRequiredMixin, APIView):

    parser_classes = [MultiPartParser, FormParser]



    def post(self, request, *args, **kwargs):

        agent_id = request.session.get('agent_id')

        if not agent_id:

            return Response({'success': False, 'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)



        agent = Agent.objects.filter(agent_id=agent_id, status='active').select_related('branch').first()

        if agent is None:

            return Response({'success': False, 'detail': 'Agent not found.'}, status=status.HTTP_404_NOT_FOUND)



        document_request_id = request.data.get('document_request_id')

        document_type = request.data.get('document_type')

        uploaded_file = request.FILES.get('uploaded_file')



        if not document_request_id or not document_type or not uploaded_file:

            return Response({'success': False, 'detail': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)



        try:

            doc_request = (

                DocumentRequest.objects

                .select_related('savings_application', 'savings_application__customer')

                .get(id=document_request_id, savings_application__agent=agent, savings_application__isnull=False)

            )

        except DocumentRequest.DoesNotExist:

            return Response({'success': False, 'detail': 'Document request not found.'}, status=status.HTTP_404_NOT_FOUND)



        savings_app = doc_request.savings_application

        if not savings_app:

            return Response({'success': False, 'detail': 'Savings application not found for this request.'}, status=status.HTTP_400_BAD_REQUEST)



        field_map = {

            'id_proof': 'id_proof',

            'pan_card_document': 'pan_card_document',

            'id_proof_back': 'id_proof_back',

            'income_proof': 'income_proof',

            'photo': 'photo',

            'signature': 'signature',

            'collateral': 'collateral',

            'residential_proof': 'residential_proof_file',

            'residential_proof_file': 'residential_proof_file',

        }

        field_name = field_map.get(document_type)

        if not field_name:

            return Response({'success': False, 'detail': 'Unsupported document type.'}, status=status.HTTP_400_BAD_REQUEST)



        customer_document, _created = CustomerDocument.objects.get_or_create(

            savings_application=savings_app,

            defaults={

                'loan_application': None,

                'branch': getattr(savings_app, 'branch', None),

                'agent': agent,

            },

        )



        setattr(customer_document, field_name, uploaded_file)

        customer_document.agent = agent

        if getattr(savings_app, 'branch', None):

            customer_document.branch = savings_app.branch

        customer_document.save()



        DocumentReupload.objects.create(

            document_request=doc_request,

            loan_application=None,

            document_type=document_type,

            uploaded_file=uploaded_file,

            uploaded_by=agent,

        )



        if savings_app.status == 'document_requested':

            savings_app.status = 'resubmitted'

            savings_app.save(update_fields=['status', 'last_update'])

        elif savings_app.status in ['document_requested_by_hq', 'hq_resubmitted']:

            doc_request.mark_as_resolved()

            savings_app.status = 'branch_resubmitted'

            savings_app.save(update_fields=['status', 'last_update'])

        else:

            doc_request.mark_as_resolved()



        return Response({'success': True})





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsDocumentRequestAPI(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=403)



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            return JsonResponse({'success': False, 'error': 'Branch employee not found.'}, status=404)



        import json



        try:

            data = json.loads((request.body or b'{}').decode('utf-8'))

        except Exception:

            return JsonResponse({'success': False, 'error': 'Invalid request body.'}, status=400)



        application_id = (data.get('application_id') or '').strip()

        document_type = (data.get('document_type') or '').strip()

        reason = (data.get('reason') or '').strip()

        comment = (data.get('comment') or '').strip()



        if not (application_id and document_type and reason):

            return JsonResponse({'success': False, 'error': 'Missing required fields.'}, status=400)



        branch = branch_employee.branch



        savings_app = (

            SavingsAccountApplication.objects

            .filter(application_id=application_id, agent__branch=branch)

            .first()

        )

        if not savings_app:

            return JsonResponse({'success': False, 'error': 'Savings application not found.'}, status=404)



        DocumentRequest.objects.create(

            savings_application=savings_app,

            document_type=document_type,

            reason=reason,

            comment=comment,

            requested_by=branch_employee,

            requested_by_hq=None,

            branch=branch,

        )

        savings_app.status = 'document_requested'

        savings_app.save(update_fields=['status', 'last_update'])



        return JsonResponse({'success': True, 'new_status': 'document_requested'})





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsDocumentReviewAPI(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            return JsonResponse({'success': False, 'detail': 'Authentication required.'}, status=403)



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            return JsonResponse({'success': False, 'detail': 'Branch employee not found.'}, status=404)



        import json



        try:

            data = json.loads((request.body or b'{}').decode('utf-8'))

        except Exception:

            return JsonResponse({'success': False, 'detail': 'Invalid request body.'}, status=400)



        document_request_id = data.get('document_request_id')

        decision = (data.get('decision') or '').strip()

        review_comment = (data.get('review_comment') or '').strip()



        if not document_request_id or not decision:

            return JsonResponse({'success': False, 'detail': 'Missing required fields.'}, status=400)



        branch = branch_employee.branch



        try:

            doc_request = (

                DocumentRequest.objects

                .select_related('savings_application')

                .get(id=int(document_request_id), savings_application__isnull=False, is_resolved=False)

            )

        except Exception:

            return JsonResponse({'success': False, 'detail': 'Document request not found.'}, status=404)



        savings_app = doc_request.savings_application

        if not savings_app:

            return JsonResponse({'success': False, 'detail': 'Savings application not found.'}, status=404)



        allowed = SavingsAccountApplication.objects.filter(

            application_id=savings_app.application_id,

        ).filter(

            Q(branch=branch) | Q(branch__isnull=True, agent__branch=branch)

        ).exists()

        if not allowed:

            return JsonResponse({'success': False, 'detail': 'Not allowed.'}, status=403)



        latest_reupload = (

            DocumentReupload.objects

            .filter(document_request=doc_request)

            .order_by('-uploaded_at')

            .first()

        )

        if not latest_reupload:

            return JsonResponse({'success': False, 'detail': 'No re-upload found for this request yet.'}, status=400)



        if decision == 'approved':

            doc_request.mark_as_resolved()



            has_pending = DocumentRequest.objects.filter(

                savings_application=savings_app,

                is_resolved=False,

            ).exists()

            if not has_pending and savings_app.status == 'resubmitted':

                savings_app.status = 'branch_document_accepted'

                savings_app.save(update_fields=['status', 'last_update'])



            return JsonResponse({'success': True})



        if decision == 'request_again':

            DocumentReupload.objects.filter(document_request=doc_request).delete()

            if review_comment:

                doc_request.comment = review_comment

            doc_request.requested_at = timezone.now()

            doc_request.save(update_fields=['comment', 'requested_at'])

            savings_app.status = 'document_requested'

            savings_app.save(update_fields=['status', 'last_update'])

            return JsonResponse({'success': True})



        return JsonResponse({'success': False, 'detail': 'Invalid decision.'}, status=400)





class AgentSavingsCollectionsAccountsListView(AgentSessionRequiredMixin, TemplateView):

    template_name = 'agent/agent-collections-accounts.html'




    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('agent/partials/collections-accounts-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').select_related('branch').first()

        if agent is None:

            raise Http404



        branch = agent.branch



        accounts = (

            SavingsAccountApplication.objects

            .filter(

                Q(agent_assignments__agent=agent, agent_assignments__is_active=True) |

                Q(agent=agent),

                account_id__isnull=False,

                status='hq_approved',

                product_type__in=['rd', 'fd'],

            )

            .select_related('customer', 'agent', 'branch')

            .distinct()

            .order_by('-hq_approved_at', '-submitted_at')

        )



        agent_id = (self.request.GET.get('agent_id') or '').strip()
        if agent_id:
            accounts = accounts.filter(agent__agent_id=agent_id)



        q = (self.request.GET.get('q') or '').strip()
        if q:
            accounts = accounts.filter(
                Q(account_id__icontains=q)
                | Q(application_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__customer_id__icontains=q)
            )



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(accounts, 20)

        page_obj = paginator.get_page(page_number)



        today = timezone.now().date()
        page_accounts = list(page_obj.object_list)
        rd_accounts = [a for a in page_accounts if (a.product_type or '').strip().lower() == 'rd']
        rd_last_due_by_app_id = {}
        rd_counts_by_app_id = {}
        if rd_accounts:
            rd_last_due_by_app_id = {
                row['account__application_id']: row['last_due']
                for row in (
                    SavingsCollection.objects
                    .filter(account__in=rd_accounts, collection_type='rd_installment', is_expected=True)
                    .values('account__application_id')
                    .annotate(last_due=Max('collection_date'))
                )
                if row.get('account__application_id')
            }

            rd_counts_by_app_id = {
                row['account__application_id']: {
                    'expected_count': int(row.get('expected_count') or 0),
                    'collected_count': int(row.get('collected_count') or 0),
                }
                for row in (
                    SavingsCollection.objects
                    .filter(account__in=rd_accounts, collection_type='rd_installment', is_expected=True)
                    .values('account__application_id')
                    .annotate(
                        expected_count=Count('id'),
                        collected_count=Count('id', filter=Q(is_collected=True)),
                    )
                )
                if row.get('account__application_id')
            }

        for a in page_accounts:
            tenure_completed = False
            product_type = (a.product_type or '').strip().lower()
            if product_type == 'fd':
                if a.maturity_date:
                    tenure_completed = a.maturity_date <= today
            elif product_type == 'rd':
                last_due = rd_last_due_by_app_id.get(a.application_id)
                if last_due:
                    tenure_completed = last_due <= today
            a.tenure_completed = tenure_completed

            close_request_ready = False
            if product_type == 'fd':
                close_request_ready = bool(tenure_completed)
            elif product_type == 'rd':
                counts = rd_counts_by_app_id.get(a.application_id) or {}
                expected_count = int(counts.get('expected_count') or 0)
                collected_count = int(counts.get('collected_count') or 0)
                all_collected = expected_count > 0 and collected_count >= expected_count
                close_request_ready = bool(tenure_completed and all_collected)
            a.close_request_ready = close_request_ready



        context['accounts'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['filter_agent_id'] = agent_id

        context['filter_q'] = q

        context['agents'] = (
            Agent.objects
            .filter(branch=branch, status='active')
            .only('agent_id', 'full_name')
            .order_by('full_name')
        )

        return context





class AgentSavingsCollectionsListView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'agent/agent-collections-list.html'


    def get(self, request, *args, **kwargs):
        if (request.GET.get('partial') or '').strip() == '1':
            context = self.get_context_data(**kwargs)
            html = render_to_string('agent/partials/pending-collections-rows.html', context, request=request)
            return HttpResponse(html)
        return super().get(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').first()

        if agent is None:

            raise Http404



        application_id = kwargs.get('application_id')

        account = (

            SavingsAccountApplication.objects

            .filter(application_id=application_id, account_id__isnull=False, status='hq_approved')

            .select_related('customer', 'agent', 'branch')

            .first()

        )

        if not account:

            raise Http404



        account.ensure_expected_collections_schedule()



        is_assigned = (

            SavingsAgentAssign.objects

            .filter(account=account, agent=agent, is_active=True)

            .exists()

        ) or (account.agent_id == agent.agent_id)



        if not is_assigned:

            raise Http404



        collections_qs = SavingsCollection.objects.filter(account=account).select_related(

            'collected_by_branch_employee',

            'collected_by_agent',

            'branch',

            'agent',

        ).order_by('-is_expected', 'installment_no', 'collection_date', 'created_at')



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(collections_qs, 20)

        page_obj = paginator.get_page(page_number)



        total_amount = (

            collections_qs

            .filter(is_collected=True)

            .aggregate(total=Sum('amount'))

            .get('total')

            or Decimal('0')

        )



        rd_standard_rows = []

        rd_actual_rows = []

        rd_summary = None

        if account.product_type == 'rd':

            rd_summary = _get_rd_interest_as_of(account, timezone.now().date())

            daily_deposit = account.installment_amount

            if daily_deposit is None and account.product_id:

                daily_deposit = (

                    DailyProduct.objects

                    .filter(daily_product_id=account.product_id)

                    .values_list('deposit_amount', flat=True)

                    .first()

                )



            expected_installments = list(

                SavingsCollection.objects

                .filter(account=account, collection_type='rd_installment', is_expected=True)

                .only('installment_no', 'amount', 'is_collected')

                .order_by('installment_no')

            )

            actual_map = {}

            for r in expected_installments:

                if not r.installment_no:

                    continue

                actual_map[int(r.installment_no)] = (Decimal(r.amount or 0) if r.is_collected else Decimal('0'))



            if daily_deposit is not None and account.interest_rate is not None:

                rd_standard_rows = _build_rd_daily_statement(

                    tenure=account.tenure,

                    daily_deposit=Decimal(daily_deposit),

                    rate=Decimal(account.interest_rate),

                    deposits_by_no={},

                )

                rd_actual_rows = _build_rd_daily_statement(

                    tenure=account.tenure,

                    daily_deposit=Decimal('0'),

                    rate=Decimal(account.interest_rate),

                    deposits_by_no=actual_map,

                )



        context['agent'] = agent

        context['account'] = account

        context['collections'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['total_amount'] = total_amount

        context['rd_standard_rows'] = rd_standard_rows

        context['rd_actual_rows'] = rd_actual_rows

        context['rd_summary'] = rd_summary

        context['today'] = timezone.now().date()

        return context





class AgentSavingsCollectedInstallmentsView(AgentSessionRequiredMixin, TemplateView):

    template_name = 'agent/collected-installment.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('agent/partials/collected-installments-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').first()

        if agent is None:

            raise Http404



        collections_qs = (

            SavingsCollection.objects

            .filter(

                is_collected=True,

                collected_by_agent=agent,

                account__account_id__isnull=False,

                account__status='hq_approved',

                account__product_type='rd',

            )

            .select_related(

                'account',

                'account__customer',

                'collected_by_branch_employee',

                'collected_by_agent',

                'branch',

                'agent',

            )

            .order_by('-collection_date', '-created_at')

        )



        selected_date_raw = (self.request.GET.get('date') or '').strip()

        selected_date = None

        if selected_date_raw:

            try:

                selected_date = datetime.strptime(selected_date_raw, '%Y-%m-%d').date()

            except ValueError:

                selected_date = None

        if selected_date:

            collections_qs = collections_qs.filter(collection_date=selected_date)



        q = (self.request.GET.get('q') or '').strip()

        if q:

            collections_qs = collections_qs.filter(

                Q(account__account_id__icontains=q)

                | Q(account__application_id__icontains=q)

                | Q(account__customer__full_name__icontains=q)

                | Q(collection_id__icontains=q)

            )



        total_amount = (

            collections_qs

            .aggregate(total=Sum('amount'))

            .get('total')

            or Decimal('0')

        )



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(collections_qs, 15)

        page_obj = paginator.get_page(page_number)



        context['collections'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['total_amount'] = total_amount

        context['agent'] = agent

        context['today'] = timezone.now().date()

        context['q'] = q

        context['selected_date'] = selected_date_raw

        return context





class AgentSavingsPendingCollectionsListView(AgentSessionRequiredMixin, TemplateView):

    template_name = 'agent/agent-collections-list.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('agent/partials/pending-collections-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').first()

        if agent is None:

            raise Http404



        today = timezone.now().date()



        selected_date_raw = (self.request.GET.get('date') or '').strip()

        selected_date = None

        if selected_date_raw:

            try:

                selected_date = datetime.strptime(selected_date_raw, '%Y-%m-%d').date()

            except ValueError:

                selected_date = None



        filter_date = selected_date or today



        collections_qs = (

            SavingsCollection.objects

            .filter(

                agent=agent,

                is_expected=True,

                is_collected=False,

                collection_date=filter_date,

                account__account_id__isnull=False,

                account__status='hq_approved',

            )

            .filter(
                Q(account__surrender_status__isnull=True) | Q(account__surrender_status__in=['', 'none'])
            )

            .select_related(

                'account',

                'account__customer',

                'collected_by_branch_employee',

                'collected_by_agent',

                'branch',

                'agent',

            )

            .order_by('collection_date', 'installment_no', 'created_at')

        )



        selected_date_raw = (self.request.GET.get('date') or '').strip()

        selected_date = None

        if selected_date_raw:

            try:

                selected_date = datetime.strptime(selected_date_raw, '%Y-%m-%d').date()

            except ValueError:

                selected_date = None

        if selected_date:

            collections_qs = collections_qs.filter(collection_date=selected_date)



        q = (self.request.GET.get('q') or '').strip()

        if q:

            collections_qs = collections_qs.filter(

                Q(account__account_id__icontains=q)

                | Q(account__application_id__icontains=q)

                | Q(account__customer__full_name__icontains=q)

                | Q(collection_id__icontains=q)

            )



        total_amount = (

            collections_qs

            .aggregate(total=Sum('amount'))

            .get('total')

            or Decimal('0')

        )



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(collections_qs, 15)

        page_obj = paginator.get_page(page_number)



        context['collections'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['total_amount'] = total_amount

        context['agent'] = agent

        context['is_global_pending'] = True

        context['today'] = today

        context['q'] = q

        context['selected_date'] = selected_date_raw

        return context





class AgentSavingsAssignedCollectionsListView(AgentSessionRequiredMixin, TemplateView):

    template_name = 'agent/agent-assigned-collections.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('agent/partials/assigned-collections-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        agent_id = self.request.session.get('agent_id')

        if not agent_id:

            raise Http404



        agent = Agent.objects.filter(agent_id=agent_id, status='active').first()

        if agent is None:

            raise Http404



        collections_qs = (

            SavingsCollection.objects

            .filter(

                agent=agent,

                is_expected=True,

                account__account_id__isnull=False,

                account__status='hq_approved',

            )

            .filter(
                Q(account__surrender_status__isnull=True) | Q(account__surrender_status__in=['', 'none'])
            )

            .select_related(

                'account',

                'account__customer',

                'collected_by_branch_employee',

                'collected_by_agent',

                'branch',

                'agent',

            )

            .order_by('collection_date', 'installment_no', 'created_at')

        )



        selected_date_raw = (self.request.GET.get('date') or '').strip()

        selected_date = None

        if selected_date_raw:

            try:

                selected_date = datetime.strptime(selected_date_raw, '%Y-%m-%d').date()

            except ValueError:

                selected_date = None

        if selected_date:

            collections_qs = collections_qs.filter(collection_date=selected_date)



        q = (self.request.GET.get('q') or '').strip()

        if q:

            collections_qs = collections_qs.filter(

                Q(account__account_id__icontains=q)

                | Q(account__application_id__icontains=q)

                | Q(account__customer__full_name__icontains=q)

                | Q(collection_id__icontains=q)

            )



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(collections_qs, 15)

        page_obj = paginator.get_page(page_number)



        total_amount = (

            collections_qs

            .filter(is_collected=True)

            .aggregate(total=Sum('amount'))

            .get('total')

            or Decimal('0')

        )



        context['collections'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['total_amount'] = total_amount

        context['agent'] = agent

        context['is_global_assigned'] = True

        context['today'] = timezone.now().date()

        context['q'] = q

        context['selected_date'] = selected_date_raw

        return context





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsApplicationDetail(TemplateView):

    template_name = 'savings/application-detail.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch

        application_id = kwargs.get('application_id')



        app = (

            SavingsAccountApplication.objects

            .filter(application_id=application_id)

            .filter(Q(branch=branch) | Q(agent__branch=branch))

            .select_related('customer', 'agent', 'branch', 'customer__address')

            .first()

        )

        if not app:

            raise Http404



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



        pending_requested_doc_types = list(

            DocumentRequest.objects.filter(

                savings_application=app,

                is_resolved=False,

            ).values_list('document_type', flat=True)

        )



        pending_review_requests = []

        pending_upload_requests = []



        field_map = {

            'id_proof': 'id_proof',

            'id_proof_back': 'id_proof_back',

            'income_proof': 'income_proof',

            'photo': 'photo',

            'signature': 'signature',

            'collateral': 'collateral',

            'residential_proof': 'residential_proof_file',

            'residential_proof_file': 'residential_proof_file',

        }



        doc_requests_qs = (

            DocumentRequest.objects

            .filter(savings_application=app, is_resolved=False)

            .order_by('-requested_at')

        )



        for req in doc_requests_qs:

            latest_reupload = (

                DocumentReupload.objects

                .filter(document_request=req)

                .order_by('-uploaded_at')

                .first()

            )



            file_url = None

            if latest_reupload and getattr(latest_reupload, 'uploaded_file', None):

                try:

                    file_url = latest_reupload.uploaded_file.url

                except Exception:

                    file_url = None



            item = {
                'id': req.id,
                'document_type': req.document_type,
                'document_label': req.get_document_type_display() or req.document_type,
                'requested_at': req.requested_at,
                'file_url': file_url,
            }

            if file_url:

                pending_review_requests.append(item)

            else:

                pending_upload_requests.append(item)



        context['application'] = app
        context['documents'] = documents
        context['pending_requested_doc_types'] = pending_requested_doc_types
        context['pending_review_requests'] = pending_review_requests
        context['pending_upload_requests'] = pending_upload_requests

        return context





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsCollectionsListView(TemplateView):

    template_name = 'savings/collections-list.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('savings/partials/collections-list-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch

        application_id = kwargs.get('application_id')



        account = (

            SavingsAccountApplication.objects

            .filter(application_id=application_id, branch=branch)

            .select_related('customer', 'agent', 'branch')

            .first()

        )

        if not account:

            raise Http404



        today = timezone.now().date()

        tenure_completed = False

        if account.maturity_date:

            tenure_completed = account.maturity_date <= today

        payable_principal = Decimal('0.00')
        payable_interest = Decimal('0.00')
        payable_total = Decimal('0.00')

        if (account.product_type or '').strip().lower() == 'rd':
            rd_payable = _get_rd_interest_as_of(account, today)
            if rd_payable:
                payable_principal = Decimal(rd_payable.get('principal') or 0)
                payable_interest = Decimal(rd_payable.get('interest_total') or 0)
                payable_total = Decimal(rd_payable.get('payable') or 0)
        elif (account.product_type or '').strip().lower() == 'fd':
            fd_principal = (
                SavingsCollection.objects
                .filter(account=account, collection_type='fd_deposit', is_collected=True)
                .aggregate(total=Sum('amount'))
                .get('total')
                or Decimal('0')
            )
            payable_principal = Decimal(fd_principal or 0)
            if tenure_completed and account.maturity_amount is not None:
                payable_total = Decimal(account.maturity_amount or 0)
                payable_interest = (payable_total - payable_principal)
            else:
                payable_total = payable_principal
                payable_interest = Decimal('0.00')

        if not tenure_completed:
            payable_total = payable_principal

        try:
            payable_principal = Decimal(payable_principal).quantize(Decimal('0.01'))
        except Exception:
            payable_principal = Decimal('0.00')
        try:
            payable_interest = Decimal(payable_interest).quantize(Decimal('0.01'))
        except Exception:
            payable_interest = Decimal('0.00')
        try:
            payable_total = Decimal(payable_total).quantize(Decimal('0.01'))
        except Exception:
            payable_total = Decimal('0.00')

        account.payable_principal = payable_principal
        account.payable_interest = payable_interest
        account.payable_total = payable_total



        collections_qs = SavingsCollection.objects.filter(account=account).select_related(

            'collected_by_branch_employee',

            'collected_by_agent',

            'branch',

            'agent',

        ).order_by('-is_expected', 'installment_no', 'collection_date', 'created_at')



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(collections_qs, 20)

        page_obj = paginator.get_page(page_number)



        agents = Agent.objects.filter(branch=branch, status='active').order_by('full_name')

        latest_assignment = (

            SavingsAgentAssign.objects

            .filter(account=account, is_active=True)

            .select_related('agent')

            .first()

        )

        current_assigned_agent = latest_assignment.agent if latest_assignment else None

        selected_agent_id = current_assigned_agent.agent_id if current_assigned_agent else None



        total_amount = (

            collections_qs

            .filter(is_collected=True)

            .aggregate(total=Sum('amount'))

            .get('total')

            or Decimal('0')

        )



        rd_standard_rows = []

        rd_actual_rows = []

        rd_summary = None

        if account.product_type == 'rd':

            rd_summary = _get_rd_interest_as_of(account, timezone.now().date())

            daily_deposit = account.installment_amount

            if daily_deposit is None and account.product_id:

                daily_deposit = (

                    DailyProduct.objects

                    .filter(daily_product_id=account.product_id)

                    .values_list('deposit_amount', flat=True)

                    .first()

                )



            expected_installments = list(

                SavingsCollection.objects

                .filter(account=account, collection_type='rd_installment', is_expected=True)

                .only('installment_no', 'amount', 'is_collected')

                .order_by('installment_no')

            )

            actual_map = {}

            for r in expected_installments:

                if not r.installment_no:

                    continue

                actual_map[int(r.installment_no)] = (Decimal(r.amount or 0) if r.is_collected else Decimal('0'))



            if daily_deposit is not None and account.interest_rate is not None:

                rd_standard_rows = _build_rd_daily_statement(

                    tenure=account.tenure,

                    daily_deposit=Decimal(daily_deposit),

                    rate=Decimal(account.interest_rate),

                    deposits_by_no={},

                )

                rd_actual_rows = _build_rd_daily_statement(

                    tenure=account.tenure,

                    daily_deposit=Decimal('0'),

                    rate=Decimal(account.interest_rate),

                    deposits_by_no=actual_map,

                )



        context['account'] = account

        context['collections'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['total_amount'] = total_amount

        context['agents'] = agents

        context['selected_agent_id'] = selected_agent_id

        context['current_assigned_agent'] = current_assigned_agent

        context['rd_standard_rows'] = rd_standard_rows

        context['rd_actual_rows'] = rd_actual_rows

        context['rd_summary'] = rd_summary

        context['today'] = today

        context['tenure_completed'] = tenure_completed

        has_cash_account = BranchAccount.objects.filter(branch=branch, type='CASH').exists()
        has_bank_account = BranchAccount.objects.filter(branch=branch, type='BANK').exists()

        all_payment_modes = list(getattr(SavingsCollection, 'PAYMENT_MODES', []))
        if has_cash_account and has_bank_account:
            payment_modes = all_payment_modes
        elif has_cash_account:
            payment_modes = [pm for pm in all_payment_modes if pm and pm[0] == 'cash']
        elif has_bank_account:
            payment_modes = [pm for pm in all_payment_modes if pm and pm[0] != 'cash']
        else:
            payment_modes = all_payment_modes

        context['payment_modes'] = payment_modes

        return context





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsAllAccountsListView(TemplateView):

    template_name = 'savings/all-savings-accounts.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('savings/partials/all-savings-accounts-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch



        accounts = (

            SavingsAccountApplication.objects

            .filter(account_id__isnull=False)

            .filter(Q(branch=branch) | Q(branch__isnull=True, agent__branch=branch))

            .select_related('customer', 'agent', 'branch')

        )



        product_type = (self.request.GET.get('product_type') or '').strip()

        if product_type:

            accounts = accounts.filter(product_type=product_type)



        account_status = (self.request.GET.get('account_status') or '').strip().lower()
        if account_status == 'inactive':
            accounts = accounts.filter(status='inactive')
        elif account_status == 'active':
            accounts = accounts.exclude(status='inactive')



        agent_id = (self.request.GET.get('agent_id') or '').strip()

        if agent_id:

            accounts = accounts.filter(agent__agent_id=agent_id)



        q = (self.request.GET.get('q') or '').strip()

        if q:

            accounts = accounts.filter(

                Q(account_id__icontains=q)

                | Q(application_id__icontains=q)

                | Q(customer__full_name__icontains=q)

                | Q(customer__customer_id__icontains=q)

            )



        accounts = accounts.order_by('-hq_approved_at', '-submitted_at')



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(accounts, 15)

        page_obj = paginator.get_page(page_number)

        today = timezone.now().date()
        for acc in page_obj.object_list:
            tenure_completed = False
            if acc.maturity_date:
                tenure_completed = acc.maturity_date <= today
            elif (acc.product_type or '').strip().lower() == 'rd':
                last_due_date = (
                    SavingsCollection.objects
                    .filter(account=acc, collection_type='rd_installment', is_expected=True)
                    .aggregate(last=Max('collection_date'))
                    .get('last')
                )
                if last_due_date:
                    tenure_completed = last_due_date <= today
            acc.tenure_completed = tenure_completed

            collections_completed = False
            if (acc.product_type or '').strip().lower() == 'rd':
                has_pending = SavingsCollection.objects.filter(
                    account=acc,
                    collection_type='rd_installment',
                    is_expected=True,
                    is_collected=False,
                ).exists()
                collections_completed = not has_pending
            elif (acc.product_type or '').strip().lower() == 'fd':
                collections_completed = True
            acc.collections_completed = collections_completed



        agents = (

            Agent.objects

            .filter(branch=branch, status='active')

            .only('agent_id', 'full_name')

            .order_by('full_name')

        )



        context['accounts'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['agents'] = agents

        context['filter_product_type'] = product_type

        context['filter_account_status'] = account_status

        context['filter_agent_id'] = agent_id

        context['filter_q'] = q

        return context





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsCollectionsAccountsListView(TemplateView):

    template_name = 'savings/collections-accounts.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('savings/partials/collections-accounts-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch



        accounts = (

            SavingsAccountApplication.objects

            .filter(branch=branch, account_id__isnull=False, status='hq_approved', product_type='rd')

            .filter(Q(surrender_status__isnull=True) | Q(surrender_status__in=['', 'none']))

            .select_related('customer', 'agent', 'branch')

            .order_by('-hq_approved_at', '-submitted_at')

        )



        agent_id = (self.request.GET.get('agent_id') or '').strip()
        if agent_id:
            accounts = accounts.filter(agent__agent_id=agent_id)



        q = (self.request.GET.get('q') or '').strip()
        if q:
            accounts = accounts.filter(
                Q(account_id__icontains=q)
                | Q(application_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__customer_id__icontains=q)
            )



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(accounts, 20)

        page_obj = paginator.get_page(page_number)



        context['accounts'] = page_obj.object_list

        context['page_obj'] = page_obj

        context['paginator'] = paginator

        context['filter_agent_id'] = agent_id

        context['filter_q'] = q

        context['agents'] = (
            Agent.objects
            .filter(branch=branch, status='active')
            .only('agent_id', 'full_name')
            .order_by('full_name')
        )

        return context



@method_decorator(branch_permission_required(), name='dispatch')
class BranchSavingsSurrenderVerifyAPI(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=403)



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            return JsonResponse({'success': False, 'message': 'Branch employee not found.'}, status=404)



        branch = branch_employee.branch

        application_id = (request.POST.get('application_id') or '').strip()

        if not application_id:

            return JsonResponse({'success': False, 'message': 'Missing application_id.'}, status=400)



        with transaction.atomic():

            account = (

                SavingsAccountApplication.objects

                .select_for_update()

                .filter(application_id=application_id, branch=branch)

                .first()

            )

            if not account:

                return JsonResponse({'success': False, 'message': 'Account not found.'}, status=404)



            current_status = (account.surrender_status or 'none').strip()

            today = timezone.now().date()
            tenure_completed = False
            if account.maturity_date:
                tenure_completed = account.maturity_date <= today
            elif (account.product_type or '').strip().lower() == 'rd':
                last_due_date = (
                    SavingsCollection.objects
                    .filter(account=account, collection_type='rd_installment', is_expected=True)
                    .aggregate(last=Max('collection_date'))
                    .get('last')
                )
                if last_due_date:
                    tenure_completed = last_due_date <= today

            if current_status != 'requested' and not (current_status == 'none' and tenure_completed):

                return JsonResponse(

                    {

                        'success': False,

                        'message': 'Surrender request is not in requested state.',

                        'surrender_status': current_status,

                        'surrender_status_display': account.get_surrender_status_display(),

                    },

                    status=409,

                )

            if current_status == 'none' and tenure_completed:
                account.surrender_status = 'requested'
                account.save(update_fields=['surrender_status', 'last_update'])



            account.surrender_status = 'processing'

            account.save(update_fields=['surrender_status', 'last_update'])



        return JsonResponse(

            {

                'success': True,

                'message': 'Surrender request verified and forwarded to HQ.',

                'application_id': account.application_id,

                'surrender_status': account.surrender_status,

                'surrender_status_display': account.get_surrender_status_display(),

            }

        )



@method_decorator(branch_permission_required(), name='dispatch')
class BranchSavingsSurrenderRequestAPI(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=403)



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            return JsonResponse({'success': False, 'message': 'Branch employee not found.'}, status=404)



        branch = branch_employee.branch

        application_id = (request.POST.get('application_id') or '').strip()

        note = (request.POST.get('note') or '').strip()

        if not application_id:

            return JsonResponse({'success': False, 'message': 'Missing application_id.'}, status=400)



        with transaction.atomic():

            account = (

                SavingsAccountApplication.objects

                .select_for_update()

                .filter(application_id=application_id, branch=branch, account_id__isnull=False, status='hq_approved')

                .first()

            )

            if not account:

                return JsonResponse({'success': False, 'message': 'Account not found.'}, status=404)



            current_status = (account.surrender_status or 'none').strip()

            if current_status and current_status != 'none':

                return JsonResponse(

                    {

                        'success': False,

                        'message': 'Close request already created.',

                        'surrender_status': current_status,

                        'surrender_status_display': account.get_surrender_status_display(),

                    },

                    status=409,

                )



            account.surrender_status = 'requested'

            if note:

                account.surrender_note = note

            account.save(update_fields=['surrender_status', 'surrender_note', 'last_update'])



        return JsonResponse(

            {

                'success': True,

                'message': 'Close request submitted.',

                'application_id': account.application_id,

                'surrender_status': account.surrender_status,

                'surrender_status_display': account.get_surrender_status_display(),

            }

        )



@method_decorator(branch_permission_required(), name='dispatch')
class BranchSavingsSurrenderRequestsListView(TemplateView):

    template_name = 'savings/surrender-requests.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch

        accounts = (

            SavingsAccountApplication.objects

            .filter(

                branch=branch,
                account_id__isnull=False,
                status='hq_approved',
            )
            .exclude(Q(surrender_status__isnull=True) | Q(surrender_status__in=['', 'none']))
            .select_related('customer', 'agent', 'branch')
        )

        product_type = (self.request.GET.get('product_type') or '').strip().lower()
        if product_type in {'rd', 'fd'}:
            accounts = accounts.filter(product_type=product_type)

        agent_id = (self.request.GET.get('agent_id') or '').strip()
        if agent_id:
            accounts = accounts.filter(agent__agent_id=agent_id)

        q = (self.request.GET.get('q') or '').strip()
        if q:
            accounts = accounts.filter(
                Q(account_id__icontains=q)
                | Q(application_id__icontains=q)
                | Q(customer__full_name__icontains=q)
                | Q(customer__customer_id__icontains=q)
            )

        accounts = accounts.order_by('-last_update', '-submitted_at')

        agents = (
            Agent.objects
            .filter(branch=branch, status='active')
            .only('agent_id', 'full_name')
            .order_by('full_name')
        )

        context['accounts'] = accounts
        context['agents'] = agents
        context['filter_product_type'] = product_type
        context['filter_agent_id'] = agent_id
        context['filter_q'] = q

        return context


@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsAssignAgentView(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch

        application_id = kwargs.get('application_id')



        agent_id = (request.POST.get('agent_id') or '').strip()

        if not agent_id:

            return redirect('branch:savings_collections_list', application_id=application_id)



        agent = Agent.objects.filter(agent_id=agent_id, branch=branch, status='active').first()

        if agent is None:

            return redirect('branch:savings_collections_list', application_id=application_id)



        with transaction.atomic():

            account = (

                SavingsAccountApplication.objects

                .select_for_update()

                .get(application_id=application_id, branch=branch)

            )

            account.agent = agent

            account.save(update_fields=['agent', 'last_update'])



            SavingsCollection.objects.filter(

                account=account,

                is_collected=False,

            ).update(agent=agent)



            latest_assignment = (

                SavingsAgentAssign.objects

                .filter(account=account, is_active=True)

                .select_related('agent')

                .first()

            )

            if latest_assignment is None or latest_assignment.agent_id != agent.agent_id:

                SavingsAgentAssign.objects.create(

                    account=account,

                    agent=agent,

                    assigned_by=branch_employee,

                    is_active=True,

                )



        return redirect('branch:savings_collections_list', application_id=application_id)





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsDocumentRequestsView(TemplateView):

    template_name = 'savings/document-requests.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        branch = branch_employee.branch

        context['document_requests'] = (

            DocumentRequest.objects

            .filter(branch=branch, savings_application__isnull=False, is_resolved=False)

            .select_related('savings_application', 'savings_application__customer')

            .order_by('-requested_at')

        )

        return context





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsDocumentUploadAPI(APIView):

    parser_classes = [MultiPartParser, FormParser]



    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            return Response({'success': False, 'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            return Response({'success': False, 'detail': 'Branch employee not found.'}, status=status.HTTP_404_NOT_FOUND)



        branch = branch_employee.branch

        document_request_id = request.data.get('document_request_id')

        document_type = request.data.get('document_type')

        uploaded_file = request.FILES.get('uploaded_file')



        if not document_request_id or not document_type or not uploaded_file:

            return Response({'success': False, 'detail': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)



        try:

            doc_request = (

                DocumentRequest.objects

                .select_related('savings_application', 'savings_application__customer')

                .get(id=document_request_id, branch=branch, savings_application__isnull=False)

            )

        except DocumentRequest.DoesNotExist:

            return Response({'success': False, 'detail': 'Document request not found.'}, status=status.HTTP_404_NOT_FOUND)



        savings_app = doc_request.savings_application

        if not savings_app:

            return Response({'success': False, 'detail': 'Savings application not found for this request.'}, status=status.HTTP_400_BAD_REQUEST)



        field_map = {

            'id_proof': 'id_proof',

            'pan_card_document': 'pan_card_document',

            'id_proof_back': 'id_proof_back',

            'income_proof': 'income_proof',

            'photo': 'photo',

            'signature': 'signature',

            'collateral': 'collateral',

            'residential_proof': 'residential_proof_file',

            'residential_proof_file': 'residential_proof_file',

        }

        field_name = field_map.get(document_type)

        if not field_name:

            return Response({'success': False, 'detail': 'Unsupported document type.'}, status=status.HTTP_400_BAD_REQUEST)



        customer_document, _created = CustomerDocument.objects.get_or_create(

            savings_application=savings_app,

            defaults={

                'loan_application': None,

                'branch': branch,

                'agent': getattr(savings_app, 'agent', None),

            },

        )



        setattr(customer_document, field_name, uploaded_file)

        customer_document.branch = branch

        customer_document.save()



        DocumentReupload.objects.create(

            document_request=doc_request,

            loan_application=None,

            document_type=document_type,

            uploaded_file=uploaded_file,

            uploaded_by=None,

        )



        if savings_app.status == 'document_requested':

            savings_app.status = 'resubmitted'

            savings_app.save(update_fields=['status', 'last_update'])

        elif savings_app.status in ['document_requested_by_hq', 'hq_resubmitted']:

            doc_request.mark_as_resolved()

            savings_app.status = 'branch_resubmitted'

            savings_app.save(update_fields=['status', 'last_update'])

        else:

            doc_request.mark_as_resolved()



        return Response({'success': True})





@method_decorator(branch_permission_required(), name='dispatch')

class BranchApproveSavingsApplicationView(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        application_id = kwargs.get('application_id')

        branch = branch_employee.branch



        app = SavingsAccountApplication.objects.filter(application_id=application_id, branch=branch).first()

        if not app:

            raise Http404



        if app.status == 'resubmitted':

            app.status = 'branch_resubmitted'

        else:

            app.status = 'branch_approved'

        app.save(update_fields=['status', 'last_update'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Savings application approved successfully.',
                'redirect_url': reverse('branch:pending_savings_applications'),
            })

        return redirect('branch:pending_savings_applications')





@method_decorator(branch_permission_required(), name='dispatch')

class BranchAcceptSavingsDocumentsView(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        application_id = kwargs.get('application_id')

        branch = branch_employee.branch



        app = (

            SavingsAccountApplication.objects

            .filter(application_id=application_id)

            .filter(Q(branch=branch) | Q(branch__isnull=True, agent__branch=branch))

            .first()

        )

        if not app:

            raise Http404



        if app.status == 'resubmitted':

            app.status = 'branch_document_accepted'

            app.save(update_fields=['status', 'last_update'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Documents accepted successfully.',
                'redirect_url': reverse('branch:savings_application_detail', kwargs={'application_id': application_id}),
            })



        return redirect('branch:savings_application_detail', application_id=application_id)





@method_decorator(branch_permission_required(), name='dispatch')

class BranchRejectSavingsApplicationView(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        application_id = kwargs.get('application_id')

        branch = branch_employee.branch



        app = SavingsAccountApplication.objects.filter(application_id=application_id, branch=branch).first()

        if not app:

            raise Http404



        reason = (request.POST.get('reason') or '').strip()

        if not reason:

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Please provide a rejection reason.'}, status=400)

            return redirect('branch:savings_application_detail', application_id=application_id)



        app.status = 'rejected_by_branch'

        app.rejection_reason = reason

        app.save(update_fields=['status', 'rejection_reason', 'last_update'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Savings application rejected successfully.',
                'redirect_url': reverse('branch:pending_savings_applications'),
            })

        return redirect('branch:pending_savings_applications')





@method_decorator(branch_permission_required(), name='dispatch')

class BranchResubmitSavingsApplicationView(View):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            raise Http404



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            raise Http404



        application_id = kwargs.get('application_id')

        branch = branch_employee.branch



        app = SavingsAccountApplication.objects.filter(application_id=application_id, branch=branch).first()

        if not app:

            raise Http404



        app.status = 'document_requested'

        app.save(update_fields=['status', 'last_update'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Document re-upload requested successfully.',
                'redirect_url': reverse('branch:savings_application_detail', kwargs={'application_id': application_id}),
            })

        return redirect('branch:savings_application_detail', application_id=application_id)





@method_decorator(branch_permission_required(), name='dispatch')

class BranchNewSavingsApplication(TemplateView):

    template_name = 'savings/new-application.html'



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context['base_template'] = 'branch/base.html'

        context['dashboard_url_name'] = 'branch:dashboard'

        return context





@method_decorator(branch_permission_required(), name='dispatch')

class BranchPendingSavingsApplications(TemplateView):

    template_name = 'savings/pending-applications.html'



    def get(self, request, *args, **kwargs):

        if (request.GET.get('partial') or '').strip() == '1':

            context = self.get_context_data(**kwargs)

            html = render_to_string('savings/partials/pending-applications-rows.html', context, request=request)

            return HttpResponse(html)



        return super().get(request, *args, **kwargs)



    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')

        branch = None

        if logged_user_id:

            try:

                branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

                branch = branch_employee.branch

            except BranchEmployee.DoesNotExist:

                None



        qs = SavingsAccountApplication.objects.filter(status__in=[

            'pending',

            'document_requested',

            'resubmitted',

            'branch_document_accepted',

            'branch_resubmitted',

            'branch_approved',

            'document_requested_by_hq',

            'hq_resubmitted',

        ]).filter(
            Q(surrender_status__isnull=True) | Q(surrender_status__in=['', 'none'])
        )

        if branch is not None:

            qs = qs.filter(

                Q(branch=branch) |

                Q(branch__isnull=True, agent__branch=branch)

            )



        qs = qs.select_related('customer', 'agent', 'branch').order_by('-submitted_at')



        page_number_raw = (self.request.GET.get('page') or '1').strip()

        try:

            page_number = int(page_number_raw)

        except ValueError:

            page_number = 1

        if page_number < 1:

            page_number = 1



        paginator = Paginator(qs, 20)

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

        return context





class CustomerLookupAPI(APIView):

    def get(self, request, *args, **kwargs):

        agent_id = request.session.get('agent_id')

        if not agent_id:

            return Response({'success': False, 'message': 'Authentication required.'}, status=400)



        q = (request.query_params.get('q') or '').strip()

        suggest = (request.query_params.get('suggest') or '').strip() == '1'

        if suggest:
            q_norm = q

            limit_raw = (request.query_params.get('limit') or '').strip()
            offset_raw = (request.query_params.get('offset') or '').strip()
            try:
                limit = int(limit_raw) if limit_raw else 10
            except ValueError:
                limit = 10
            try:
                offset = int(offset_raw) if offset_raw else 0
            except ValueError:
                offset = 0

            if limit < 1:
                limit = 10
            if limit > 50:
                limit = 50
            if offset < 0:
                offset = 0

            qs = CustomerDetail.objects.filter(agent__agent_id=agent_id, loan_application__isnull=False)
            if q_norm:
                qs = qs.filter(
                    Q(customer_id__icontains=q_norm)
                    | Q(full_name__icontains=q_norm)
                    | Q(adhar_number__icontains=q_norm)
                    | Q(pan_number__icontains=q_norm)
                    | Q(contact__icontains=q_norm)
                )

            customers_qs = (
                qs
                .only('customer_id', 'full_name', 'adhar_number', 'pan_number')
                .order_by('-submitted_at')
            )

            customers_plus = list(customers_qs[offset:offset + limit + 1])
            has_more = len(customers_plus) > limit
            customers = customers_plus[:limit]

            customer_ids = [c.customer_id for c in customers]
            counts_by_customer = {cid: {'fd': 0, 'rd': 0} for cid in customer_ids}
            if customer_ids:
                for row in (
                    SavingsAccountApplication.objects
                    .filter(customer_id__in=customer_ids)
                    .values('customer_id', 'product_type')
                    .annotate(cnt=Count('application_id'))
                ):
                    cid = row.get('customer_id')
                    ptype = row.get('product_type')
                    if cid in counts_by_customer and ptype in ['fd', 'rd']:
                        counts_by_customer[cid][ptype] = int(row.get('cnt') or 0)

            return Response(
                {
                    'success': True,
                    'customers': [
                        {
                            'customer_id': c.customer_id,
                            'full_name': c.full_name,
                            'adhar_number': c.adhar_number,
                            'pan_number': c.pan_number,
                            'fd_count': counts_by_customer.get(c.customer_id, {}).get('fd', 0),
                            'rd_count': counts_by_customer.get(c.customer_id, {}).get('rd', 0),
                        }
                        for c in customers
                    ],
                    'has_more': has_more,
                    'next_offset': (offset + limit if has_more else None),
                }
            )

        if not q:

            return Response({'success': False, 'message': 'Query is required.'}, status=400)



        customer = (
            CustomerDetail.objects
            .filter(agent__agent_id=agent_id, loan_application__isnull=False)
            .filter(
                Q(customer_id__iexact=q)
                | Q(adhar_number__iexact=q)
                | Q(pan_number__iexact=q)
                | Q(contact__iexact=q)
            )
            .select_related('address')
            .first()
        )



        if not customer:

            return Response({'success': False, 'message': 'Customer not found.'}, status=404)



        address = getattr(customer, 'address', None)



        existing_docs = None

        if getattr(customer, 'loan_application_id', None):

            existing_docs = CustomerDocument.objects.filter(loan_application=customer.loan_application).first()

        if existing_docs is None:

            latest_savings_app = (

                SavingsAccountApplication.objects

                .filter(customer=customer)

                .order_by('-submitted_at')

                .first()

            )

            if latest_savings_app is not None:

                existing_docs = CustomerDocument.objects.filter(savings_application=latest_savings_app).first()



        return Response({

            'success': True,

            'customer': {

                'customer_id': customer.customer_id,

                'full_name': customer.full_name,

                'father_name': customer.father_name,

                'date_of_birth': str(customer.date_of_birth),

                'gender': customer.gender,

                'contact': customer.contact,

                'email': customer.email,

                'adhar_number': customer.adhar_number,

                'pan_number': customer.pan_number,

            },

            'documents': {

                'id_proof': (existing_docs.id_proof.url if existing_docs and existing_docs.id_proof else None),

                'pan_card_document': (existing_docs.pan_card_document.url if existing_docs and existing_docs.pan_card_document else None),

                'id_proof_back': (existing_docs.id_proof_back.url if existing_docs and existing_docs.id_proof_back else None),

                'photo': (existing_docs.photo.url if existing_docs and existing_docs.photo else None),

                'signature': (existing_docs.signature.url if existing_docs and existing_docs.signature else None),

                'residential_proof_file': (existing_docs.residential_proof_file.url if existing_docs and existing_docs.residential_proof_file else None),

                'has_any': bool(existing_docs),

            },

            'address': {

                'address_line_1': address.address_line_1 if address else '',

                'address_line_2': address.address_line_2 if address else '',

                'landmark': address.landmark if address else '',

                'post_office': address.post_office if address else '',

                'city_or_town': address.city_or_town if address else '',

                'district': address.district if address else '',

                'state': address.state if address else '',

                'country': address.country if address else 'India',

                'post_code': address.post_code if address else '',

                'current_address_line_1': address.current_address_line_1 if address else '',

                'current_address_line_2': address.current_address_line_2 if address else '',

                'current_landmark': address.current_landmark if address else '',

                'current_post_office': address.current_post_office if address else '',

                'current_city_or_town': address.current_city_or_town if address else '',

                'current_district': address.current_district if address else '',

                'current_state': address.current_state if address else '',

                'current_country': address.current_country if address else 'India',

                'current_post_code': address.current_post_code if address else '',

            }

        })





@method_decorator(branch_permission_required(), name='dispatch')

class BranchSavingsCollectionCreateAPI(APIView):

    def post(self, request, *args, **kwargs):

        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            return Response({'success': False, 'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            return Response({'success': False, 'detail': 'Branch employee not found.'}, status=status.HTTP_404_NOT_FOUND)



        account_id = (request.data.get('account_id') or '').strip()

        collection_type = (request.data.get('collection_type') or '').strip()

        amount_raw = request.data.get('amount')

        collection_date = request.data.get('collection_date')

        expected_collection_id = (request.data.get('expected_collection_id') or '').strip() or None



        if not account_id or not collection_type or amount_raw is None or not collection_date:

            return Response({'success': False, 'detail': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)



        try:

            collection_date = datetime.strptime(str(collection_date), '%Y-%m-%d').date()

        except (TypeError, ValueError):

            return Response({'success': False, 'detail': 'Invalid collection_date. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)



        try:

            amount = Decimal(str(amount_raw))

        except (InvalidOperation, TypeError):

            return Response({'success': False, 'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)



        if amount <= 0:

            return Response({'success': False, 'detail': 'Amount must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)



        if collection_type not in dict(SavingsCollection.TXN_TYPES):

            return Response({'success': False, 'detail': 'Invalid collection_type.'}, status=status.HTTP_400_BAD_REQUEST)



        if collection_type == 'fd_deposit':

            return Response(

                {'success': False, 'detail': 'FD deposit collection is disabled. FD starts on HQ approval date.'},

                status=status.HTTP_400_BAD_REQUEST,

            )



        account = SavingsAccountApplication.objects.filter(account_id=account_id, branch=branch_employee.branch).first()

        if not account:

            return Response({'success': False, 'detail': 'Account not found for this branch.'}, status=status.HTTP_404_NOT_FOUND)



        if account.status != 'hq_approved':

            return Response({'success': False, 'detail': 'Account is not active for collections.'}, status=status.HTTP_400_BAD_REQUEST)



        payment_mode = (request.data.get('payment_mode') or 'cash').strip()

        receipt_no = (request.data.get('receipt_no') or '').strip() or None

        note = (request.data.get('note') or '').strip() or None



        with transaction.atomic():

            account = (

                SavingsAccountApplication.objects

                .select_for_update()

                .get(pk=account.application_id)

            )

            current_surrender_status = (account.surrender_status or 'none').strip()

            if current_surrender_status and current_surrender_status != 'none':
                if not (current_surrender_status == 'approved' and collection_type == 'withdrawal'):
                    return Response(
                        {
                            'success': False,
                            'detail': 'Collections are paused because surrender request is active.',
                            'message': 'Collections are paused because surrender request is active.',
                            'surrender_status': current_surrender_status,
                            'surrender_status_display': account.get_surrender_status_display(),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )



            account.ensure_expected_collections_schedule()



            if collection_type == 'rd_installment':

                today = timezone.now().date()

                if collection_date != today:

                    return Response(

                        {'success': False, 'detail': 'RD installment can only be collected for today.'},

                        status=status.HTTP_400_BAD_REQUEST,

                    )



            if collection_type == 'rd_installment':

                existing_same_day_qs = SavingsCollection.objects.select_for_update().filter(

                    account=account,

                    collection_type='rd_installment',

                    is_collected=True,

                    collection_date=collection_date,

                )

                if expected_collection_id:

                    existing_same_day_qs = existing_same_day_qs.exclude(collection_id=expected_collection_id)



                if existing_same_day_qs.exists():

                    return Response(

                        {'success': False, 'detail': 'Only one RD installment can be collected per day for this account.'},

                        status=status.HTTP_400_BAD_REQUEST,

                    )



            account_type = 'CASH' if payment_mode == 'cash' else 'BANK'

            branch_account = (

                BranchAccount.objects

                .select_for_update()

                .filter(branch=branch_employee.branch, type=account_type)

                .order_by('-updated_at', '-created_at')

                .first()

            )

            if branch_account is None:

                return Response(

                    {'success': False, 'detail': f"No branch {account_type} account found to credit this collection."},

                    status=status.HTTP_400_BAD_REQUEST,

                )



            expected_row = None

            if collection_type in ['rd_installment']:

                expected_qs = (

                    SavingsCollection.objects

                    .select_for_update()

                    .filter(

                        account=account,

                        collection_type=collection_type,

                        is_expected=True,

                        is_collected=False,

                    )

                )

                if expected_collection_id:

                    expected_row = expected_qs.filter(collection_id=expected_collection_id).first()

                    if expected_row is None:

                        return Response(

                            {'success': False, 'detail': 'Expected installment not found or already collected.'},

                            status=status.HTTP_400_BAD_REQUEST,

                        )

                else:

                    expected_row = expected_qs.order_by('installment_no', 'collection_date', 'created_at').first()



            if expected_row is not None:

                if collection_type == 'rd_installment' and expected_row.collection_date and expected_row.collection_date < timezone.now().date():

                    return Response(

                        {'success': False, 'detail': 'This RD installment is missed and cannot be collected now.'},

                        status=status.HTTP_400_BAD_REQUEST,

                    )

                expected_row.amount = amount

                expected_row.collection_date = collection_date

                expected_row.receipt_no = receipt_no

                expected_row.payment_mode = payment_mode

                expected_row.note = note

                expected_row.collected_by_branch_employee = branch_employee

                expected_row.branch = branch_employee.branch

                expected_row.is_collected = True

                expected_row.save(update_fields=[

                    'amount', 'collection_date', 'receipt_no', 'payment_mode', 'note',

                    'collected_by_branch_employee', 'branch', 'is_collected',

                ])

                collection = expected_row

            else:

                collection = SavingsCollection.objects.create(

                    account=account,

                    collection_type=collection_type,

                    amount=amount,

                    collection_date=collection_date,

                    receipt_no=receipt_no,

                    payment_mode=payment_mode,

                    note=note,

                    branch=branch_employee.branch,

                    collected_by_branch_employee=branch_employee,

                    is_expected=False,

                    is_collected=True,

                )



            if collection_type == 'withdrawal':

                if account.withdraw_date or account.withdraw_amount:
                    return Response({'success': False, 'detail': 'Account is already withdrawn/closed.'}, status=status.HTTP_409_CONFLICT)

                if Decimal(branch_account.current_balance or 0) < amount:
                    return Response({'success': False, 'detail': 'Insufficient branch balance for withdrawal.'}, status=status.HTTP_400_BAD_REQUEST)

                branch_account.current_balance = (Decimal(branch_account.current_balance) - amount).quantize(Decimal('0.01'))
                branch_account.updated_by = branch_employee
                branch_account.save(update_fields=['current_balance', 'updated_by', 'updated_at'])

                account.withdraw_date = collection_date
                account.withdraw_amount = amount
                account.status = 'inactive'
                if current_surrender_status == 'approved':
                    account.surrender_status = 'completed'
                account.save(update_fields=['withdraw_date', 'withdraw_amount', 'status', 'surrender_status', 'last_update'])

                BranchTransaction.objects.create(
                    branch=branch_employee.branch,
                    branch_account=branch_account,
                    disbursement_log=None,
                    transaction_type='DEBIT',
                    purpose='Savings Withdraw/Close',
                    code='206',
                    mode=payment_mode,
                    bank_payment_method=payment_mode if payment_mode in ['upi', 'bank'] else None,
                    amount=amount,
                    transfer_to_from=None,
                    description=f"Savings withdrawal for {account.account_id} ({collection.collection_id})",
                    transaction_date=timezone.now(),
                    created_by=branch_employee,
                )

                return Response({'success': True, 'collection_id': collection.collection_id})

            branch_account.current_balance = (Decimal(branch_account.current_balance) + amount).quantize(Decimal('0.01'))

            branch_account.updated_by = branch_employee

            branch_account.save(update_fields=['current_balance', 'updated_by', 'updated_at'])



            if collection_type == 'rd_installment':

                try:

                    _apply_rd_daily_interest(account, collection.collection_date)

                except ValueError as e:

                    return Response({'success': False, 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

                account.rd_principal_balance = (Decimal(account.rd_principal_balance or 0) + amount).quantize(Decimal('0.01'))

                if account.rd_last_interest_date is None:

                    account.rd_last_interest_date = collection.collection_date

                account.save(update_fields=['rd_principal_balance', 'rd_interest_accrued', 'rd_last_interest_date', 'last_update'])



            BranchTransaction.objects.create(

                branch=branch_employee.branch,

                branch_account=branch_account,

                disbursement_log=None,

                transaction_type='CREDIT',

                purpose=f"Savings Collection - {collection_type}",

                code='204',

                mode=payment_mode,

                bank_payment_method=payment_mode if payment_mode in ['upi', 'bank'] else None,

                amount=amount,

                transfer_to_from=None,

                description=f"Savings collection for {account.account_id} ({collection.collection_id})",

                transaction_date=timezone.now(),

                created_by=branch_employee,

            )



        return Response({'success': True, 'collection_id': collection.collection_id})





class AgentSavingsCollectionCreateAPI(AgentSessionRequiredMixin, APIView):

    def post(self, request, *args, **kwargs):

        agent_id = request.session.get('agent_id')

        if not agent_id:

            return Response({'success': False, 'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)



        try:

            agent = Agent.objects.get(agent_id=agent_id)

        except Agent.DoesNotExist:

            return Response({'success': False, 'detail': 'Agent not found.'}, status=status.HTTP_404_NOT_FOUND)



        account_id = (request.data.get('account_id') or '').strip()

        collection_type = (request.data.get('collection_type') or '').strip()

        amount_raw = request.data.get('amount')

        collection_date = request.data.get('collection_date')

        expected_collection_id = (request.data.get('expected_collection_id') or '').strip() or None



        if not account_id or not collection_type or amount_raw is None or not collection_date:

            return Response({'success': False, 'detail': 'Missing required fields.'}, status=status.HTTP_400_BAD_REQUEST)



        try:

            collection_date = datetime.strptime(str(collection_date), '%Y-%m-%d').date()

        except (TypeError, ValueError):

            return Response({'success': False, 'detail': 'Invalid collection_date. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)



        try:

            amount = Decimal(str(amount_raw))

        except (InvalidOperation, TypeError):

            return Response({'success': False, 'detail': 'Invalid amount.'}, status=status.HTTP_400_BAD_REQUEST)



        if amount <= 0:

            return Response({'success': False, 'detail': 'Amount must be greater than 0.'}, status=status.HTTP_400_BAD_REQUEST)



        if collection_type not in dict(SavingsCollection.TXN_TYPES):

            return Response({'success': False, 'detail': 'Invalid collection_type.'}, status=status.HTTP_400_BAD_REQUEST)



        if collection_type == 'fd_deposit':

            return Response(

                {'success': False, 'detail': 'FD deposit collection is disabled. FD starts on HQ approval date.'},

                status=status.HTTP_400_BAD_REQUEST,

            )



        account = SavingsAccountApplication.objects.filter(account_id=account_id, agent=agent).first()

        if not account:

            return Response({'success': False, 'detail': 'Account not found for this agent.'}, status=status.HTTP_404_NOT_FOUND)



        if account.status != 'hq_approved':

            return Response({'success': False, 'detail': 'Account is not active for collections.'}, status=status.HTTP_400_BAD_REQUEST)



        payment_mode = (request.data.get('payment_mode') or 'cash').strip()

        receipt_no = (request.data.get('receipt_no') or '').strip() or None

        note = (request.data.get('note') or '').strip() or None



        with transaction.atomic():

            account = (

                SavingsAccountApplication.objects

                .select_for_update()

                .get(pk=account.application_id)

            )



            account.ensure_expected_collections_schedule()



            if collection_type == 'rd_installment':

                today = timezone.now().date()

                if collection_date != today:

                    return Response(

                        {'success': False, 'detail': 'RD installment can only be collected for today.'},

                        status=status.HTTP_400_BAD_REQUEST,

                    )



                existing_same_day_qs = SavingsCollection.objects.select_for_update().filter(

                    account=account,

                    collection_type='rd_installment',

                    is_collected=True,

                    collection_date=collection_date,

                )

                if expected_collection_id:

                    existing_same_day_qs = existing_same_day_qs.exclude(collection_id=expected_collection_id)



                if existing_same_day_qs.exists():

                    return Response(

                        {'success': False, 'detail': 'Only one RD installment can be collected per day for this account.'},

                        status=status.HTTP_400_BAD_REQUEST,

                    )



            expected_row = None

            if collection_type in ['rd_installment']:

                expected_qs = (

                    SavingsCollection.objects

                    .select_for_update()

                    .filter(

                        account=account,

                        collection_type=collection_type,

                        is_expected=True,

                        is_collected=False,

                    )

                )

                if expected_collection_id:

                    expected_row = expected_qs.filter(collection_id=expected_collection_id).first()

                    if expected_row is None:

                        return Response(

                            {'success': False, 'detail': 'Expected installment not found or already collected.'},

                            status=status.HTTP_400_BAD_REQUEST,

                        )

                else:

                    expected_row = expected_qs.order_by('installment_no', 'collection_date', 'created_at').first()



            if expected_row is not None:

                if collection_type == 'rd_installment' and expected_row.collection_date and expected_row.collection_date < timezone.now().date():

                    return Response(

                        {'success': False, 'detail': 'This RD installment is missed and cannot be collected now.'},

                        status=status.HTTP_400_BAD_REQUEST,

                    )



                expected_row.amount = amount

                expected_row.collection_date = collection_date

                expected_row.receipt_no = receipt_no

                expected_row.payment_mode = payment_mode

                expected_row.note = note

                expected_row.collected_by_agent = agent

                expected_row.branch = account.branch

                expected_row.is_collected = True

                expected_row.save(update_fields=[

                    'amount', 'collection_date', 'receipt_no', 'payment_mode', 'note',

                    'collected_by_agent', 'branch', 'is_collected',

                ])

                collection = expected_row

            else:

                collection = SavingsCollection.objects.create(

                    account=account,

                    collection_type=collection_type,

                    amount=amount,

                    collection_date=collection_date,

                    receipt_no=receipt_no,

                    payment_mode=payment_mode,

                    note=note,

                    branch=account.branch,

                    collected_by_agent=agent,

                    is_expected=False,

                    is_collected=True,

                )



            if collection_type == 'rd_installment':

                try:

                    _apply_rd_daily_interest(account, collection.collection_date)

                except ValueError as e:

                    return Response({'success': False, 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

                account.rd_principal_balance = (Decimal(account.rd_principal_balance or 0) + amount).quantize(Decimal('0.01'))

                if account.rd_last_interest_date is None:

                    account.rd_last_interest_date = collection.collection_date

                account.save(update_fields=['rd_principal_balance', 'rd_interest_accrued', 'rd_last_interest_date', 'last_update'])



        return Response({'success': True, 'collection_id': collection.collection_id})





class SavingsMasterDataAPI(APIView):

    def get(self, request, *args, **kwargs):

        agent_id = request.session.get('agent_id')

        if not agent_id:

            return Response({'success': False, 'message': 'Authentication required.'}, status=400)



        types_qs = SavingType.objects.filter(is_active=True).order_by('name')

        one_time_qs = OneTimeDeposit.objects.filter(is_active=True).order_by('deposit_amount', 'tenure', 'tenure_unit', 'payable_amount')

        daily_qs = DailyProduct.objects.filter(is_active=True).order_by('deposit_amount', 'interest_rate', 'tenure', 'tenure_unit')



        return Response({

            'success': True,

            'types': [{'id': t.type_id, 'name': t.name} for t in types_qs],

            'interests': [],

            'tenures': [],

            'one_time_deposits': [

                {

                    'id': d.one_time_deposit_id,

                    'deposit_amount': str(d.deposit_amount),

                    'payable_amount': (str(d.payable_amount) if d.payable_amount is not None else None),

                    'tenure': d.tenure,

                    'tenure_unit': d.tenure_unit,

                }

                for d in one_time_qs

            ],

            'daily_products': [

                {

                    'id': d.daily_product_id,

                    'deposit_amount': str(d.deposit_amount),

                    'interest_rate': str(d.interest_rate),

                    'tenure': d.tenure,

                    'tenure_unit': d.tenure_unit,

                }

                for d in daily_qs

            ],

        })





class BranchSavingsMasterDataAPI(APIView):

    @method_decorator(branch_permission_required())

    def get(self, request, *args, **kwargs):

        types_qs = SavingType.objects.filter(is_active=True).order_by('name')

        one_time_qs = OneTimeDeposit.objects.filter(is_active=True).order_by('deposit_amount', 'tenure', 'tenure_unit', 'payable_amount')

        daily_qs = DailyProduct.objects.filter(is_active=True).order_by('deposit_amount', 'interest_rate', 'tenure', 'tenure_unit')



        return Response({

            'success': True,

            'types': [{'id': t.type_id, 'name': t.name} for t in types_qs],

            'interests': [],

            'tenures': [],

            'one_time_deposits': [

                {

                    'id': d.one_time_deposit_id,

                    'deposit_amount': str(d.deposit_amount),

                    'payable_amount': (str(d.payable_amount) if d.payable_amount is not None else None),

                    'tenure': d.tenure,

                    'tenure_unit': d.tenure_unit,

                }

                for d in one_time_qs

            ],

            'daily_products': [

                {

                    'id': d.daily_product_id,

                    'deposit_amount': str(d.deposit_amount),

                    'interest_rate': str(d.interest_rate),

                    'tenure': d.tenure,

                    'tenure_unit': d.tenure_unit,

                }

                for d in daily_qs

            ],

        })





class BranchCustomerLookupAPI(APIView):

    @method_decorator(branch_permission_required())

    def get(self, request, *args, **kwargs):

        q = (request.query_params.get('q') or '').strip()

        suggest = (request.query_params.get('suggest') or '').strip() == '1'

        if suggest:
            q_norm = q

            limit_raw = (request.query_params.get('limit') or '').strip()
            offset_raw = (request.query_params.get('offset') or '').strip()
            try:
                limit = int(limit_raw) if limit_raw else 10
            except ValueError:
                limit = 10
            try:
                offset = int(offset_raw) if offset_raw else 0
            except ValueError:
                offset = 0

            if limit < 1:
                limit = 10
            if limit > 50:
                limit = 50
            if offset < 0:
                offset = 0

            qs = CustomerDetail.objects.all()
            if q_norm:
                qs = qs.filter(
                    Q(customer_id__icontains=q_norm)
                    | Q(full_name__icontains=q_norm)
                    | Q(adhar_number__icontains=q_norm)
                    | Q(pan_number__icontains=q_norm)
                    | Q(contact__icontains=q_norm)
                )

            customers_qs = (
                qs
                .only('customer_id', 'full_name', 'adhar_number', 'pan_number')
                .order_by('-submitted_at')
            )

            customers_plus = list(customers_qs[offset:offset + limit + 1])
            has_more = len(customers_plus) > limit
            customers = customers_plus[:limit]

            customer_ids = [c.customer_id for c in customers]
            counts_by_customer = {cid: {'fd': 0, 'rd': 0} for cid in customer_ids}
            if customer_ids:
                for row in (
                    SavingsAccountApplication.objects
                    .filter(customer_id__in=customer_ids)
                    .values('customer_id', 'product_type')
                    .annotate(cnt=Count('application_id'))
                ):
                    cid = row.get('customer_id')
                    ptype = row.get('product_type')
                    if cid in counts_by_customer and ptype in ['fd', 'rd']:
                        counts_by_customer[cid][ptype] = int(row.get('cnt') or 0)

            return Response(
                {
                    'success': True,
                    'customers': [
                        {
                            'customer_id': c.customer_id,
                            'full_name': c.full_name,
                            'adhar_number': c.adhar_number,
                            'pan_number': c.pan_number,
                            'fd_count': counts_by_customer.get(c.customer_id, {}).get('fd', 0),
                            'rd_count': counts_by_customer.get(c.customer_id, {}).get('rd', 0),
                        }
                        for c in customers
                    ],
                    'has_more': has_more,
                    'next_offset': (offset + limit if has_more else None),
                }
            )

        if not q:

            return Response({'success': False, 'message': 'Query is required.'}, status=400)



        customer = CustomerDetail.objects.filter(

            Q(customer_id__iexact=q) |

            Q(adhar_number__iexact=q) |

            Q(pan_number__iexact=q) |

            Q(contact__iexact=q)

        ).select_related('address').first()



        if not customer:

            return Response({'success': False, 'message': 'Customer not found.'}, status=404)



        address = getattr(customer, 'address', None)



        existing_docs = None

        if getattr(customer, 'loan_application_id', None):

            existing_docs = CustomerDocument.objects.filter(loan_application=customer.loan_application).first()

        if existing_docs is None:

            latest_savings_app = (

                SavingsAccountApplication.objects

                .filter(customer=customer)

                .order_by('-submitted_at')

                .first()

            )

            if latest_savings_app is not None:

                existing_docs = CustomerDocument.objects.filter(savings_application=latest_savings_app).first()



        return Response({

            'success': True,

            'customer': {

                'customer_id': customer.customer_id,

                'full_name': customer.full_name,

                'father_name': customer.father_name,

                'date_of_birth': str(customer.date_of_birth),

                'gender': customer.gender,

                'contact': customer.contact,

                'email': customer.email,

                'adhar_number': customer.adhar_number,

                'pan_number': customer.pan_number,

            },

            'documents': {

                'id_proof': (existing_docs.id_proof.url if existing_docs and existing_docs.id_proof else None),

                'pan_card_document': (existing_docs.pan_card_document.url if existing_docs and existing_docs.pan_card_document else None),

                'id_proof_back': (existing_docs.id_proof_back.url if existing_docs and existing_docs.id_proof_back else None),

                'photo': (existing_docs.photo.url if existing_docs and existing_docs.photo else None),

                'signature': (existing_docs.signature.url if existing_docs and existing_docs.signature else None),

                'residential_proof_file': (existing_docs.residential_proof_file.url if existing_docs and existing_docs.residential_proof_file else None),

                'has_any': bool(existing_docs),

            },

            'address': {

                'address_line_1': address.address_line_1 if address else '',

                'address_line_2': address.address_line_2 if address else '',

                'landmark': address.landmark if address else '',

                'post_office': address.post_office if address else '',

                'city_or_town': address.city_or_town if address else '',

                'district': address.district if address else '',

                'state': address.state if address else '',

                'country': address.country if address else 'India',

                'post_code': address.post_code if address else '',

                'current_address_line_1': address.current_address_line_1 if address else '',

                'current_address_line_2': address.current_address_line_2 if address else '',

                'current_landmark': address.current_landmark if address else '',

                'current_post_office': address.current_post_office if address else '',

                'current_city_or_town': address.current_city_or_town if address else '',

                'current_district': address.current_district if address else '',

                'current_state': address.current_state if address else '',

                'current_country': address.current_country if address else 'India',

                'current_post_code': address.current_post_code if address else '',

            }

        })





class NewSavingsApplicationAPI(APIView):

    parser_classes = (MultiPartParser, FormParser)

    def _generate_pdf_for_email(self, html_content):
        """Generate PDF for email attachment using Playwright"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._generate_pdf_async(html_content))
        finally:
            loop.close()

    async def _generate_pdf_async(self, html_content):
        """Generate PDF from HTML content using Playwright"""
        browser = None
        try:
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=True)
                except Exception:
                    await self._install_playwright_chromium_for_email()
                    browser = await p.chromium.launch(headless=True)

                page = await browser.new_page()
                page.set_default_timeout(30000)
                await page.set_content(html_content, wait_until='domcontentloaded')
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
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    async def _install_playwright_chromium_for_email(self):
        """Install Playwright Chromium browser if missing. Runs once when needed."""
        cmd = [sys.executable, '-m', 'playwright', 'install', 'chromium']

        def _run():
            return subprocess.run(cmd, check=True, capture_output=True)

        await asyncio.to_thread(_run)



    @method_decorator(csrf_exempt)

    def post(self, request, *args, **kwargs):

        data = request.data

        files = request.FILES



        required_fields = [

            'full_name', 'date_of_birth', 'gender', 'contact', 'adhar_number',

            'address_line_1', 'state', 'post_code',

            'product_type', 'product_id',

        ]

        # required_file_fields = ['id_proof', 'pan_card_document', 'photo', 'signature']
        required_file_fields = ['id_proof']



        errors = {}



        for f in required_fields:

            if not data.get(f):

                errors[f] = 'This field is required.'

        use_existing_documents = str(data.get('use_existing_documents') or '').strip().lower() in ('1', 'true', 'yes', 'on')



        for f in required_file_fields:

            if not use_existing_documents and not files.get(f):

                errors[f] = 'This file is required.'



        product_type = (data.get('product_type') or '').strip().lower()

        if product_type not in ('fd', 'rd'):

            errors['product_type'] = 'Invalid product type.'

        product_id = (data.get('product_id') or '').strip()

        selected_product = None

        if not product_id:

            errors['product_id'] = 'This field is required.'

        else:

            try:

                if product_type == 'fd':

                    selected_product = OneTimeDeposit.objects.get(one_time_deposit_id=product_id, is_active=True)

                elif product_type == 'rd':

                    selected_product = DailyProduct.objects.get(daily_product_id=product_id, is_active=True)

            except (OneTimeDeposit.DoesNotExist, DailyProduct.DoesNotExist):

                errors['product_id'] = 'Selected product not found.'



        installment_amount_decimal = None

        interest_rate_decimal = None

        tenure = None



        if selected_product is not None:

            installment_amount_decimal = selected_product.deposit_amount

            if product_type == 'fd':

                interest_rate_decimal = None

            else:

                interest_rate_decimal = selected_product.interest_rate

            tenure = int(selected_product.tenure)



        post_code = (data.get('post_code') or '').strip()

        if post_code and not (post_code.isdigit() and len(post_code) == 6):

            errors['post_code'] = 'Post code must be exactly 6 digits.'



        existing_customer_id = (data.get('existing_customer_id') or '').strip()

        existing_customer = None

        if existing_customer_id:

            try:

                existing_customer = CustomerDetail.objects.select_related('address').get(customer_id=existing_customer_id)

            except CustomerDetail.DoesNotExist:

                errors['existing_customer_id'] = 'Customer not found.'



        existing_docs = None

        if use_existing_documents:

            if existing_customer is None:

                errors['use_existing_documents'] = 'Please fetch/select an existing customer to use existing documents.'

            else:

                if getattr(existing_customer, 'loan_application_id', None):

                    existing_docs = CustomerDocument.objects.filter(loan_application=existing_customer.loan_application).first()

                if existing_docs is None:

                    latest_savings_app = (

                        SavingsAccountApplication.objects

                        .filter(customer=existing_customer)

                        .order_by('-submitted_at')

                        .first()

                    )

                    if latest_savings_app is not None:

                        existing_docs = CustomerDocument.objects.filter(savings_application=latest_savings_app).first()

                if existing_docs is None:

                    errors['use_existing_documents'] = 'No existing documents found for this customer.'



        if use_existing_documents and existing_docs is not None:

            for f in required_file_fields:

                if not getattr(existing_docs, f, None):

                    errors[f] = 'Existing documents are missing this required file. Please upload it.'



        adhar_number = data.get('adhar_number')

        pan_number = data.get('pan_number')

        if not existing_customer_id:

            if adhar_number and CustomerDetail.objects.filter(adhar_number=adhar_number).exists():

                errors['adhar_number'] = 'A customer with this Adhar Number already exists.'

            if pan_number and CustomerDetail.objects.filter(pan_number=pan_number).exists():

                errors['pan_number'] = 'A customer with this PAN Number already exists.'



        agent_id = request.session.get('agent_id')

        if not agent_id:

            return Response({'success': False, 'message': 'Authentication required.'}, status=400)



        try:

            agent = Agent.objects.get(agent_id=agent_id)

        except Agent.DoesNotExist:

            return Response({'success': False, 'message': 'Agent not found.'}, status=400)



        if errors:

            return Response({'success': False, 'errors': errors}, status=400)



        nominee_name = (data.get('nominee_name') or '').strip()

        nominee_relationship = (data.get('nominee_relationship') or '').strip()

        nominee_kyc_type = (data.get('nominee_kyc_type') or '').strip()

        nominee_kyc_number = (data.get('nominee_kyc_number') or '').strip()

        nominee_kyc_document = files.get('nominee_kyc_document')



        if not nominee_name:

            errors['nominee_name'] = 'This field is required.'

        if not nominee_relationship:

            errors['nominee_relationship'] = 'This field is required.'

        if nominee_kyc_type and nominee_kyc_type not in ('aadhaar', 'pan'):

            errors['nominee_kyc_type'] = 'Please select Aadhaar or PAN.'

        if nominee_kyc_number:

            if not nominee_kyc_type:

                errors['nominee_kyc_type'] = 'Please select Aadhaar or PAN.'

            elif nominee_kyc_type == 'aadhaar':

                clean_value = nominee_kyc_number.replace(' ', '')
                if not clean_value.isdigit() or len(clean_value) != 12:
                    errors['nominee_kyc_number'] = 'Nominee Aadhaar number must be exactly 12 digits.'

            elif nominee_kyc_type == 'pan':

                import re
                pan_value = nominee_kyc_number.upper()
                if not re.match(r'^[A-Z]{5}\d{4}[A-Z]$', pan_value):
                    errors['nominee_kyc_number'] = 'Nominee PAN number must be 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).'



        if errors:

            return Response({'success': False, 'errors': errors}, status=400)



        branch = agent.branch



        payment_mode = (data.get('payment_mode') or 'cash').strip()

        receipt_no = (data.get('receipt_no') or '').strip() or None

        note = (data.get('note') or '').strip() or None



        with transaction.atomic():

            if existing_customer:

                customer = existing_customer

            else:

                customer = CustomerDetail.objects.create(

                    full_name=data['full_name'],

                    father_name=data.get('father_name'),

                    date_of_birth=data['date_of_birth'],

                    gender=data['gender'],

                    contact=data['contact'],

                    email=data.get('email'),

                    adhar_number=data['adhar_number'],

                    pan_number=str(data['pan_number']).upper(),

                    agent=agent,

                    branch=branch,

                    loan_application=None,

                )



            CustomerAddress.objects.update_or_create(

                customer=customer,

                defaults={

                    'loan_application': None,

                    'address_line_1': data['address_line_1'],

                    'address_line_2': data.get('address_line_2'),

                    'landmark': data.get('landmark'),

                    'post_office': data.get('post_office'),

                    'city_or_town': data.get('city_or_town') or 'N/A',

                    'district': data.get('district') or 'N/A',

                    'state': data['state'],

                    'country': data.get('country', 'India'),

                    'post_code': post_code,

                    'current_address_line_1': data.get('current_address_line_1') or data['address_line_1'],

                    'current_address_line_2': data.get('current_address_line_2') or data.get('address_line_2'),

                    'current_landmark': data.get('current_landmark') or data.get('landmark'),

                    'current_post_office': data.get('current_post_office') or data.get('post_office'),

                    'current_city_or_town': data.get('current_city_or_town') or (data.get('city_or_town') or 'N/A'),

                    'current_district': data.get('current_district') or (data.get('district') or 'N/A'),

                    'current_state': data.get('current_state') or data['state'],

                    'current_country': data.get('current_country') or data.get('country', 'India'),

                    'current_post_code': (data.get('current_post_code') or post_code),

                    'residential_proof_type': data.get('residential_proof_type'),

                    'agent': agent,

                    'branch': branch,

                }

            )



            savings_app = SavingsAccountApplication.objects.create(

                customer=customer,

                product_type=product_type,

                product_id=product_id,

                installment_amount=installment_amount_decimal,

                interest_rate=interest_rate_decimal,

                tenure=tenure,

                status='pending',

                nominee_name=nominee_name or None,

                nominee_relationship=nominee_relationship or None,

                nominee_kyc_type=nominee_kyc_type or None,

                nominee_kyc_number=nominee_kyc_number or None,

                nominee_kyc_document=nominee_kyc_document,

                agent=agent,

                branch=branch,

            )



            if product_type == 'fd':

                branch_employee = (

                    BranchEmployee.objects

                    .filter(branch=branch, is_active=True)

                    .order_by('-is_manager', 'id')

                    .first()

                )

                if branch_employee is None:

                    return Response(

                        {'success': False, 'errors': {'payment': 'No active branch employee found to record FD deposit transaction.'}},

                        status=400,

                    )



                account_type = 'CASH' if payment_mode == 'cash' else 'BANK'

                branch_account = (

                    BranchAccount.objects

                    .select_for_update()

                    .filter(branch=branch, type=account_type)

                    .order_by('-updated_at', '-created_at')

                    .first()

                )

                if branch_account is None:

                    return Response(

                        {'success': False, 'errors': {'payment': f"No branch {account_type} account found to credit this FD deposit."}},

                        status=400,

                    )



                fd_amount = Decimal(str(installment_amount_decimal)).quantize(Decimal('0.01'))

                # branch_account.current_balance = (Decimal(branch_account.current_balance) + fd_amount).quantize(Decimal('0.01'))

                # branch_account.updated_by = branch_employee

                # branch_account.save(update_fields=['current_balance', 'updated_by', 'updated_at'])



                deposit_collection = SavingsCollection.objects.create(
                    account=savings_app,
                    collection_type='fd_deposit',
                    amount=fd_amount,
                    collection_date=timezone.now().date(),
                    receipt_no=receipt_no,
                    payment_mode=payment_mode,
                    note=note,
                    branch=branch,
                    agent=agent,
                    collected_by_agent=agent,
                    is_expected=False,
                    is_collected=True,
                )



                # BranchTransaction.objects.create(

                #     branch=branch,

                #     branch_account=branch_account,

                #     disbursement_log=None,

                #     transaction_type='CREDIT',

                #     purpose="Savings FD Deposit (Application)",

                #     code='204',

                #     mode=payment_mode,

                #     bank_payment_method=payment_mode if payment_mode in ['upi', 'bank'] else None,

                #     amount=fd_amount,

                #     transfer_to_from=None,

                #     description=f"FD deposit for {savings_app.application_id} ({deposit_collection.collection_id})",

                #     created_by=branch_employee,

                # )



            CustomerDocument.objects.create(

                loan_application=None,

                savings_application=savings_app,

                id_proof=(existing_docs.id_proof if use_existing_documents and existing_docs else files.get('id_proof')),

                pan_card_document=(existing_docs.pan_card_document if use_existing_documents and existing_docs else files.get('pan_card_document')),

                id_proof_back=(existing_docs.id_proof_back if use_existing_documents and existing_docs else files.get('id_proof_back')),

                income_proof=(existing_docs.income_proof if use_existing_documents and existing_docs else files.get('income_proof')),

                photo=(existing_docs.photo if use_existing_documents and existing_docs else files.get('photo')),

                signature=(existing_docs.signature if use_existing_documents and existing_docs else files.get('signature')),

                collateral=(existing_docs.collateral if use_existing_documents and existing_docs else files.get('collateral')),

                residential_proof_file=(existing_docs.residential_proof_file if use_existing_documents and existing_docs else files.get('residential_proof_file')),

                agent=agent,

                branch=branch,

            )



        def _enqueue_email():
            t = threading.Thread(
                target=_send_savings_application_email_in_background,
                args=(savings_app.application_id,),
                daemon=True,
            )
            t.start()

        transaction.on_commit(_enqueue_email)

        pdf_url = f"/agent/savings/api/application/{savings_app.application_id}/pdf/"

        return Response({
            'success': True,
            'message': 'Savings application submitted successfully',
            'customer_id': customer.customer_id,
            'application_id': savings_app.application_id,
            'pdf_url': pdf_url,
        })





class BranchNewSavingsApplicationAPI(APIView):

    parser_classes = (MultiPartParser, FormParser)

    def _generate_pdf_for_email(self, html_content):
        """Generate PDF for email attachment using Playwright"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._generate_pdf_async(html_content))
        finally:
            loop.close()

    async def _generate_pdf_async(self, html_content):
        """Generate PDF from HTML content using Playwright"""
        browser = None
        try:
            async with async_playwright() as p:
                try:
                    browser = await p.chromium.launch(headless=True)
                except Exception:
                    await self._install_playwright_chromium_for_email()
                    browser = await p.chromium.launch(headless=True)

                page = await browser.new_page()
                page.set_default_timeout(30000)
                await page.set_content(html_content, wait_until='domcontentloaded')
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
        finally:
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass

    async def _install_playwright_chromium_for_email(self):
        """Install Playwright Chromium browser if missing. Runs once when needed."""
        cmd = [sys.executable, '-m', 'playwright', 'install', 'chromium']

        def _run():
            return subprocess.run(cmd, check=True, capture_output=True)

        await asyncio.to_thread(_run)



    @method_decorator(csrf_exempt)

    @method_decorator(branch_permission_required())

    def post(self, request, *args, **kwargs):

        data = request.data

        files = request.FILES



        required_fields = [

            'full_name', 'date_of_birth', 'gender', 'contact', 'adhar_number',

            'address_line_1', 'state', 'post_code',

            'product_type', 'product_id',

        ]

        # required_file_fields = ['id_proof', 'pan_card_document', 'photo', 'signature']
        required_file_fields = ['id_proof']



        errors = {}

        for f in required_fields:

            if not data.get(f):

                errors[f] = 'This field is required.'

        use_existing_documents = str(data.get('use_existing_documents') or '').strip().lower() in ('1', 'true', 'yes', 'on')



        for f in required_file_fields:

            if not use_existing_documents and not files.get(f):

                errors[f] = 'This file is required.'



        product_type = (data.get('product_type') or '').strip().lower()

        if product_type not in ('fd', 'rd'):

            errors['product_type'] = 'Invalid product type.'



        product_id = (data.get('product_id') or '').strip()

        selected_product = None

        if not product_id:

            errors['product_id'] = 'This field is required.'

        else:

            try:

                if product_type == 'fd':

                    selected_product = OneTimeDeposit.objects.get(one_time_deposit_id=product_id, is_active=True)

                elif product_type == 'rd':

                    selected_product = DailyProduct.objects.get(daily_product_id=product_id, is_active=True)

            except (OneTimeDeposit.DoesNotExist, DailyProduct.DoesNotExist):

                errors['product_id'] = 'Selected product not found.'



        installment_amount_decimal = None

        interest_rate_decimal = None

        tenure = None



        if selected_product is not None:

            installment_amount_decimal = selected_product.deposit_amount

            if product_type == 'fd':

                interest_rate_decimal = None

            else:

                interest_rate_decimal = selected_product.interest_rate

            tenure = int(selected_product.tenure)



        post_code = (data.get('post_code') or '').strip()

        if post_code and not (post_code.isdigit() and len(post_code) == 6):

            errors['post_code'] = 'Post code must be exactly 6 digits.'



        existing_customer_id = (data.get('existing_customer_id') or '').strip()

        existing_customer = None

        if existing_customer_id:

            try:

                existing_customer = CustomerDetail.objects.select_related('address').get(customer_id=existing_customer_id)

            except CustomerDetail.DoesNotExist:

                errors['existing_customer_id'] = 'Customer not found.'



        existing_docs = None

        if use_existing_documents:

            if existing_customer is None:

                errors['use_existing_documents'] = 'Please fetch/select an existing customer to use existing documents.'

            else:

                if getattr(existing_customer, 'loan_application_id', None):

                    existing_docs = CustomerDocument.objects.filter(loan_application=existing_customer.loan_application).first()

                if existing_docs is None:

                    latest_savings_app = (

                        SavingsAccountApplication.objects

                        .filter(customer=existing_customer)

                        .order_by('-submitted_at')

                        .first()

                    )

                    if latest_savings_app is not None:

                        existing_docs = CustomerDocument.objects.filter(savings_application=latest_savings_app).first()

                if existing_docs is None:

                    errors['use_existing_documents'] = 'No existing documents found for this customer.'



        if use_existing_documents and existing_docs is not None:

            for f in required_file_fields:

                if not getattr(existing_docs, f, None):

                    errors[f] = 'Existing documents are missing this required file. Please upload it.'



        adhar_number = data.get('adhar_number')

        pan_number = data.get('pan_number')

        if not existing_customer_id:

            if adhar_number and CustomerDetail.objects.filter(adhar_number=adhar_number).exists():

                errors['adhar_number'] = 'A customer with this Adhar Number already exists.'

            if pan_number and CustomerDetail.objects.filter(pan_number=pan_number).exists():

                errors['pan_number'] = 'A customer with this PAN Number already exists.'



        logged_user_id = request.session.get('logged_user_id')

        if not logged_user_id:

            return Response({'success': False, 'message': 'Authentication required.'}, status=400)



        try:

            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)

        except BranchEmployee.DoesNotExist:

            return Response({'success': False, 'message': 'Branch user not found.'}, status=400)



        branch = branch_employee.branch



        if errors:

            return Response({'success': False, 'errors': errors}, status=400)



        nominee_name = (data.get('nominee_name') or '').strip()

        nominee_relationship = (data.get('nominee_relationship') or '').strip()

        nominee_kyc_type = (data.get('nominee_kyc_type') or '').strip()

        nominee_kyc_number = (data.get('nominee_kyc_number') or '').strip()

        nominee_kyc_document = files.get('nominee_kyc_document')



        if not nominee_name:

            errors['nominee_name'] = 'This field is required.'

        if not nominee_relationship:

            errors['nominee_relationship'] = 'This field is required.'

        if nominee_kyc_type and nominee_kyc_type not in ('aadhaar', 'pan'):

            errors['nominee_kyc_type'] = 'Please select Aadhaar or PAN.'

        if nominee_kyc_number:

            if not nominee_kyc_type:

                errors['nominee_kyc_type'] = 'Please select Aadhaar or PAN.'

            elif nominee_kyc_type == 'aadhaar':

                clean_value = nominee_kyc_number.replace(' ', '')
                if not clean_value.isdigit() or len(clean_value) != 12:
                    errors['nominee_kyc_number'] = 'Nominee Aadhaar number must be exactly 12 digits.'

            elif nominee_kyc_type == 'pan':

                pan_value = nominee_kyc_number.upper()
                if not re.match(r'^[A-Z]{5}\d{4}[A-Z]$', pan_value):
                    errors['nominee_kyc_number'] = 'Nominee PAN number must be 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F).'



        if errors:

            return Response({'success': False, 'errors': errors}, status=400)



        with transaction.atomic():

            if existing_customer:

                customer = existing_customer

            else:

                customer = CustomerDetail.objects.create(

                    full_name=data['full_name'],

                    father_name=data.get('father_name'),

                    date_of_birth=data['date_of_birth'],

                    gender=data['gender'],

                    contact=data['contact'],

                    email=data.get('email'),

                    adhar_number=data['adhar_number'],

                    pan_number=str(data['pan_number']).upper(),

                    agent=None,

                    branch=branch,

                    loan_application=None,

                )



            CustomerAddress.objects.update_or_create(

                customer=customer,

                defaults={

                    'loan_application': None,

                    'address_line_1': data['address_line_1'],

                    'address_line_2': data.get('address_line_2'),

                    'landmark': data.get('landmark'),

                    'post_office': data.get('post_office'),

                    'city_or_town': data.get('city_or_town') or 'N/A',

                    'district': data.get('district') or 'N/A',

                    'state': data['state'],

                    'country': data.get('country', 'India'),

                    'post_code': post_code,

                    'current_address_line_1': data.get('current_address_line_1') or data['address_line_1'],

                    'current_address_line_2': data.get('current_address_line_2') or data.get('address_line_2'),

                    'current_landmark': data.get('current_landmark') or data.get('landmark'),

                    'current_post_office': data.get('current_post_office') or data.get('post_office'),

                    'current_city_or_town': data.get('current_city_or_town') or (data.get('city_or_town') or 'N/A'),

                    'current_district': data.get('current_district') or (data.get('district') or 'N/A'),

                    'current_state': data.get('current_state') or data['state'],

                    'current_country': data.get('current_country') or data.get('country', 'India'),

                    'current_post_code': (data.get('current_post_code') or post_code),

                    'residential_proof_type': data.get('residential_proof_type'),

                    'agent': None,

                    'branch': branch,

                }

            )



            savings_app = SavingsAccountApplication.objects.create(

                customer=customer,

                product_type=product_type,

                product_id=product_id,

                installment_amount=installment_amount_decimal,

                interest_rate=interest_rate_decimal,

                tenure=tenure,

                status='pending',

                nominee_name=nominee_name or None,

                nominee_relationship=nominee_relationship or None,

                nominee_kyc_type=nominee_kyc_type or None,

                nominee_kyc_number=nominee_kyc_number or None,

                nominee_kyc_document=nominee_kyc_document,

                agent=None,

                branch=branch,

            )



            if product_type == 'fd':

                payment_mode = (data.get('payment_mode') or 'cash').strip()

                receipt_no = (data.get('receipt_no') or '').strip() or None

                note = (data.get('note') or '').strip() or None



                account_type = 'CASH' if payment_mode == 'cash' else 'BANK'

                branch_account = (

                    BranchAccount.objects

                    .select_for_update()

                    .filter(branch=branch, type=account_type)

                    .order_by('-updated_at', '-created_at')

                    .first()

                )

                if branch_account is None:

                    return Response(

                        {'success': False, 'errors': {'payment': f"No branch {account_type} account found to credit this FD deposit."}},

                        status=400,

                    )



                fd_amount = Decimal(str(installment_amount_decimal)).quantize(Decimal('0.01'))

                branch_account.current_balance = (Decimal(branch_account.current_balance) + fd_amount).quantize(Decimal('0.01'))

                branch_account.updated_by = branch_employee

                branch_account.save(update_fields=['current_balance', 'updated_by', 'updated_at'])



                deposit_collection = SavingsCollection.objects.create(

                    account=savings_app,

                    collection_type='fd_deposit',

                    amount=fd_amount,

                    collection_date=timezone.now().date(),

                    receipt_no=receipt_no,

                    payment_mode=payment_mode,

                    note=note,

                    branch=branch,

                    collected_by_branch_employee=branch_employee,

                    is_expected=False,

                    is_collected=True,

                )



                BranchTransaction.objects.create(

                    branch=branch,

                    branch_account=branch_account,

                    disbursement_log=None,

                    transaction_type='CREDIT',

                    purpose="Savings FD Deposit (Application)",

                    code='204',

                    mode=payment_mode,

                    bank_payment_method=payment_mode if payment_mode in ['upi', 'bank'] else None,

                    amount=fd_amount,

                    transfer_to_from=None,

                    description=f"FD deposit for {savings_app.application_id} ({deposit_collection.collection_id})",

                    created_by=branch_employee,

                )



            CustomerDocument.objects.create(

                loan_application=None,

                savings_application=savings_app,

                id_proof=(existing_docs.id_proof if use_existing_documents and existing_docs else files.get('id_proof')),

                pan_card_document=(existing_docs.pan_card_document if use_existing_documents and existing_docs else files.get('pan_card_document')),

                id_proof_back=(existing_docs.id_proof_back if use_existing_documents and existing_docs else files.get('id_proof_back')),

                income_proof=(existing_docs.income_proof if use_existing_documents and existing_docs else files.get('income_proof')),

                photo=(existing_docs.photo if use_existing_documents and existing_docs else files.get('photo')),

                signature=(existing_docs.signature if use_existing_documents and existing_docs else files.get('signature')),

                collateral=(existing_docs.collateral if use_existing_documents and existing_docs else files.get('collateral')),

                residential_proof_file=(existing_docs.residential_proof_file if use_existing_documents and existing_docs else files.get('residential_proof_file')),

                agent=None,

                branch=branch,

            )



        def _enqueue_email():
            t = threading.Thread(
                target=_send_savings_application_email_in_background,
                args=(savings_app.application_id,),
                daemon=True,
            )
            t.start()

        transaction.on_commit(_enqueue_email)

        pdf_url = f"/branch/savings/api/application/{savings_app.application_id}/pdf/"

        return Response({
            'success': True,
            'message': 'Savings application submitted successfully',
            'customer_id': customer.customer_id,
            'application_id': savings_app.application_id,
            'pdf_url': pdf_url,
        })


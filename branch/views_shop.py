from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.generic import TemplateView
from rest_framework.views import APIView
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from loan.models import Shop, ShopBankAccount, LoanApplication
from branch.models import BranchTransaction
from agent.models import Agent
from branch.models import BranchEmployee
import logging

logger = logging.getLogger(__name__)


class BranchSessionRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)
        except BranchEmployee.DoesNotExist:
            request.session.flush()
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        branch = getattr(branch_employee, 'branch', None)
        if branch is not None and not getattr(branch, 'status', True):
            request.session.flush()
            login_url = reverse('branch:branch_login_page')
            return redirect(f"{login_url}?next={request.path}")

        request.branch_employee = branch_employee
        request.branch_manager = branch_employee
        return super().dispatch(request, *args, **kwargs)


class BranchShopView(BranchSessionRequiredMixin, TemplateView):
    template_name = 'branch/shop/shop.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        logged_user_id = self.request.session.get('logged_user_id')
        if not logged_user_id:
            context['shops'] = []
            context['categories'] = []
            context['show_active'] = True
            return context

        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)
        except BranchEmployee.DoesNotExist:
            context['shops'] = []
            context['categories'] = []
            context['show_active'] = True
            return context

        branch = branch_employee.branch

        show_active = self.request.GET.get('show_active', 'true') == 'true'
        base_qs = Shop.objects.filter(agent__isnull=False, agent__branch=branch)
        if show_active:
            shops_qs = base_qs.exclude(status='inactive').order_by('-created_at')
        else:
            shops_qs = base_qs.filter(status='inactive').order_by('-created_at')

        context['shops'] = shops_qs
        context['show_active'] = show_active
        categories = list(
            shops_qs.values_list('category', flat=True)
            .distinct()
            .exclude(category__isnull=True)
            .exclude(category='')
        )
        context['categories'] = categories
        return context

class BranchShopDetailView(BranchSessionRequiredMixin, TemplateView):
    template_name = 'branch/shop/shop_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shop_id = kwargs.get('shop_id')
        
        if not shop_id:
            context['error'] = 'Shop ID is required'
            return context
            
        # Get the shop and verify it belongs to this branch
        logged_user_id = self.request.session.get('logged_user_id')
        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)
            branch = branch_employee.branch
        except BranchEmployee.DoesNotExist:
            context['error'] = 'Authentication failed'
            return context
            
        shop = get_object_or_404(Shop, shop_id=shop_id, agent__branch=branch)
        
        # Get shop details
        context['shop'] = shop
        context['bank_accounts'] = ShopBankAccount.objects.filter(shop=shop)
        
        # Get transactions related to this shop
        context['transactions'] = BranchTransaction.objects.filter(
            disbursement_log__loan_id__shop=shop
        ).order_by('-transaction_date')[:20]  # Last 20 transactions
        
        # Get loans related to this shop
        context['loans'] = LoanApplication.objects.filter(
            shop=shop
        ).order_by('-submitted_at')[:20]  # Last 20 loans
        
        return context


class BranchShopBankAccountAPI(BranchSessionRequiredMixin, APIView):
    @method_decorator(csrf_exempt)
    def get(self, request, *args, **kwargs):
        shop_id = (request.GET.get('shop_id') or '').strip()
        if not shop_id:
            return Response({'success': False, 'message': 'Shop ID is required.'}, status=400)

        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'success': False, 'message': 'Authentication required.'}, status=401)

        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)
        except BranchEmployee.DoesNotExist:
            return Response({'success': False, 'message': 'Branch manager not found.'}, status=404)

        try:
            shop = Shop.objects.get(
                shop_id=shop_id,
                agent__isnull=False,
                agent__branch=branch_employee.branch,
            )
        except Shop.DoesNotExist:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)

        if shop.agent_id is None:
            return Response({'success': False, 'message': 'Shop not found.'}, status=404)

        accounts = ShopBankAccount.objects.filter(shop=shop).order_by('-created_at')
        payload = []
        for a in accounts:
            payload.append({
                'bank_account_id': a.bank_account_id,
                'account_holder_name': a.account_holder_name,
                'bank_name': a.bank_name,
                'account_number': a.account_number,
                'ifsc_code': a.ifsc_code,
                'created_at': a.created_at.isoformat() if a.created_at else None,
            })

        return Response({'success': True, 'bank_accounts': payload, 'shop_name': shop.name}, status=200)

    @method_decorator(csrf_exempt)
    def post(self, request, *args, **kwargs):
        return Response({'success': False, 'message': 'Method not allowed.'}, status=405)

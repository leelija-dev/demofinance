from django.db.models import manager, Q, OuterRef, Subquery
from django.http import response
from django.http import HttpResponse, HttpResponseForbidden
from django.utils.timezone import make_aware
from datetime import datetime
from django.shortcuts import render
from django.views import View
from rest_framework.views import APIView
from django.views.generic import ListView
from rest_framework.response import Response
from rest_framework import status
from headquater.models import Branch
from branch.models import BranchEmployee
from agent.models import Agent
from loan.models import ( CustomerDetail, CustomerAddress, CustomerLoanDetail, CustomerDocument, DocumentRequest, 
 LoanCategory, LoanInterest, DocumentReupload, LoanApplication, LoanPeriod, LoanTenure, EmiAgentAssign, EmiCollectionDetail, LoanEMISchedule,
 LoanCloseRequest, CustomerAccount, LoanApplicationDraft
)
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
from zoneinfo import ZoneInfo

# for PDF generation
import asyncio
from playwright.async_api import async_playwright
import subprocess
import sys
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from main.pagination import AgentPagination

class AssignedEmiListAPIView(APIView):

    pagination_class = AgentPagination

    def get(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response({'detail': 'Agent authentication required.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            agent = Agent.objects.select_related('branch').get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'detail': 'Agent not found.'}, status=status.HTTP_403_FORBIDDEN)

        # Get filter parameters from query params
        status_filter = request.query_params.get('status')
        
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        search = request.query_params.get('search')

        # Base query
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

        qs = qs.exclude(
            Q(emi__loan_application__close_requests__status__in=['pending', 'approved'])
            | Q(reschedule_emi__loan_application__close_requests__status__in=['pending', 'approved'])
        ).distinct()

        # Apply status filter if provided
        if status_filter and status_filter != 'all':
            if status_filter.lower() == 'pending':
                # For pending, get records that are neither 'collected' nor 'verified'
                qs = qs.exclude(
                    Q(collections__status='collected') | 
                    Q(collections__status='verified')
                )
            else:
                # For other statuses, filter by the exact status
                qs = qs.filter(collections__status=status_filter)

        # Apply date range filter if provided
        if date_from and date_to:
            try:
                # Make timezone aware
                date_from = make_aware(datetime.strptime(date_from, '%Y-%m-%d'))
                date_to = make_aware(datetime.strptime(date_to, '%Y-%m-%d')).replace(hour=23, minute=59, second=59, microsecond=999999)
                
                # Filter by assignment date
                qs = qs.filter(
                    Q(installment_date__range=(date_from, date_to))
                ).distinct()
                
            except ValueError as e:
                return Response(
                    {
                        'success': False,
                        'message': 'Invalid date format. Use "DD MMM YYYY" (e.g., 14 Nov 2025) or "YYYY-MM-DD".',
                        'error': 'invalid_date_format',
                        'status_code': status.HTTP_400_BAD_REQUEST
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Apply search filter if provided
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

        # Apply pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)

        # Build response
        results = []
        for a in page:
            # For each assignment, prefer the original EMI and fall back to the
            # rescheduled EMI so that both types share the same response shape.
            emi_obj = getattr(a, 'emi', None) or getattr(a, 'reschedule_emi', None)
            loan_app = getattr(emi_obj, 'loan_application', None) if emi_obj else None
            customer = getattr(loan_app, 'customer', None) if loan_app else None
            branch = getattr(loan_app, 'branch', None) if loan_app else None

            results.append({
                'assignment_id': a.assignment_id,
                'loan_ref_no': getattr(loan_app, 'loan_ref_no', None) if loan_app else None,
                'customer_name': getattr(customer, 'full_name', None) if customer else None,
                'branch_name': getattr(branch, 'branch_name', None) if branch else None,
                'emi_amount': float(a.installment_amount) if a.installment_amount is not None else 0.0,
                'principal_amount': float(a.principal_amount) if a.principal_amount is not None else 0.0,
                'interest_amount': float(a.interest_amount) if a.interest_amount is not None else 0.0,
                'installment_date': a.installment_date.strftime("%d-%m-%Y") if a.installment_date else None,
                'collected_at': a.collected_at.strftime("%d-%m-%Y") if a.collected_at else None,
                'status': getattr(a, 'latest_status', None) or 'pending',
            })

        return paginator.get_paginated_response(results)


class OverdueEmiList(APIView):
    """
    API endpoint that returns a list of overdue EMIs for the logged-in agent.
    """
    def get(self, request, format=None):
        agent_id = request.session.get('agent_id')
        if not agent_id:
            return Response(
                {'error': 'Agent not authenticated'}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        today = timezone.now().date()
        
        # Get the agent's assignments with basic EMI info for both
        # original schedules and rescheduled EMIs.
        overdue_assignments = (
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
            .exclude(
                Q(emi__loan_application__close_requests__status__in=['pending', 'approved'])
                | Q(reschedule_emi__loan_application__close_requests__status__in=['pending', 'approved'])
            )
            .order_by('installment_date')
        )

        # Prepare the response data; for each assignment prefer the
        # original EMI and fall back to the rescheduled EMI so the
        # frontend receives a uniform shape regardless of type.
        data = []
        for assignment in overdue_assignments:
            emi_obj = getattr(assignment, 'emi', None) or getattr(assignment, 'reschedule_emi', None)
            if not emi_obj:
                continue

            loan_app = getattr(emi_obj, 'loan_application', None)
            if not loan_app:
                continue

            customer = getattr(loan_app, 'customer', None)
            # Prefer the customer.branch if present; otherwise fall back to
            # loan_application.branch when available.
            branch = getattr(customer, 'branch', None) or getattr(loan_app, 'branch', None)

            # Flag whether this assignment points to a rescheduled EMI so the
            # frontend can decide which late-fee API to call and how to
            # display penalty input behavior.
            is_reschedule = bool(getattr(assignment, 'reschedule_emi_id', None))

            data.append({
                'loan_id': getattr(loan_app, 'loan_ref_no', None),
                'branch': getattr(branch, 'branch_name', None) if branch else None,
                'customer_id': getattr(customer, 'customer_id', None) if customer else None,
                'customer_name': (getattr(customer, 'full_name', '') or 'N/A') if customer else 'N/A',
                'assignment_id': assignment.assignment_id,
                # Use the underlying schedule / reschedule EMI id so
                # later APIs (late-fee, collection, etc.) can resolve it.
                'emi_id': getattr(emi_obj, 'id', None),
                'is_reschedule': 1 if is_reschedule else 0,
                'due_date': assignment.installment_date,
                'installment_amount': assignment.installment_amount,
                'principal_amount': assignment.principal_amount,
                'interest_amount': assignment.interest_amount,
                'assigned_date': assignment.assigned_at.strftime('%d-%m-%Y : %H:%M') if assignment.assigned_at else None,
                'is_active': assignment.is_active,
                'days_overdue': (today - getattr(emi_obj, 'installment_date', today)).days,
            })

        return Response({
            'status': 'success',
            'count': len(data),
            'today': today,
            'results': data
        }, status=status.HTTP_200_OK)
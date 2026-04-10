from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from agent.models import Agent
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import AgentSerializer
from loan.models import LoanApplication, EmiCollectionDetail, LoanEMISchedule, EmiAgentAssign, LoanEMIReschedule
from branch.models import BranchEmployee, BranchAccount
from rest_framework.parsers import MultiPartParser, FormParser
from .decorators import branch_permission_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from datetime import timedelta, datetime, time
from django.db.models import Q, Sum, Count
from django.db.models import F

from savings.models import SavingsCollection, SavingsAgentAssign


##### for agent ####
@method_decorator(branch_permission_required('view_agent', 'view_emis', 'collect_emi', 'receive_emi', 'reject_emi'), name='dispatch')
class AgentListView(TemplateView):
    template_name = 'agent/agent.html'

@method_decorator(branch_permission_required('add_agent'), name='dispatch')
class AgentCreateView(TemplateView):
    template_name = 'agent/agent_create.html'

@method_decorator(branch_permission_required('change_agent'), name='dispatch')
class AgentEditView(TemplateView):
    template_name = 'agent/agent_edit.html'

@method_decorator(branch_permission_required('view_agent'), name='dispatch')
class AgentOverviewView(TemplateView):
    template_name = 'agent/agent_overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent_id = kwargs.get('agent_id')

        logged_user_id = self.request.session.get('logged_user_id')
        if not logged_user_id:
            context.update({
                'agent': None,
                'performance': None,
                'portfolio': None,
                'collections': None,
                'delinquency': None,
            })
            return context

        try:
            branch_employee = BranchEmployee.objects.get(id=logged_user_id)
        except BranchEmployee.DoesNotExist:
            context.update({
                'agent': None,
                'performance': None,
                'portfolio': None,
                'collections': None,
                'delinquency': None,
            })
            return context

        # Fetch agent scoped to manager's branch
        try:
            agent = Agent.objects.get(agent_id=agent_id, branch=branch_employee.branch)
        except Agent.DoesNotExist:
            context.update({
                'agent': None,
                'performance': None,
                'portfolio': None,
                'collections': None,
                'delinquency': None,
            })
            return context
        context['agent'] = agent

        # Provide branch bank accounts for online deposit selection
        try:
            context['branch_accounts'] = BranchAccount.objects.filter(branch=branch_employee.branch, type='BANK').only('id','bank_name','account_number')
        except Exception:
            context['branch_accounts'] = []

        # Unverified collected amount (collected, not yet verified)
        unverified_total = EmiCollectionDetail.objects.filter(
            collected_by_agent=agent,
            collected=True,
            status__in=['collected']
        ).aggregate(total=Sum('amount_received') + Sum('penalty_received'))['total'] or 0

        savings_unverified_total = SavingsCollection.objects.filter(
            collected_by_agent=agent,
            is_collected=True,
            is_deposited_to_branch=False,
            collection_type__in=['rd_installment', 'fd_deposit'],
        ).aggregate(total=Sum('amount'))['total'] or 0

        unverified_total = (unverified_total or 0) + (savings_unverified_total or 0)
        context['unverified_collected_amount'] = unverified_total

        now = timezone.now()
        today = timezone.localdate()
        thirty_days_ago = now - timedelta(days=30)

        # Get filter parameter (default to 30 days)
        filter_param = self.request.GET.get('filter', '30d')
        if filter_param == '60d':
            days_ago = now - timedelta(days=60)
        elif filter_param == 'all':
            days_ago = None
        elif filter_param == 'custom':
            # For custom filter, clear previous dates and only use newly provided dates
            days_ago = None
            # Clear previous date selections when custom is selected
            start_date_str = None
            end_date_str = None
        else:
            days_ago = thirty_days_ago

        # Get custom date range (only if custom filter is selected and dates are provided)
        if filter_param == 'custom':
            start_date_str = self.request.GET.get('start_date')
            end_date_str = self.request.GET.get('end_date')
        else:
            # For non-custom filters, don't use custom dates
            start_date_str = None
            end_date_str = None

        start_date = None
        end_date = None
        if start_date_str and end_date_str:
            try:
                start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone())
                end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').replace(tzinfo=timezone.get_current_timezone()).replace(hour=23, minute=59, second=59)
            except ValueError:
                pass

        # Recent applied loans for this agent (for Recent Activity table)
        recent_loans = LoanApplication.objects.filter(
            agent=agent,
            branch=branch_employee.branch,
        ).order_by('-submitted_at')[:5].values(
            id=F('loan_ref_no'),
            customer_name=F('customer__full_name'),
            loan_amount=F('loan_details__loan_amount'),
            date=F('submitted_at'),
        )
        context['recent_loans'] = recent_loans

        # Portfolio metrics
        # Total loans within the filter period
        total_loans_query = LoanApplication.objects.filter(agent=agent)
        if filter_param == '60d':
            total_loans_query = total_loans_query.filter(submitted_at__gte=now - timedelta(days=60))
        elif filter_param == 'custom' and start_date and end_date:
            total_loans_query = total_loans_query.filter(submitted_at__gte=start_date, submitted_at__lte=end_date)
        else:
            total_loans_query = total_loans_query.filter(submitted_at__gte=thirty_days_ago)
        
        total_loans = total_loans_query.count()
        
        # Active loans (all time, since active status is current)
        active_loans = LoanApplication.objects.filter(
            agent=agent,
            status__in=['approved', 'disbursed', 'branch_approved', 'hq_approved']
        ).count()
        
        # New applications within filter period (same as total loans for now)
        new_apps_count = total_loans

        portfolio = {
            'total_loans': total_loans,
            'active_loans': active_loans,
            'new_apps_30d': new_apps_count,
        }
        context['portfolio'] = portfolio

        # Collections metrics (filter by days_ago if not all or custom)
        # Total collections (all time)
        all_collections = EmiCollectionDetail.objects.filter(
            collected_by_agent=agent,
            collected=True,
        )
        total_collections_count = all_collections.count()
        total_collections_amount = all_collections.aggregate(
            total_amount=Sum('amount_received') + Sum('penalty_received')
        )['total_amount'] or 0
        
        # Filtered collections for period metrics
        collections_total = EmiCollectionDetail.objects.filter(
            collected_by_agent=agent,
            collected=True,
        )
        if days_ago:
            collections_total = collections_total.filter(collected_at__gte=days_ago)
        if start_date and end_date:
            collections_total = collections_total.filter(collected_at__gte=start_date, collected_at__lte=end_date)

        savings_all_collections = SavingsCollection.objects.filter(
            collected_by_agent=agent,
            is_collected=True,
            collection_type__in=['rd_installment', 'fd_deposit'],
        )

        savings_collections_total = savings_all_collections
        if days_ago:
            savings_collections_total = savings_collections_total.filter(collection_date__gte=days_ago.date())
        if start_date and end_date:
            savings_collections_total = savings_collections_total.filter(
                collection_date__gte=start_date.date(),
                collection_date__lte=end_date.date(),
            )

        # Recent Collections (always last 30 days for the table) - Only successful collections
        recent_emi_collections = all_collections.filter(
            collected_at__gte=thirty_days_ago,
        ).order_by('-collected_at')[:5].values(
            'collected_id',
            'amount_received',
            'penalty_received',
            'collected_at',
            customer_name=F('loan_application__customer__full_name'),
            loan_ref_no=F('loan_application__loan_ref_no'),
        ).annotate(collection_amount=F('amount_received') + F('penalty_received'))

        recent_savings_collections = SavingsCollection.objects.filter(
            collected_by_agent=agent,
            is_collected=True,
            collection_type__in=['rd_installment', 'fd_deposit'],
            collection_date__gte=thirty_days_ago.date(),
        ).order_by('-collection_date')[:5].values(
            collected_id=F('collection_id'),
            collected_at=F('collection_date'),
            customer_name=F('account__customer__full_name'),
            loan_ref_no=F('account__application_id'),
            collection_amount=F('amount'),
        )

        def _normalize_collected_at(value):
            if value is None:
                return timezone.now()
            if isinstance(value, datetime):
                if timezone.is_naive(value):
                    return timezone.make_aware(value, timezone.get_current_timezone())
                return value
            # value is a date
            dt_value = datetime.combine(value, time.min)
            return timezone.make_aware(dt_value, timezone.get_current_timezone())

        recent_collections = sorted(
            list(recent_emi_collections) + list(recent_savings_collections),
            key=lambda r: _normalize_collected_at(r.get('collected_at')),
            reverse=True,
        )[:5]

        collections = {
            'total_count': total_collections_count,
            'total_amount': total_collections_amount,
            '30d_count': collections_total.count(),
            '30d_amount': collections_total.aggregate(
                total_amount=Sum('amount_received') + Sum('penalty_received')
            )['total_amount'] or 0,
        }

        savings_total_count = savings_all_collections.count()
        savings_total_amount = savings_all_collections.aggregate(total_amount=Sum('amount'))['total_amount'] or 0

        savings_period_count = savings_collections_total.count()
        savings_period_amount = savings_collections_total.aggregate(total_amount=Sum('amount'))['total_amount'] or 0

        collections['total_count'] = (collections.get('total_count') or 0) + (savings_total_count or 0)
        collections['total_amount'] = (collections.get('total_amount') or 0) + (savings_total_amount or 0)
        collections['30d_count'] = (collections.get('30d_count') or 0) + (savings_period_count or 0)
        collections['30d_amount'] = (collections.get('30d_amount') or 0) + (savings_period_amount or 0)

        context['collections'] = collections
        context['recent_collections'] = recent_collections
        context['filter_param'] = filter_param
        context['start_date'] = start_date_str
        context['end_date'] = end_date_str

        # Today EMI due vs collected summary
        # Primary source: explicit agent assignments for today
        today_assignments = EmiAgentAssign.objects.filter(
            agent=agent,
            is_active=True,
            installment_date=today,
        )

        assigned_due_count = today_assignments.count()
        assigned_due_amount = today_assignments.aggregate(total=Sum('installment_amount'))['total'] or 0

        # Fallback source: EMI schedules due today for this agent that may not have an EmiAgentAssign row
        # (this can happen if weekly/monthly schedules weren't assigned explicitly)
        unassigned_original_emis = LoanEMISchedule.objects.filter(
            loan_application__agent=agent,
            installment_date=today,
        ).exclude(
            agent_assignments__agent=agent,
            agent_assignments__is_active=True,
            agent_assignments__installment_date=today,
        ).distinct()

        unassigned_reschedule_emis = LoanEMIReschedule.objects.filter(
            loan_application__agent=agent,
            installment_date=today,
        ).exclude(
            agent_assignments__agent=agent,
            agent_assignments__is_active=True,
            agent_assignments__installment_date=today,
        ).distinct()

        unassigned_due_count = unassigned_original_emis.count() + unassigned_reschedule_emis.count()
        unassigned_due_amount = (
            (unassigned_original_emis.aggregate(total=Sum('installment_amount'))['total'] or 0)
            + (unassigned_reschedule_emis.aggregate(total=Sum('installment_amount'))['total'] or 0)
        )

        today_due_count = assigned_due_count + unassigned_due_count
        today_due_amount = (assigned_due_amount or 0) + (unassigned_due_amount or 0)

        # Collected for today's due EMIs (any date) without double counting
        assigned_collections = EmiCollectionDetail.objects.filter(
            collected_by_agent=agent,
            collected=True,
            assignment__in=today_assignments,
        )

        unassigned_collections = EmiCollectionDetail.objects.filter(
            collected_by_agent=agent,
            collected=True,
            assignment__isnull=True,
        ).filter(
            Q(emi__in=unassigned_original_emis) | Q(reschedule_emi__in=unassigned_reschedule_emis)
        )

        today_collected_count = assigned_collections.count() + unassigned_collections.count()

        _assigned_aggs = assigned_collections.aggregate(
            amount=Sum('amount_received'),
            penalty=Sum('penalty_received'),
        )
        _unassigned_aggs = unassigned_collections.aggregate(
            amount=Sum('amount_received'),
            penalty=Sum('penalty_received'),
        )

        today_collected_amount = (
            (_assigned_aggs.get('amount') or 0)
            + (_assigned_aggs.get('penalty') or 0)
            + (_unassigned_aggs.get('amount') or 0)
            + (_unassigned_aggs.get('penalty') or 0)
        )

        today_collected_today = EmiCollectionDetail.objects.filter(
            collected_by_agent=agent,
            collected=True,
            collected_at__date=today,
        )
        today_collected_today_count = today_collected_today.count()
        _today_aggs = today_collected_today.aggregate(
            amount=Sum('amount_received'),
            penalty=Sum('penalty_received'),
        )
        today_collected_today_amount = (
            (_today_aggs.get('amount') or 0) + (_today_aggs.get('penalty') or 0)
        )

        daily_collected_today = today_collected_today.filter(
            Q(assignment__emi__frequency='daily')
            | Q(assignment__reschedule_emi__frequency='daily')
            | Q(emi__frequency='daily')
            | Q(reschedule_emi__frequency='daily')
        )
        daily_collected_today_count = daily_collected_today.count()
        _daily_today_aggs = daily_collected_today.aggregate(
            amount=Sum('amount_received'),
            penalty=Sum('penalty_received'),
        )
        daily_collected_today_amount = (
            (_daily_today_aggs.get('amount') or 0) + (_daily_today_aggs.get('penalty') or 0)
        )

        weekly_collected_today = today_collected_today.filter(
            Q(assignment__emi__frequency='weekly')
            | Q(assignment__reschedule_emi__frequency='weekly')
            | Q(emi__frequency='weekly')
            | Q(reschedule_emi__frequency='weekly')
        )
        weekly_collected_today_count = weekly_collected_today.count()
        _weekly_today_aggs = weekly_collected_today.aggregate(
            amount=Sum('amount_received'),
            penalty=Sum('penalty_received'),
        )
        weekly_collected_today_amount = (
            (_weekly_today_aggs.get('amount') or 0) + (_weekly_today_aggs.get('penalty') or 0)
        )

        context['today_summary'] = {
            'due_count': today_due_count,
            'due_amount': today_due_amount,
            'collected_today_count': today_collected_today_count,
            'collected_today_amount': today_collected_today_amount,
            'collected_today_daily_count': daily_collected_today_count,
            'collected_today_daily_amount': daily_collected_today_amount,
            'collected_today_weekly_count': weekly_collected_today_count,
            'collected_today_weekly_amount': weekly_collected_today_amount,
            'collected_count': today_collected_count,
            'collected_amount': today_collected_amount,
        }

        # Today RD (Savings) due vs collected summary (for accounts assigned to this agent)
        assigned_savings_accounts = SavingsAgentAssign.objects.filter(
            agent=agent,
            is_active=True,
        ).values('account_id')

        today_rd_expected = (
            SavingsCollection.objects
            .filter(
                account_id__in=assigned_savings_accounts,
                collection_type='rd_installment',
                is_expected=True,
                collection_date=today,
                account__account_id__isnull=False,
                account__status='hq_approved',
            )
            .filter(Q(account__surrender_status__isnull=True) | Q(account__surrender_status__in=['', 'none']))
        )

        today_rd_due_count = today_rd_expected.count()
        today_rd_due_amount = today_rd_expected.aggregate(total=Sum('amount'))['total'] or 0

        today_rd_collected = today_rd_expected.filter(
            is_collected=True,
            collected_by_agent=agent,
        )
        today_rd_collected_count = today_rd_collected.count()
        today_rd_collected_amount = today_rd_collected.aggregate(total=Sum('amount'))['total'] or 0

        context['today_savings_summary'] = {
            'due_count': today_rd_due_count,
            'due_amount': today_rd_due_amount,
            'collected_count': today_rd_collected_count,
            'collected_amount': today_rd_collected_amount,
        }

        # Delinquency metrics (overdue EMIs assigned to agent)
        # Get EMIs assigned to this agent that are overdue and unpaid
        overdue_emis = LoanEMISchedule.objects.filter(
            Q(agent_assignments__agent=agent) &
            Q(installment_date__lt=today)
        ).exclude(collections__collected=True).distinct()
        overdue_emi_count = overdue_emis.count()
        overdue_total_amount = overdue_emis.aggregate(
            total_overdue=Sum('installment_amount')  # Use installment_amount as the scheduled amount
        )['total_overdue'] or 0

        delinquency = {
            'overdue_emi_count': overdue_emi_count,
            'overdue_total_amount': overdue_total_amount,
        }
        context['delinquency'] = delinquency

        # Assigned Loans (EMIs assigned to this agent)
        assigned_loans = EmiAgentAssign.objects.filter(agent=agent).select_related(
            'emi__loan_application__customer'
        ).order_by('-assigned_at')[:10]  # Show recent 10 assignments
        context['assigned_loans'] = assigned_loans

        context['receive_emi'] = (
            branch_employee.is_manager or 
            branch_employee.has_perm('receive_emi')
        )
        
        context['view_emis'] = (
            branch_employee.is_manager or 
            branch_employee.has_perm('view_emis')
        )
        context['view_loans'] = (
            branch_employee.is_manager or 
            branch_employee.has_perm('view_loans')
        )
        context['change_agent'] = (
            branch_employee.is_manager or 
            branch_employee.has_perm('change_agent')
        )

        return context

class AgentCreateAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
            from branch.models import BranchEmployee
            branch_employee = BranchEmployee.objects.get(id=logged_user_id)
            # Use request.data directly (it already includes files); avoid deepcopying file objects
            serializer = AgentSerializer(data=request.data)
            if serializer.is_valid():
                # Ensure the new agent is always linked to the current branch manager's branch
                agent = serializer.save(branch=branch_employee.branch)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            # print('Serializer errors:', serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            # print('AgentCreateAPIView error:', e)
            traceback.print_exc()
            return Response({'detail': f'Internal server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class AgentListAPIView(APIView):
    def get(self, request, *args, **kwargs):
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        from branch.models import BranchEmployee
        branch_employee = BranchEmployee.objects.get(id=logged_user_id)
        agents = Agent.objects.filter(branch=branch_employee.branch)
        serializer = AgentSerializer(agents, many=True)
        return Response(serializer.data)

class AgentUpdateAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]
    def put(self, request, agent_id, *args, **kwargs):
        return self._update(request, agent_id, partial=True)

    def patch(self, request, agent_id, *args, **kwargs):
        return self._update(request, agent_id, partial=True)

    def _update(self, request, agent_id, partial):
        # print('FILES:', request.FILES)
        # print('DATA:', request.data)
        logged_user_id = request.session.get('logged_user_id')
        if not logged_user_id:
            return Response({'detail': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            agent = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            return Response({'detail': 'Agent not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AgentSerializer(agent, data=request.data, partial=partial)
        if serializer.is_valid():
            agent = serializer.save()
            # print('Agent updated:', agent)
            return Response(serializer.data, status=status.HTTP_200_OK)
        # print('Serializer errors:', serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AgentDeleteAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'success': False, 'message': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

            from branch.models import BranchEmployee
            try:
                branch_employee = BranchEmployee.objects.get(id=logged_user_id)
            except BranchEmployee.DoesNotExist:
                return Response({'success': False, 'message': 'Branch user not found.'}, status=status.HTTP_403_FORBIDDEN)

            agent_id = request.data.get('agent_id') or request.data.get('agentId')
            if not agent_id:
                return Response({'success': False, 'message': 'Agent ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                agent = Agent.objects.get(agent_id=agent_id, branch=branch_employee.branch)
            except Agent.DoesNotExist:
                return Response({'success': False, 'message': 'Agent not found for this branch.'}, status=status.HTTP_404_NOT_FOUND)

            # If already inactive, just return success
            if agent.status == 'inactive':
                return Response({'success': True, 'message': 'Agent is already inactive.'}, status=status.HTTP_200_OK)

            # Business rule 1: block if agent has active loans
            active_loans_exist = LoanApplication.objects.filter(
                agent=agent,
                status__in=['approved', 'disbursed', 'branch_approved', 'hq_approved']
            ).exists()
            if active_loans_exist:
                return Response({
                    'success': False,
                    'message': 'Cannot deactivate agent because they are assigned to active loans. Please reassign or close these loans first.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Business rule 2: block if there are pending collections for this agent
            pending_collections_exist = EmiCollectionDetail.objects.filter(
                collected_by_agent=agent,
                status__in=['pending']
            ).exists()
            if pending_collections_exist:
                return Response({
                    'success': False,
                    'message': 'Cannot deactivate agent because there are pending collections. Please reassign or resolve them first.'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Soft delete: mark agent as inactive
            agent.status = 'inactive'
            agent.save(update_fields=['status'])

            return Response({'success': True}, status=status.HTTP_200_OK)

        except Exception as exc:
            # For safety, do not expose full exception details to client
            return Response({
                'success': False,
                'message': 'Unexpected error while deactivating agent.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AgentDeactivateInfoAPIView(APIView):
    """Return current loan and EMI assignment summary for an agent before deactivation."""

    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'success': False, 'message': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

            from branch.models import BranchEmployee
            try:
                branch_employee = BranchEmployee.objects.get(id=logged_user_id)
            except BranchEmployee.DoesNotExist:
                return Response({'success': False, 'message': 'Branch user not found.'}, status=status.HTTP_403_FORBIDDEN)

            agent_id = request.data.get('agent_id') or request.data.get('agentId')
            if not agent_id:
                return Response({'success': False, 'message': 'Agent ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                agent = Agent.objects.get(agent_id=agent_id, branch=branch_employee.branch)
            except Agent.DoesNotExist:
                return Response({'success': False, 'message': 'Agent not found for this branch.'}, status=status.HTTP_404_NOT_FOUND)

            # EMI assignments for this agent (we'll filter to running loans only)
            assignments = EmiAgentAssign.objects.filter(agent=agent).select_related(
                'emi__loan_application', 'reschedule_emi__loan_application'
            )

            # Group EMI counts per loan_ref_no, but only for loans that still have unpaid EMIs
            emi_summary = {}
            running_loans = set()

            for assign in assignments:
                base_emi = assign.emi or assign.reschedule_emi
                if not base_emi:
                    continue
                loan = getattr(base_emi, 'loan_application', None)
                if not loan:
                    continue

                # Only consider EMIs that are not yet paid
                if getattr(base_emi, 'paid', False):
                    continue

                # Determine if this loan is still running (has unpaid EMIs original or rescheduled)
                has_unpaid_original = LoanEMISchedule.objects.filter(
                    loan_application=loan, paid=False
                ).exists()
                has_unpaid_reschedule = LoanEMIReschedule.objects.filter(
                    loan_application=loan, paid=False
                ).exists()

                if not (has_unpaid_original or has_unpaid_reschedule):
                    # All EMIs are paid for this loan; treat as completed and skip from summary
                    continue

                loan_ref_no = loan.loan_ref_no
                running_loans.add(loan_ref_no)
                if loan_ref_no not in emi_summary:
                    emi_summary[loan_ref_no] = 0
                # Count only unpaid EMIs assigned to this agent for this loan
                emi_summary[loan_ref_no] += 1

            emi_list = [
                {'loan_ref_no': loan_ref_no, 'emi_count': count}
                for loan_ref_no, count in emi_summary.items()
            ]

            # Count of running loans for this agent (where they have unpaid EMIs assigned)
            loan_app_count = len(running_loans)

            return Response({
                'success': True,
                'loan_app_count': loan_app_count,
                'emi_assignments': emi_list,
            }, status=status.HTTP_200_OK)

        except Exception:
            return Response({
                'success': False,
                'message': 'Unexpected error while fetching agent summary.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AgentActivateAPIView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                return Response({'success': False, 'message': 'Authentication required.'}, status=status.HTTP_403_FORBIDDEN)

            from branch.models import BranchEmployee
            try:
                branch_employee = BranchEmployee.objects.get(id=logged_user_id)
            except BranchEmployee.DoesNotExist:
                return Response({'success': False, 'message': 'Branch user not found.'}, status=status.HTTP_403_FORBIDDEN)

            agent_id = request.data.get('agent_id') or request.data.get('agentId')
            if not agent_id:
                return Response({'success': False, 'message': 'Agent ID is required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                agent = Agent.objects.get(agent_id=agent_id, branch=branch_employee.branch)
            except Agent.DoesNotExist:
                return Response({'success': False, 'message': 'Agent not found for this branch.'}, status=status.HTTP_404_NOT_FOUND)

            if agent.status == 'active':
                return Response({'success': True, 'message': 'Agent is already active.'}, status=status.HTTP_200_OK)

            agent.status = 'active'
            agent.save(update_fields=['status'])

            return Response({'success': True}, status=status.HTTP_200_OK)

        except Exception:
            return Response({
                'success': False,
                'message': 'Unexpected error while activating agent.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView

from agent.models import Agent
from branch.decorators import branch_permission_required
from branch.models import BranchEmployee
from headquater.decorators import require_permissions_for_class
from headquater.models import Branch

from .services import (
    is_valid_coordinate,
    list_agent_locations,
    parse_coordinate,
    upsert_agent_location,
)


def _get_session_agent(request):
    agent_id = request.session.get('agent_id')
    if not agent_id:
        return None
    try:
        agent = Agent.objects.get(agent_id=agent_id, status='active')
    except Agent.DoesNotExist:
        return None
    return agent


class AgentLocationPingAPI(View):
    """
    Agents POST their GPS coordinates here.
    Uses agent session (agent_id). Isolated from existing agent APIs.
    """

    def post(self, request):
        agent = _get_session_agent(request)
        if not agent:
            return JsonResponse(
                {'success': False, 'message': 'Authentication required.'},
                status=401,
            )

        try:
            data = json.loads(request.body.decode('utf-8')) if request.body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            data = {}
        if not data:
            data = request.POST

        latitude = parse_coordinate(data.get('latitude'))
        longitude = parse_coordinate(data.get('longitude'))
        if not is_valid_coordinate(latitude, longitude):
            return JsonResponse(
                {'success': False, 'message': 'Invalid latitude/longitude.'},
                status=400,
            )

        loc = upsert_agent_location(
            agent=agent,
            latitude=latitude,
            longitude=longitude,
            accuracy_m=data.get('accuracy') or data.get('accuracy_m'),
            recorded_at=data.get('recorded_at'),
        )
        return JsonResponse({
            'success': True,
            'message': 'Location updated.',
            'recorded_at': loc.recorded_at.isoformat(),
        })


@method_decorator(branch_permission_required('view_agent'), name='dispatch')
class BranchAgentLocationMapView(TemplateView):
    template_name = 'agent_location/branch_map.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        branch_employee = getattr(self.request, 'branch_employee', None)
        context['branch_name'] = getattr(getattr(branch_employee, 'branch', None), 'branch_name', '')
        context['api_url'] = '/branch/agent-location/api/locations/'
        context['portal'] = 'branch'
        return context


@method_decorator(branch_permission_required('view_agent'), name='dispatch')
class BranchAgentLocationListAPI(View):
    """JSON list of agents + last location for the logged-in branch only."""

    def get(self, request):
        branch_employee = getattr(request, 'branch_employee', None)
        if branch_employee is None:
            logged_user_id = request.session.get('logged_user_id')
            try:
                branch_employee = BranchEmployee.objects.get(id=logged_user_id, is_active=True)
            except BranchEmployee.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)

        status_filter = request.GET.get('status', 'active')
        search = request.GET.get('q', '')
        agents = list_agent_locations(
            branch=branch_employee.branch,
            status=status_filter,
            search=search,
        )
        return JsonResponse({
            'success': True,
            'agents': agents,
            'branch_id': branch_employee.branch_id,
            'branch_name': branch_employee.branch.branch_name,
        })


@require_permissions_for_class('view_agent')
class HQAgentLocationMapView(LoginRequiredMixin, TemplateView):
    template_name = 'agent_location/hq_map.html'
    login_url = '/hq/login/'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['branches'] = Branch.objects.all().order_by('branch_name')
        context['selected_branch_id'] = (self.request.GET.get('branch_id') or '').strip()
        context['api_url'] = '/hq/agent-location/api/locations/'
        context['portal'] = 'hq'
        return context


@require_permissions_for_class('view_agent')
class HQAgentLocationListAPI(LoginRequiredMixin, View):
    """JSON list of agents + last location across all branches (optional branch filter)."""
    login_url = '/hq/login/'

    def get(self, request):
        if not request.user.is_authenticated:
            return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)

        status_filter = request.GET.get('status', 'active')
        search = request.GET.get('q', '')
        branch_id = (request.GET.get('branch_id') or '').strip()
        agents = list_agent_locations(
            branch=None,
            branch_id=branch_id or None,
            status=status_filter,
            search=search,
        )
        return JsonResponse({
            'success': True,
            'agents': agents,
            'branch_id': branch_id or None,
        })

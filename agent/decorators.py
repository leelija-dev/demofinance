from django.shortcuts import redirect
from django.http import JsonResponse
from agent.models import Agent


class AgentSessionRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        agent_id = request.session.get('agent_id')
        wants_json = (
            request.path.startswith('/agent/api/')
            or 'application/json' in (request.headers.get('Accept', '') or '')
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        )

        if not agent_id:
            if wants_json:
                return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)
            return redirect('/agent/login/')


        try:
            agent = Agent.objects.get(agent_id=agent_id)
        except Agent.DoesNotExist:
            request.session.flush()
            if wants_json:
                return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)
            return redirect('/agent/login/')


        if agent.status != 'active':
            request.session.flush()
            if wants_json:
                return JsonResponse({'success': False, 'message': 'Authentication required.'}, status=401)
            return redirect('/agent/login/')


        return super().dispatch(request, *args, **kwargs)
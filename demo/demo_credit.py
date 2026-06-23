from functools import wraps

from django.conf import settings
from django.utils import timezone
from django.shortcuts import render

from agent.models import Agent
from branch.models import BranchEmployee


def decrement_demo_credit(method):
    """
    Method decorator for APIView ``post()`` methods that need to decrement
    demo credit after a successful loan application submission.

    When ``settings.IS_DEMO`` is ``True``:

    1. Calls the original method.
    2. If the response indicates success (status 200 and ``success=True``),
       resolves the headquarter employee who owns the branch and decrements
       their ``demo_credit`` by 1.
    3. Returns the response **unchanged**.

    When ``settings.IS_DEMO`` is ``False``, it is a no-op and simply passes
    through to the original method.

    Usage::

        from demo.demo_credit import decrement_demo_credit

        class NewLoanApplicationAPIV2(APIView):

            @decrement_demo_credit
            def post(self, request, *args, **kwargs):
                ...
                return Response({'success': True, ...})
    """

    @wraps(method)
    def wrapper(self, request, *args, **kwargs):
        response = method(self, request, *args, **kwargs)

        if settings.IS_DEMO and response.status_code == 200 and response.data.get("success"):
            agent_id = request.session.get("agent_id")
            branch_manager_id = request.session.get("logged_user_id")

            headquarter_employee_id = request.user.id
            if agent_id:
                try:
                    agent = Agent.objects.get(agent_id=agent_id)
                    headquarter_employee_id = agent.branch.created_by.id
                except Agent.DoesNotExist:
                    pass
            if branch_manager_id:
                try:
                    branch_manager = BranchEmployee.objects.get(id=branch_manager_id)
                    headquarter_employee_id = branch_manager.created_by
                except BranchEmployee.DoesNotExist:
                    pass

            from headquater.models import HeadquarterEmployee

            headquarter_employee = HeadquarterEmployee.objects.filter(id=headquarter_employee_id).first()
            if headquarter_employee and headquarter_employee.demo_credit > 0:
                headquarter_employee.demo_credit = headquarter_employee.demo_credit - 1
                headquarter_employee.save(update_fields=["demo_credit"])

        return response

    return wrapper


def check_demo_credit(is_branch=True):
    """
    Decorator for view methods (get/post etc.) that handles demo credit check.

    - When IS_DEMO is false: just calls the original method (view handles render).
    - When IS_DEMO is true and credit is 0: renders expire template directly.
    - When IS_DEMO is true and credit > 0: stores demo_credit on self._demo_credit,
      then calls the original method (view reads it and renders normally).

    Usage:
        @check_demo_credit(BranchEmployee)
        def get(self, request, *args, **kwargs):
            ...
            context["demo_credit"] = getattr(self, '_demo_credit', None)
            return render(request, self.template_name, context)

    Args:
        branch_employee_model: The BranchEmployee model class to query.
    """

    def decorator(method):
        def wrapper(self, request, *args, **kwargs):
            if not settings.IS_DEMO:
                return method(self, request, *args, **kwargs)

            # Resolve headquarter employee from request
            agent_id = request.session.get("agent_id")
            logged_user_id = request.session.get("logged_user_id")
            headquarter_employee_id = request.user.id
            if agent_id and not is_branch:
                try:
                    agent = Agent.objects.get(agent_id=agent_id)
                    print('Got agent ->', agent)
                    headquarter_employee_id = agent.branch.created_by.id 
                except Agent.DoesNotExist:
                    pass
            
            if logged_user_id and is_branch:
                try:
                    branch_manager = BranchEmployee.objects.get(id=logged_user_id)
                    print('Got branch_manager ->', branch_manager)
                    headquarter_employee_id = branch_manager.created_by
                except BranchEmployee.DoesNotExist:
                    pass

            # headquarter_employee = request.user
            # if not headquarter_employee or headquarter_employee.id != headquarter_employee_id:
            from headquater.models import HeadquarterEmployee
            headquarter_employee = HeadquarterEmployee.objects.filter(id=headquarter_employee_id).first()

            if not headquarter_employee:
                return method(self, request, *args, **kwargs)

            trial_expiry_date = headquarter_employee.trial_expiry_date
            if not trial_expiry_date or trial_expiry_date < timezone.now():
                return method(self, request, *args, **kwargs)

            demo_credit = headquarter_employee.demo_credit
            previous_self_parent_context = self.parent_context
            if demo_credit > 0:
                self.parent_context = {
                    **previous_self_parent_context,
                    "demo_credit": demo_credit,
                }
                return method(self, request, *args, **kwargs)
            context = {
                **previous_self_parent_context,
                "error_message": "Demo credit exhausted. test",
            }
            template_name = "demo/templates/partials/demo-credit-expire.html"
            return render(request, template_name, context)

        return wrapper

    return decorator
from django.conf import settings
from django.utils import timezone
from django.shortcuts import render


def check_demo_credit(branch_employee_model):
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
            headquarter_employee_id = request.user.id
            logged_user_id = request.session.get("logged_user_id")
            if logged_user_id:
                try:
                    branch_manager = branch_employee_model.objects.get(id=logged_user_id)
                    headquarter_employee_id = branch_manager.created_by
                except branch_employee_model.DoesNotExist:
                    pass

            headquarter_employee = request.user
            if not headquarter_employee or headquarter_employee.id != headquarter_employee_id:
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

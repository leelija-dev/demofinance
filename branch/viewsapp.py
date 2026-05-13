from django.shortcuts import render
from django.utils import timezone
from django.views.generic import TemplateView
from branch.decorators import branch_permission_required
from django.utils.decorators import method_decorator
from branch.models import BranchEmployee
from headquater.models import HeadquarterEmployee

@method_decorator(branch_permission_required('add_loan'), name='dispatch')
class NewLoanApplicationCardsView(TemplateView):
    template_name = 'loan/new-application-cards.html'

    def get(self, request, *args, **kwargs):
        context = {
            "is_active": True,
            "error_message": None,
            "agent_id": None,  # For branch users, no agent_id
            "branch_manager_id": request.session.get("logged_user_id"),
            "base_template": "branch/base.html",
        }

        logged_user_id = request.session.get("logged_user_id")
        headquarter_employee_id = request.user.id

        if logged_user_id:
            try:
                branch_manager = BranchEmployee.objects.get(id=logged_user_id)
                context['branch_manager_id'] = branch_manager.id
                context['branch_id'] = getattr(branch_manager.branch, 'branch_id', None)
                if not branch_manager.branch.status:
                    context["is_active"] = False
                    context["error_message"] = (
                        "Cannot create loan application. Branch is currently inactive."
                    )
                elif not branch_manager.is_active:
                    context["is_active"] = False
                    context["error_message"] = (
                        "Cannot create loan application. Branch manager is currently inactive."
                    )
                headquarter_employee_id = branch_manager.created_by 
            except BranchEmployee.DoesNotExist:
                context["is_active"] = False
                context["error_message"] = "Branch manager not found."
        else:
            context["is_active"] = False
            context["error_message"] = "Authentication required."

        context['page_title'] = 'New Loan Application - Card Based'

        print(headquarter_employee_id)
        headquarter_employee = HeadquarterEmployee.objects.filter(id=headquarter_employee_id).first()
        if headquarter_employee:
            trial_expiry_date = headquarter_employee.trial_expiry_date
            if trial_expiry_date and trial_expiry_date >= timezone.now():
                demo_credit = headquarter_employee.demo_credit
                context["demo_credit"] = demo_credit
                if demo_credit == 0:
                    context["is_active"] = False
                    context["error_message"] = "Demo credit exhausted."
                    self.template_name = 'loan/partials/demo-credit-expire.html'
                    return render(request, self.template_name, context)
        print('context -> ', context)

        return render(request, self.template_name, context)

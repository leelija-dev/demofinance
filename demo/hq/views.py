from django.contrib import messages
from django.views.generic import View
from django.shortcuts import redirect, render
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms.forms import ReactivateTrialUserForm, TrialUserCreationForm


class CreateTrialUserView(LoginRequiredMixin, View):
    """View for creating trial users with custom email and duration"""

    template_name = "demo/hq/templates/create_trial_user.html"

    def get(self, request):
        form = TrialUserCreationForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = TrialUserCreationForm(request.POST)
        if form.is_valid():
            try:
                trial_user, trial_password = form.create_trial_user()
                messages.success(request, f"Trial user created successfully! Email: {trial_user.email}, Password: {trial_password}")
                return redirect("hq:create_trial_user")
            except Exception as e:
                messages.error(request, f"Error creating trial user: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")

        return render(request, self.template_name, {"form": form})


class ReactivateTrialUserView(LoginRequiredMixin, View):
    """View for reactivating an expired trial user with a new trial duration"""

    template_name = "demo/hq/templates/reactivate_trial_user.html"

    def get(self, request):
        form = ReactivateTrialUserForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = ReactivateTrialUserForm(request.POST)
        if form.is_valid():
            try:
                trial_user = form.reactivate_trial_user()
                messages.success(request, f'Trial user reactivated successfully! Email: {trial_user.email}, New expiry: {trial_user.trial_expiry_date.strftime("%Y-%m-%d %H:%M")}')
                return redirect("hq:reactivate_trial_user")
            except Exception as e:
                messages.error(request, f"Error reactivating trial user: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")

        return render(request, self.template_name, {"form": form})

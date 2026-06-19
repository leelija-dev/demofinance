from django import forms
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.utils import timezone


class TrialUserCreationForm(forms.Form):
    """Form for creating trial users with custom email and duration"""

    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                "placeholder": "Enter email for trial user",
            }
        ),
    )
    trial_duration = forms.IntegerField(
        label="Trial Duration (Days)",
        min_value=1,
        max_value=365,
        initial=7,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                "placeholder": "Number of days",
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")
        User = get_user_model()

        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")

        return email

    def create_trial_user(self):
        """Create a trial user based on form data"""

        User = get_user_model()
        email = self.cleaned_data["email"]
        trial_duration = self.cleaned_data["trial_duration"]

        # Generate username and password
        trial_username = email.split("@")[0] + "_admin"
        trial_password = email.split("@")[0] + "@trial2026"

        # Get or create Super Admin role
        from headquater.models import Role

        super_admin_role, _ = Role.objects.get_or_create(name="Super Admin", defaults={"role_type": "super_admin"})

        # Create trial user
        trial_user = User.objects.create_user(
            username=trial_username,
            email=email,
            password=trial_password,
            first_name="Trial",
            last_name="Admin",
            is_headquater_admin=True,
            is_staff=True,
            is_superuser=True,
            is_active=True,
        )

        # Set trial expiry
        trial_user.trial_expiry_date = timezone.now() + timedelta(days=trial_duration)
        trial_user.role = super_admin_role
        trial_user.demo_credit = 3
        trial_user.save()
        # Create a CASH wallet for the trial user
        from headquater.models import HeadquartersWallet

        if not HeadquartersWallet.objects.filter(type="CASH", created_by=trial_user).exists():
            HeadquartersWallet.objects.get_or_create(type="CASH", created_by=trial_user, defaults={"name": "Cash", "balance": 0.00})

        return trial_user, trial_password


class ReactivateTrialUserForm(forms.Form):
    """Form for reactivating an expired trial user"""

    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                "placeholder": "Enter email of expired trial user",
            }
        ),
    )
    trial_duration = forms.IntegerField(
        label="Trial Duration (Days)",
        min_value=1,
        max_value=365,
        initial=7,
        widget=forms.NumberInput(
            attrs={
                "class": "w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                "placeholder": "Number of days",
            }
        ),
    )

    def clean_email(self):
        email = self.cleaned_data.get("email")

        User = get_user_model()

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise forms.ValidationError("No user found with this email.")

        # Check if user is a trial user (has trial_expiry_date)
        if not hasattr(user, "trial_expiry_date") or not user.trial_expiry_date:
            raise forms.ValidationError("This user is not a trial user.")

        # Check if user is still active (not yet expired)

        if user.is_active and user.trial_expiry_date > timezone.now():
            raise forms.ValidationError("This trial user is still active and has not expired yet.")

        return email

    def reactivate_trial_user(self):
        """Reactivate an expired trial user with a new trial duration"""

        User = get_user_model()
        email = self.cleaned_data["email"]
        trial_duration = self.cleaned_data["trial_duration"]

        trial_user = User.objects.get(email=email)

        # Reactivate user
        trial_user.is_active = True
        trial_user.demo_credit = 3
        trial_user.trial_expiry_date = timezone.now() + timedelta(days=trial_duration)
        trial_user.save(update_fields=["is_active", "demo_credit", "trial_expiry_date"])

        # Reactivate all branches created by this trial user
        from headquater.models import Branch
        from agent.models import Agent

        branches_reactivated = Branch.objects.filter(created_by=trial_user, status=False).update(status=True)

        # Reactivate all agents under those branches
        agents_reactivated = Agent.objects.filter(branch__created_by=trial_user, status="inactive").update(status="active")

        if branches_reactivated > 0 or agents_reactivated > 0:
            print(f"Cascade reactivate: {branches_reactivated} branches and {agents_reactivated} agents reactivated")

        return trial_user

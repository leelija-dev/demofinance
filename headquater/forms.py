from django import forms
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm, AuthenticationForm
from django.contrib.auth import authenticate, get_user_model
from .models import HeadquarterEmployee, Role, Branch, HeadquartersTransactions, HeadquartersWallet, FundTransfers
from branch.models import BranchEmployee, BranchAccount
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from loan.models import LoanMainCategory, LoanCategory, LoanInterest, LoanTenure, Deductions, ChartOfAccount, ProductCategory, ProductSubCategory, Product
from savings.models import SavingType, OneTimeDeposit, DailyProduct

class HQEmployeeRegistrationForm(UserCreationForm):
    class Meta:
        model = HeadquarterEmployee
        fields = ('email', 'username', 'password1', 'password2', 'phone_number', 'address')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})
        self.fields['username'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})
        self.fields['password1'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})
        self.fields['password2'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})
        self.fields['phone_number'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})
        self.fields['address'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})

class HQPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})
        self.fields['new_password1'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})
        self.fields['new_password2'].widget.attrs.update({'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'})

class HQAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        'invalid_login': (
            'Please enter a correct email and password. '
            'Note that both fields may be case-sensitive.'
        ),
    }

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        if not user.is_active:
            raise forms.ValidationError(
                self.error_messages['inactive'],
                code='inactive',
            )
        if not (user.is_superuser or isinstance(user, HeadquarterEmployee)):
            raise forms.ValidationError(
                "You must be a superuser or a HeadquarterEmployee admin to access this page.",
                code='permission_denied',
            )

class RoleUserRegistrationForm(UserCreationForm):
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=True,
        empty_label="Select a role"
    )
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    is_headquater_admin = forms.BooleanField(required=False, initial=False)

    class Meta:
        model = HeadquarterEmployee
        fields = ('username', 'email', 'password1', 'password2', 'role', 'phone_number', 'address', 'is_headquater_admin')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make password fields required
        self.fields['password1'].required = True
        self.fields['password2'].required = True
        # Add Tailwind-style classes to widgets for consistent styling
        common_input_class = 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white'
        checkbox_class = 'mt-1 w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:bg-boxdark dark:border-strokedark dark:text-white'

        if 'username' in self.fields:
            self.fields['username'].widget.attrs.update({'class': common_input_class})
        if 'email' in self.fields:
            self.fields['email'].widget.attrs.update({'class': common_input_class})
        if 'password1' in self.fields:
            self.fields['password1'].widget.attrs.update({'class': common_input_class})
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs.update({'class': common_input_class})
        if 'phone_number' in self.fields:
            self.fields['phone_number'].widget.attrs.update({'class': common_input_class})
        if 'address' in self.fields:
            self.fields['address'].widget.attrs.update({'class': common_input_class})
        if 'role' in self.fields:
            self.fields['role'].widget.attrs.update({'class': common_input_class})
        if 'is_headquater_admin' in self.fields:
            self.fields['is_headquater_admin'].widget.attrs.update({'class': checkbox_class})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_headquater_admin = self.cleaned_data.get('is_headquater_admin', False)
        if commit:
            user.save()
        return user




# =====================================================
# class UserEditForm(RoleUserRegistrationForm):
#     """Form for editing users with optional password fields"""
#     is_active = forms.BooleanField(required=False, initial=True)
    
#     class Meta:
#         model = HeadquarterEmployee
#         fields = ('username', 'email', 'password1', 'password2', 'role', 'phone_number', 'address', 'is_active', 'is_headquater_admin')
#         widgets = {
#             'username': forms.TextInput(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent'}),
#             'email': forms.EmailInput(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent'}),
#             'phone_number': forms.TextInput(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent'}),
#             'address': forms.Textarea(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent'}),
#             'is_active': forms.CheckboxInput(attrs={'class': 'mt-1 w-4 h-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:bg-boxdark dark:border-strokedark dark:text-white'}),
            
#         }
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Make password fields optional for editing
#         self.fields['password1'].required = False
#         self.fields['password2'].required = False
        
#         # Update password field labels
#         self.fields['password1'].label = 'Password (leave blank to keep current)'
#         self.fields['password2'].label = 'Confirm Password (leave blank to keep current)'
        
#         # Update help text
#         self.fields['password1'].help_text = 'Leave blank to keep the current password'
#         self.fields['password2'].help_text = 'Leave blank to keep the current password'

#     def clean_username(self):
#         username = self.cleaned_data.get('username')
#         if username:
#             # Check if username exists, excluding current user
#             if self.instance and self.instance.pk:
#                 if HeadquarterEmployee.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
#                     raise forms.ValidationError("A user with that username already exists.")
#             else:
#                 if HeadquarterEmployee.objects.filter(username=username).exists():
#                     raise forms.ValidationError("A user with that username already exists.")
#         return username

#     def clean_email(self):
#         email = self.cleaned_data.get('email')
#         if email:
#             # Check if email exists, excluding current user
#             if self.instance and self.instance.pk:
#                 if HeadquarterEmployee.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
#                     raise forms.ValidationError("A user with that email already exists.")
#             else:
#                 if HeadquarterEmployee.objects.filter(email=email).exists():
#                     raise forms.ValidationError("A user with that email already exists.")
#         return email

#     def clean(self):
#         cleaned_data = super().clean()
#         password1 = cleaned_data.get('password1')
#         password2 = cleaned_data.get('password2')
        
#         # If one password field is filled, both must be filled
#         if password1 or password2:
#             if not password1:
#                 raise forms.ValidationError("Please enter a password.")
#             if not password2:
#                 raise forms.ValidationError("Please confirm your password.")
#             if password1 != password2:
#                 raise forms.ValidationError("Passwords don't match.")
        
#         return cleaned_data

#     def save(self, commit=True):
#         user = super().save(commit=False)
        
#         # Only set password if provided
#         if self.cleaned_data.get('password1'):
#             user.set_password(self.cleaned_data['password1'])
        
#         if commit:
#             user.save()
#         return user
# =========================================================
class UserEditForm(UserCreationForm):
    class Meta:
        model = HeadquarterEmployee
        fields = ('username', 'email', 'first_name', 'last_name', 'phone_number', 'address', 'role', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
            }),
            'address': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
                'rows': 3,
            }),
            'role': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500 dark:bg-boxdark dark:border-strokedark',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make password fields optional for editing
        self.fields['password1'].required = False
        self.fields['password2'].required = False
        
        # Add classes to password fields
        self.fields['password1'].label = 'Password (leave blank to keep current)'
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
        })

        self.fields['password2'].label = 'Confirm Password (leave blank to keep current)'
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent dark:bg-boxdark dark:border-strokedark dark:text-white',
        })

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Check if username exists, excluding current user
            if self.instance and self.instance.pk:
                if HeadquarterEmployee.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
                    raise forms.ValidationError("A user with that username already exists.")
            else:
                if HeadquarterEmployee.objects.filter(username=username).exists():
                    raise forms.ValidationError("A user with that username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email exists, excluding current user
            if self.instance and self.instance.pk:
                if HeadquarterEmployee.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
                    raise forms.ValidationError("A user with that email already exists.")
            else:
                if HeadquarterEmployee.objects.filter(email=email).exists():
                    raise forms.ValidationError("A user with that email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        # If one password field is filled, both must be filled
        if password1 or password2:
            if not password1:
                raise forms.ValidationError("Please enter a password.")
            if not password2:
                raise forms.ValidationError("Please confirm your password.")
            if password1 != password2:
                raise forms.ValidationError("Passwords don't match.")
        
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Only set password if provided
        if self.cleaned_data.get('password1'):
            user.set_password(self.cleaned_data['password1'])
        
        if commit:
            user.save()
        return user

class RoleForm(forms.ModelForm):
    class Meta:
        model = Role
        fields = ('name', 'description', 'role_type', 'permissions')
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'}),
            'description': forms.Textarea(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent', 'rows': 3}),
            'role_type': forms.Select(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'}),
            'permissions': forms.CheckboxSelectMultiple(attrs={'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role_type'].choices = Role.ROLE_TYPES

        # # Group permissions by their content type
        # from django.contrib.auth.models import Permission
        # from django.contrib.contenttypes.models import ContentType
        
        # permissions = Permission.objects.all()
        # grouped_permissions = {}
        # for perm in permissions:
        #     print(f"{perm.codename}: {perm.name}")
        # # for perm in permissions:
        # #     content_type = ContentType.objects.get(id=perm.content_type_id)
        # #     group_name = content_type.model_class().__name__ if content_type.model_class() else content_type.name
        # #     if group_name not in grouped_permissions:
        # #         grouped_permissions[group_name] = []
        # #     grouped_permissions[group_name].append(perm)
        
        # # self.fields['permissions'].choices = [
        # #     (group, [(p.id, p.name) for p in perms])
        # #     for group, perms in grouped_permissions.items()
        # # ]

        # Group permissions by their content type for better organization
        from django.contrib.contenttypes.models import ContentType
        from django.db.models import Q
        
        # Get all permissions except those from contenttypes, sessions, and admin
        permissions = self.fields['permissions'].queryset.exclude(
            Q(content_type__app_label='contenttypes') |
            Q(content_type__app_label='sessions') |
            Q(content_type__app_label='admin')
        ).select_related('content_type').order_by('content_type__app_label', 'name')
        
        # Group permissions by app label
        grouped_permissions = {}
        for perm in permissions:
            app_label = perm.content_type.app_label
            if app_label not in grouped_permissions:
                grouped_permissions[app_label] = []
            grouped_permissions[app_label].append(perm)
        
        # Create choices in the format: [(app_label, [(perm.id, perm.name), ...]), ...]
        choices = []
        for app_label, perms in sorted(grouped_permissions.items()):
            app_perms = [(p.id, f"{p.name} ({p.codename})") for p in sorted(perms, key=lambda x: x.name)]
            choices.append((app_label, app_perms))
        
        self.fields['permissions'].choices = choices

class ChartOfAccountForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccount
        fields = ['main_type', 'head_of_account', 'code', 'description']
        widgets = {
            'main_type': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'head_of_account': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'code': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'maxlength': '10',
            }),
            'description': forms.Textarea(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'rows': 3,
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.strip().upper()
        return code

class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = ['branch_name', 'address_line_1', 'address_line_2', 'city', 'district', 'state', 'postal_code', 'country', 'contact_number', 'email', 'status']
        widgets = {
            'branch_name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'address_line_1': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'address_line_2': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'city': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'state': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'country': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'district': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'contact_number': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'maxlength': '10',
                'pattern': '[0-9]{10}',
                'title': 'Enter a 10-digit phone number',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'status': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            })
        }

    def save(self, commit=True, created_by=None):
        instance = super().save(commit=False)
        if created_by:
            instance.created_by = created_by
        if commit:
            instance.save()
        return instance

    def clean(self):
        cleaned_data = super().clean()
        branch_name = cleaned_data.get('branch_name')
        email = cleaned_data.get('email')
        address_line_1 = cleaned_data.get('address_line_1')
        city = cleaned_data.get('city')
        state = cleaned_data.get('state')
        postal_code = cleaned_data.get('postal_code')
        country = cleaned_data.get('country')
        district = cleaned_data.get('district')
        contact_number = cleaned_data.get('contact_number')
    
        if not branch_name:
            self.add_error('branch_name', 'Branch name is required')
        else:
            # Check if branch name already exists in Branch model
            from headquater.models import Branch
            existing_query = Branch.objects.filter(branch_name=branch_name)
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                existing_query = existing_query.exclude(pk=self.instance.pk)
            if existing_query.exists():
                self.add_error('branch_name', 'Branch with this name already exists.')
        if not email:
            self.add_error('email', 'Email is required')
        else:
            # Check if email already exists in Branch model
            from headquater.models import Branch
            existing_query = Branch.objects.filter(email=email)
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                existing_query = existing_query.exclude(pk=self.instance.pk)
            if existing_query.exists():
                self.add_error('email', 'Branch with this Email already exists.')
        if not contact_number:
            self.add_error('contact_number', 'Contact Number is required')
        else:
            from headquater.models import Branch
            existing_query = Branch.objects.filter(contact_number=contact_number)
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                existing_query = existing_query.exclude(pk=self.instance.pk)
            if existing_query.exists():
                self.add_error('contact_number', 'Branch with this Contact Number already exists.')
        if not address_line_1:
            self.add_error('address_line_1', 'Address Line 1 is required')
        if not city:
            self.add_error('city', 'City is required')
        if not state:
            self.add_error('state', 'State is required')
        if not postal_code:
            self.add_error('postal_code', 'Postal Code is required')
        if not country:
            self.add_error('country', 'Country is required')
        if not district:
            self.add_error('district', 'District is required')
    
        return cleaned_data

class BranchManagerForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        'autocomplete': 'new-password',
    }), required=True)
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'mt-1 w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent',
        'autocomplete': 'new-password',
    }), required=True, label='Confirm Password')

    class Meta:
        model = BranchEmployee
        fields = [
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'address',
            'date_of_birth',
            'gender',
            'password',
            'confirm_password',
            'is_active',
            'gov_id_type',
            'gov_id_number',
        ]
        widgets = {
            'email': forms.EmailInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'phone_number': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'maxlength': '10',
                'pattern': '[0-9]{10}',
                'title': 'Enter a 10-digit phone number',
            }),
            'address': forms.Textarea(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'rows': 3,
            }),
            'date_of_birth': forms.DateInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30 dateofbirth',
                'type': 'date',
            }),
            'gender': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
            'gov_id_type': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'gov_id_number': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter 12-digit Aadhar number (e.g., 123456789012)',
                'autocomplete': 'off',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing (instance exists), make password fields optional
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['confirm_password'].required = False
            self.fields['password'].widget.attrs['placeholder'] = 'Leave blank to keep the current password'
            self.fields['confirm_password'].widget.attrs['placeholder'] = 'Leave blank to keep the current password'
            self.fields['password'].help_text = 'Leave blank to keep the current password.'
            self.fields['confirm_password'].help_text = 'Leave blank to keep the current password.'

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        if password or confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")
        required_fields = ['first_name', 'last_name', 'gender', 'gov_id_type', 'gov_id_number']
        for field in required_fields:
            if not cleaned_data.get(field):
                self.add_error(field, f'{self.fields[field].label or field.replace("_", " ").title()} is required')
        
        # Check email uniqueness specifically for BranchManager
        email = cleaned_data.get('email')
        if email:
            # Check if email already exists in BranchManager model
            from branch.models import BranchEmployee
            existing_query = BranchEmployee.objects.filter(email=email)
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                existing_query = existing_query.exclude(pk=self.instance.pk)
            if existing_query.exists():
                self.add_error('email', 'Branch employee with this Email already exists.')
        
        # Existing validation for gov_id_type/number
        gov_id_type = cleaned_data.get('gov_id_type')
        gov_id_number = cleaned_data.get('gov_id_number')
        if gov_id_number:
            from branch.models import BranchEmployee
            existing_query = BranchEmployee.objects.filter(gov_id_number=gov_id_number)
            # Exclude current instance if editing
            if self.instance and self.instance.pk:
                existing_query = existing_query.exclude(pk=self.instance.pk)
            if existing_query.exists():
                self.add_error('gov_id_number', 'Branch manager with this Government ID number already exists.')
        if gov_id_type and not gov_id_number:
            self.add_error('gov_id_number', 'Government ID number is required when ID type is selected.')
        elif gov_id_number and not gov_id_type:
            self.add_error('gov_id_type', 'Government ID type is required when ID number is provided.')
        # Enforce length based on gov_id_type
        if gov_id_type and gov_id_number:
            length_map = {
                'aadhar': 12,
                'pan': 10,
                'passport': 8,
                'driving_license': 16,
                'voter_id': 10,
            }
            expected_length = length_map.get(gov_id_type)
            if expected_length and len(gov_id_number.strip()) != expected_length:
                self.add_error('gov_id_number', f'{dict(self.fields["gov_id_type"].choices).get(gov_id_type, "ID")} number must be exactly {expected_length} characters.')
        # Always uppercase PAN number
        if gov_id_type == 'pan' and gov_id_number:
            cleaned_data['gov_id_number'] = gov_id_number.upper()
        return cleaned_data

    def save(self, commit=True, created_by=None):
        instance = super().save(commit=False)
        # Only update password if a new one is provided
        password = self.cleaned_data.get('password')
        if password:
            instance.password = make_password(password)
        if created_by:
            instance.created_by = created_by
        if commit:
            instance.save()
        return instance

# Loan Management Forms
class LoanMainCategoryForm(forms.ModelForm):
    class Meta:
        model = LoanMainCategory
        fields = ['name', 'is_active', 'is_shop_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter main category name (e.g., Secured, Unsecured)',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
            'is_shop_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            qs = LoanMainCategory.objects.filter(name=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            # Check each existing category individually
            isDuplicate = False
            for existing_category in qs:
                # Get current user - either from instance or from form data
                current_user = getattr(self.instance, 'created_by', None)
                if not current_user and hasattr(self, 'current_user'):
                    current_user = self.current_user
                
                if existing_category.created_by is None:
                    isDuplicate = True
                if existing_category.created_by and current_user and existing_category.created_by == current_user:
                    isDuplicate = True
            if isDuplicate:    
                raise forms.ValidationError("A main category with this name already exists.")
        return name

class LoanCategoryForm(forms.ModelForm):
    class Meta:
        model = LoanCategory
        fields = ['main_category', 'name', 'is_active']
        widgets = {
            'main_category': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter loan category name (e.g., Personal Loan, Business Loan)',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_qs = LoanMainCategory.objects.filter(is_active=True)
        if self.instance and getattr(self.instance, 'pk', None) and self.instance.main_category_id:
            base_qs = LoanMainCategory.objects.filter(
                Q(is_active=True) | Q(main_category_id=self.instance.main_category_id)
            )
            self.fields['main_category'].disabled = True

        self.fields['main_category'].queryset = base_qs.order_by('name')
        self.fields['main_category'].empty_label = 'Select main category'

    def clean_name(self):
        name = self.cleaned_data.get('name')
        main_category = self.cleaned_data.get('main_category')
        if name:
            qs = LoanCategory.objects.filter(name=name, main_category=main_category)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("A loan category with this name already exists for the selected main category.")
        return name

class LoanInterestForm(forms.ModelForm):
    class Meta:
        model = LoanInterest
        fields = ['rate_of_interest', 'description', 'is_active']
        widgets = {
            'rate_of_interest': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter interest rate (e.g., 12.50 for 12.5%)',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
            'description': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Optional description for this interest rate',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def clean_rate_of_interest(self):
        rate = self.cleaned_data.get('rate_of_interest')
        if rate is not None:
            if rate <= 0:
                raise forms.ValidationError("Interest rate must be greater than 0.")
            if rate > 100:
                raise forms.ValidationError("Interest rate cannot exceed 100%.")
        return rate


class LoanTenureForm(forms.ModelForm):
    UNIT_CHOICES = [
        ('days', 'Days'),
        ('weeks', 'Weeks'),
        ('months', 'Months'),
        ('years', 'Years'),
    ]
    unit = forms.ChoiceField(choices=UNIT_CHOICES)
    class Meta:
        model = LoanTenure
        fields = ['interest_rate', 'value', 'unit', 'is_active']
        widgets = {
            'interest_rate': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'value': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter duration value (e.g., 90 for 90 days)',
                'min': '1',
            }),
            'unit': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        main_category = kwargs.pop('main_category', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Filter by active status and user if provided
        qs = LoanInterest.objects.filter(is_active=True)
        if user is not None:
            qs = qs.filter(created_by=user)
        if main_category is not None:
            qs = qs.filter(main_category=main_category)
        self.fields['interest_rate'].queryset = qs
        self.fields['interest_rate'].empty_label = "Select an interest rate"


class ProductCategoryForm(forms.ModelForm):
    loan_category = forms.ModelChoiceField(
        queryset=LoanCategory.objects.all(),
        required=True,
        empty_label="Select a loan category"
    )
    loan_main_category = forms.ModelChoiceField(
        queryset=LoanMainCategory.objects.all(),
        required=False,
        empty_label="Select loan main category"
    )
    class Meta:
        model = ProductCategory
        fields = ['name', 'loan_category', 'loan_main_category', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter main product name (e.g., Electronics)',
            }),
            'loan_category': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['loan_category'].queryset = LoanCategory.objects.filter(is_active=True, created_by=user)
        else:
            self.fields['loan_category'].queryset = LoanCategory.objects.filter(is_active=True)
        self.fields['loan_category'].empty_label = "Select loan category"
        self.fields['loan_category'].label_from_instance = lambda obj: obj.name
        self.fields['loan_category'].widget.attrs.update({
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
        })
        if user:
            self.fields['loan_main_category'].queryset = LoanMainCategory.objects.filter(Q(is_active=True) & (Q(created_by=user) | Q(created_by__isnull=True)))
        else:
            self.fields['loan_main_category'].queryset = LoanMainCategory.objects.filter(is_active=True)
        self.fields['loan_main_category'].empty_label = "Select loan main category"
        self.fields['loan_main_category'].widget.attrs.update({
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
        })

class ProductSubCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductSubCategory
        fields = ['main_category', 'name', 'is_active']
        widgets = {
            'main_category': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter product sub category name (e.g., Smartphones)',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['main_category'].queryset = ProductCategory.objects.filter(is_active=True, created_by=user)
        else:
            self.fields['main_category'].queryset = ProductCategory.objects.filter(is_active=True)
        self.fields['main_category'].empty_label = "Select main product"

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['sub_category', 'name', 'price', 'is_active']
        widgets = {
            'sub_category': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter product name (e.g., Samsung Galaxy S22)',
            }),
            'price': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter product price',
                'step': '0.01',
                'min': '0',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['sub_category'].queryset = ProductSubCategory.objects.filter(is_active=True, created_by=user)
        else:
            self.fields['sub_category'].queryset = ProductSubCategory.objects.filter(is_active=True)
        self.fields['sub_category'].empty_label = "Select sub category"

# Savings Management Forms
class SavingTypeForm(forms.ModelForm):
    class Meta:
        model = SavingType
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter saving type name (e.g., Fixed Deposit (FD), Recurring Deposit (RD))',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            if self.instance and self.instance.pk:
                if SavingType.objects.filter(name=name).exclude(pk=self.instance.pk).exists():
                    raise forms.ValidationError("A saving type with this name already exists.")
            else:
                if SavingType.objects.filter(name=name).exists():
                    raise forms.ValidationError("A saving type with this name already exists.")
        return name


class OneTimeDepositForm(forms.ModelForm):
    class Meta:
        model = OneTimeDeposit
        fields = ['deposit_amount', 'tenure', 'tenure_unit', 'payable_amount', 'is_active']
        widgets = {
            'deposit_amount': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter deposit amount',
                'step': '0.01',
                'min': '0',
            }),
            'tenure': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter tenure',
                'min': '1',
            }),
            'tenure_unit': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'payable_amount': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter payable amount at maturity',
                'step': '0.01',
                'min': '0',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }


class DailyProductForm(forms.ModelForm):
    class Meta:
        model = DailyProduct
        fields = ['deposit_amount', 'interest_rate', 'tenure', 'tenure_unit', 'is_active']
        widgets = {
            'deposit_amount': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter deposit amount',
                'step': '0.01',
                'min': '0',
            }),
            'interest_rate': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter interest rate (e.g., 7.50 for 7.5%)',
                'step': '0.01',
                'min': '0',
                'max': '100',
            }),
            'tenure': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter tenure',
                'min': '1',
            }),
            'tenure_unit': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }


class DeductionForm(forms.ModelForm):
    class Meta:
        model = Deductions
        fields = ['deduction_name', 'deduction_type', 'deduction_value', 'deduction_description', 'is_active']
        widgets = {
            'deduction_name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter deduction name',
            }),
            'deduction_type': forms.Select(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'deduction_value': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter deduction value (e.g., 5.00)',
                'step': '0.01',
                'min': '0',
            }),
            'deduction_description': forms.Textarea(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter description (optional)',
                'rows': 4,
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deduction_type'].label = 'Deduction Type'
        self.fields['deduction_value'].label = 'Deduction Value'
        self.fields['deduction_description'].label = 'Description (optional)'



class HeadquartersWalletForm(forms.ModelForm):
    ACCOUNT_NAME_CHOICES = [
        ('Savings Account', 'Savings Account'),
        ('Current Account', 'Current Account'),
        ('Fixed Deposit Account', 'Fixed Deposit Account'),
        ('Recurring Deposit Account', 'Recurring Deposit Account'),
        ('Salary Account', 'Salary Account'),
        ('Student Account', 'Student Account'),
        ('Joint Account', 'Joint Account'),
        ('NRI Account', 'NRI Account'),
        ('Business Account', 'Business Account'),
        ('Merchant Account', 'Merchant Account'),
        ('Corporate Account', 'Corporate Account'),
        ('Money Market Account', 'Money Market Account'),
        ('Pension Account', 'Pension Account'),
        ('Trust Account', 'Trust Account'),
        ('Escrow Account', 'Escrow Account'),
        ('Foreign Currency Account', 'Foreign Currency Account'),
        ('Offshore Account', 'Offshore Account'),
    ]

    name = forms.ChoiceField(
        choices=[('', 'Select account type')] + ACCOUNT_NAME_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            'id': 'accountName',
        })
    )

    class Meta:
        model = HeadquartersWallet
        fields = ['name', 'account_number', 'bank_name']
        widgets = {
            'account_number': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
            'bank_name': forms.TextInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus-border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            }),
        }

# Choice field to render HQ accounts nicely in selects
class HQAccountChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        if getattr(obj, 'type', '') == 'BANK':
            bank = (obj.bank_name or '').strip()
            acc = (obj.account_number or '').strip()
            if bank and acc:
                return f"{bank} - {acc}"
            if bank:
                return bank
            if acc:
                return acc
            return "Bank Account"
        return "Cash"

class WalletBalanceForm(forms.ModelForm):
    TRANSACTION_TYPES = [
        ('credit', 'Credit'),
        # ('debit', 'Debit'),
    ]
    
    transaction_type = forms.ChoiceField(
        choices=TRANSACTION_TYPES,
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
        })
    )

    # Select which HQ account to credit (Cash or specific Bank)
    hq_account = HQAccountChoiceField(
        queryset=HeadquartersWallet.objects.all().order_by('type', 'bank_name', 'account_number'),
        required=True,
        label='HQ Account',
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            'id': 'id_hq_balance_account',
        })
    )
    
    # Optional purpose account from Chart of Account
    purpose_account = forms.ModelChoiceField(
        queryset=ChartOfAccount.objects.all().order_by('main_type', 'sl_no', 'head_of_account'),
        required=True,
        label='Purpose (Chart of Account)',
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
        })
    )
    
    reference_number = forms.CharField(
        label='Reference Number',
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            'placeholder': 'Enter reference number (e.g., UTR, Cheque number)',
        })
    )
    
    proof_document = forms.FileField(
        label='Proof Document',
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400',
            'accept': '.pdf,.jpg,.jpeg,.png',
        }),
        help_text='Upload proof document (PDF, JPG, PNG) - required for non-cash transactions'
    )
    
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            'placeholder': ' Enter amount (e.g., 1000.00)',
            'step': '0.01',
            'min': '0.01',
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            'rows': 3,
            'placeholder': 'Optional description',
        })
    )
    
    class Meta:
        model = HeadquartersTransactions
        fields = ['transaction_type', 'amount', 'description', 'purpose_account', 'reference_number', 'proof_document']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set default description if not provided
        if not self.initial.get('description'):
            self.initial['description'] = 'Manual balance adjustment'

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None or amount <= 0:
            raise forms.ValidationError("Amount must be greater than 0.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get('transaction_type')
        amount = cleaned_data.get('amount')
        
        if transaction_type == 'debit' and amount is not None:
            wallet = HeadquartersWallet.objects.first()
            if not wallet:
                wallet = HeadquartersWallet.objects.create(balance=0.00)
                
            if wallet.balance < amount:
                self.add_error('amount', "Insufficient balance for this debit transaction.")
        
        return cleaned_data
        
        return cleaned_data


# class HQAccountChoiceField(forms.ModelChoiceField):
#     def label_from_instance(self, obj):
#         if getattr(obj, 'type', '') == 'BANK':
#             bank = (obj.bank_name or '').strip()
#             acc = (obj.account_number or '').strip()
#             if bank and acc:
#                 return f"{bank} - {acc}"
#             if bank:
#                 return bank
#             if acc:
#                 return acc
#             return "Bank Account"
#         # Default for CASH or others
#         return "Cash"

class BranchTransferForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),  # Will be set in __init__
        label='Select Branch',
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
        }),
        empty_label="Select a branch"
    )

    # New: HQ account selection (with formatted labels)
    hq_account = HQAccountChoiceField(
        queryset=HeadquartersWallet.objects.all().order_by('type', 'bank_name', 'account_number'),
        required=True,
        label='HQ Account',
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            'id': 'id_hq_account',
        })
    )

    # Payment mode select
    payment_mode = forms.ChoiceField(
        choices=[('cash', 'Cash'), ('bank', 'Bank')],
        required=True,
        label='Payment Mode',
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            'id': 'id_payment_mode',
        })
    )
    
    # Accounts select (populated by selected branch)
    accounts = forms.ModelChoiceField(
        queryset=BranchAccount.objects.none(),
        required=False,
        label='Accounts',
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
        })
    )

    # Bank method radios (only when payment_mode == 'bank')
    transfer_bank_payment_method = forms.ChoiceField(
        choices=[('cheque', 'Cheque'), ('neft', 'NEFT / RTGS'), ('upi', 'UPI')],
        required=False,
        label='Bank Payment Method',
        widget=forms.RadioSelect(attrs={'class': 'inline-flex gap-3', 'id': 'id_transfer_bank_payment_method'})
    )
    purpose_account = forms.ModelChoiceField(
        queryset=ChartOfAccount.objects.all().order_by('main_type', 'sl_no', 'head_of_account'),
        required=True,
        label='Purpose (Chart of Account)',
        widget=forms.Select(attrs={
            'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
        })
    )
    
    class Meta:
        model = FundTransfers
        fields = ['amount', 'purpose']
        labels = {
            'amount': 'Transfer Amount',
            # 'purpose': 'Purpose (Optional)'
        }
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
                'placeholder': 'Enter amount (e.g., 1000.00)',
                'step': '0.01',
                'min': '0.01',
            }),
            # 'purpose': forms.Textarea(attrs={
            #     'class': 'dark:bg-dark-900 shadow-theme-xs focus:border-brand-300 focus:ring-brand-500/10 dark:focus:border-brand-800 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 placeholder:text-gray-400 focus:ring-3 focus:outline-hidden dark:border-gray-700 dark:bg-gray-900 dark:text-white/90 dark:placeholder:text-white/30',
            #     'rows': 3,
            #     'placeholder': 'Optional description',
            # }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.wallet = kwargs.pop('wallet', None)
        selected_branch = kwargs.pop('selected_branch', None)
        super().__init__(*args, **kwargs)
        
        # Set branch queryset to active branches created by logged-in HQ user only
        if 'branch' in self.fields and self.request:
            self.fields['branch'].queryset = Branch.objects.filter(
                status=True, 
                created_by=self.request.user
            ).order_by('branch_id', 'branch_name')
        
        # Keep HQ accounts created by logged-in user available in select to avoid invalid choice errors.
        # We will enforce alignment with payment mode in clean().
        if 'hq_account' in self.fields and self.request:
            self.fields['hq_account'].queryset = HeadquartersWallet.objects.filter(
                created_by=self.request.user
            ).order_by('type', 'bank_name', 'account_number')
        
        # Set accounts based on selected branch
        if 'accounts' in self.fields:
            if selected_branch:
                # Handle both branch instance and branch ID
                if isinstance(selected_branch, Branch):
                    # branch_id = selected_branch.id
                    branch_identifier = selected_branch.branch_id
                else:
                    branch_identifier = selected_branch
                    
                self.fields['accounts'].queryset = BranchAccount.objects.filter(
                    branch_id=branch_identifier,
                ).order_by('type', 'bank_name', 'account_number')
            else:
                self.fields['accounts'].queryset = BranchAccount.objects.none()
            
        # Set required attribute for amount
        self.fields['amount'].required = True
        # Accounts and bank method are conditionally required based on payment mode
        if 'accounts' in self.fields:
            self.fields['accounts'].required = False
        if 'transfer_bank_payment_method' in self.fields:
            self.fields['transfer_bank_payment_method'].required = False
        # self.fields['purpose'].required = False
        
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Transfer amount must be greater than zero.")
        return amount
        
    def clean(self):
        cleaned_data = super().clean()
        if not self.wallet:
            # Keep for consistency with existing code; not strictly required anymore
            pass

        # Conditional validation based on payment mode
        branch = cleaned_data.get('branch')
        account = cleaned_data.get('accounts')
        payment_mode = cleaned_data.get('payment_mode')
        bank_method = cleaned_data.get('transfer_bank_payment_method')
        hq_account = cleaned_data.get('hq_account')
        amount = cleaned_data.get('amount')

        # Validate HQ account is present
        if not hq_account:
            self.add_error('hq_account', 'Please select an HQ account.')
        else:
            # Balance check only; allow any HQ account type with any payment mode
            if amount is not None and hq_account and hq_account.balance is not None and amount > hq_account.balance:
                self.add_error('amount', 'Insufficient balance in the selected HQ account.')

        # Validate that account belongs to selected branch when provided
        if branch and account:
            if account.branch_id != branch.branch_id:
                raise forms.ValidationError("Selected account does not belong to the selected branch.")

        # If BANK, account is mandatory and bank method is mandatory
        if payment_mode == 'bank':
            if not account:
                self.add_error('accounts', 'Please select an account for Bank payment mode.')
            if not bank_method:
                self.add_error('transfer_bank_payment_method', 'Please select a bank payment method.')
        # If CASH, ensure account is not required
        elif payment_mode == 'cash':
            cleaned_data['accounts'] = None
            cleaned_data['transfer_bank_payment_method'] = None

        return cleaned_data
        
    def save(self, commit=True):
        # Don't save the form directly - we'll handle the save in the view
        # where we can create the necessary HQ transaction and update the branch wallet
        instance = super().save(commit=False)
        instance.branch = self.cleaned_data['branch']
        return instance

class TrialUserCreationForm(forms.Form):
    """Form for creating trial users with custom email and duration"""
    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white',
            'placeholder': 'Enter email for trial user'
        })
    )
    trial_duration = forms.IntegerField(
        label="Trial Duration (Days)",
        min_value=1,
        max_value=365,
        initial=7,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:border-gray-600 dark:text-white',
            'placeholder': 'Number of days'
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()
        
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        
        return email
    
    def create_trial_user(self):
        """Create a trial user based on form data"""
        from django.contrib.auth import get_user_model
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        User = get_user_model()
        email = self.cleaned_data['email']
        trial_duration = self.cleaned_data['trial_duration']
        
        # Generate username and password
        trial_username = email.split('@')[0] + "_admin"
        trial_password = email.split('@')[0] + "@trial2026"
        
        # Get or create Super Admin role
        super_admin_role, _ = Role.objects.get_or_create(
            name='Super Admin',
            defaults={'role_type': 'super_admin'}
        )
        
        # Create trial user
        trial_user = User.objects.create_user(
            username=trial_username,
            email=email,
            password=trial_password,
            first_name='Trial',
            last_name='Admin',
            is_headquater_admin=True,
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        # Set trial expiry
        trial_user.trial_expiry_date = timezone.now() + timedelta(days=trial_duration)
        trial_user.role = super_admin_role
        trial_user.save()
        
        return trial_user, trial_password
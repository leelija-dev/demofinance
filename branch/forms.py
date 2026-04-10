from django import forms
from .models import BranchEmployee, BranchRole, BranchPermission

class BranchRoleForm(forms.ModelForm):
    class Meta:
        model = BranchRole
        fields = ['name', 'description', 'is_active', 'branch', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-white'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-white'}),
            'permissions': forms.CheckboxSelectMultiple(attrs={'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-800 dark:border-gray-700 dark:text-white'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make branch field not required since it can be null for global roles
        self.fields['branch'].required = False
        # Order permissions by name
        self.fields['permissions'].queryset = BranchPermission.objects.all().order_by('name')
        
        # Add CSS classes to form fields
        # for field_name, field in self.fields.items():
        #     if field_name != 'permissions':
        #         field.widget.attrs.update({'class': 'form-input w-full'})
        #     if field_name == 'is_active':
        #         field.widget.attrs.update({'class': 'form-checkbox'})

# class BranchEmployeeForm(forms.ModelForm):
#     class Meta:
#         model = BranchEmployee
#         fields = [
#             'email', 'first_name', 'last_name', 'phone_number', 'address', 'date_of_birth', 'gender', 'password', 'confirm_password', 'is_active', 'gov_id_type', 'gov_id_number', 'role', 'is_manager',
#         ]
#         widgets = {
#             'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
#             'address': forms.Textarea(attrs={'rows': 3}),
#             'branch': forms.Select(attrs={'class': 'form-select'}),
#             'role': forms.Select(attrs={'class': 'form-select'}),
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Add Tailwind classes to all fields
#         for field_name, field in self.fields.items():
#             if field_name not in ['is_manager']:
#                 field.widget.attrs.update({
#                     'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#                 })


# class BranchEmployeeForm(forms.ModelForm):
#     # Add confirm_password as a form field only (not in Meta.fields)
#     confirm_password = forms.CharField(
#         widget=forms.PasswordInput(attrs={
#             'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#         }),
#         label="Confirm Password",
#         required=False
#     )
    
#     class Meta:
#         model = BranchEmployee
#         fields = [
#             'email', 'first_name', 'last_name', 'phone_number', 'address', 
#             'date_of_birth', 'gender', 'password', 'is_active', 
#             'gov_id_type', 'gov_id_number', 'role', 'is_manager'
#         ]
#         widgets = {
#             'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
#             'address': forms.Textarea(attrs={'rows': 3}),
#             'branch': forms.Select(attrs={'class': 'form-select'}),
#             'role': forms.Select(attrs={'class': 'form-select'}),
#             'password': forms.PasswordInput(attrs={
#                 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#             })
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Add Tailwind classes to all fields
#         for field_name, field in self.fields.items():
#             if field_name not in ['is_manager'] :
#                 field.widget.attrs.update({
#                     'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#                 })
#             if field_name == 'is_active':
#                 field.widget = forms.CheckboxInput(attrs={
#                     'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input'
#                 })

#     def clean(self):
#         cleaned_data = super().clean()
#         password = cleaned_data.get('password')
#         confirm_password = cleaned_data.get('confirm_password')

#         if password and confirm_password and password != confirm_password:
#             self.add_error('confirm_password', "Passwords don't match")
        
#         return cleaned_data

from django import forms
from django.contrib.auth.hashers import make_password
from .models import BranchEmployee

# class BranchEmployeeForm(forms.ModelForm):
#     confirm_password = forms.CharField(
#         widget=forms.PasswordInput(attrs={
#             'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#         }),
#         label="Confirm Password",
#         required=True
#     )

#     class Meta:
#         model = BranchEmployee
#         fields = [
#             'role',
#             'email',
#             'first_name',
#             'last_name',
#             'phone_number',
#             'address',
#             'date_of_birth',
#             'gender',
#             'password',
#             'is_active',
#             'gov_id_type',
#             'gov_id_number',
#             'emergency_contact_name',
#             'emergency_contact_number',
#             'emergency_contact_relation'
#         ]
#         widgets = {
#             'date_of_birth': forms.DateInput(attrs={
#                 'type': 'date',
#                 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#             }),
#             'address': forms.Textarea(attrs={
#                 'rows': 3,
#                 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#             }),
#             'role': forms.Select(attrs={
#                 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#             }),
#             'password': forms.PasswordInput(attrs={
#                 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#             }),
#             'gov_id_type': forms.Select(attrs={
#                 'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#             }),
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # Apply Tailwind classes to all fields
#         for field_name, field in self.fields.items():
#             if field_name not in ['is_active']:
#                 field.widget.attrs.update({
#                     'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
#                 })
#             if field_name == 'is_active':
#                 field.widget = forms.CheckboxInput(attrs={
#                     'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input'
#                 })
#             if field.required:
#                 field.label = f"{field.label} *"

#     def clean(self):
#         cleaned_data = super().clean()
#         password = cleaned_data.get('password')
#         confirm_password = cleaned_data.get('confirm_password')

#         if password and confirm_password and password != confirm_password:
#             self.add_error('confirm_password', "Passwords don't match")
        
#         return cleaned_data

#     # def save(self, commit=True):
#     #     employee = super().save(commit=False)
#     #     if 'password' in self.cleaned_data and self.cleaned_data['password']:
#     #         employee.set_password(self.cleaned_data['password'])
#     #     if commit:
#     #         employee.save()
#     #     return employee

#     def save(self, commit=True):
#         employee = super().save(commit=False)
#         if self.cleaned_data.get('password'):
#             employee.password = make_password(self.cleaned_data['password'])
#         if commit:
#             employee.save()
#         return employee

class BranchEmployeeForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.is_edit = kwargs.pop('is_edit', False)
        super().__init__(*args, **kwargs)
        
        # Create confirm_password field here after calling parent __init__
        self.fields['confirm_password'] = forms.CharField(
            widget=forms.PasswordInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
            }),
            label="Confirm Password",
            required=not self.is_edit  # Not required in edit mode
        )
        
        # Make password field not required in edit mode
        if self.is_edit:
            self.fields['password'].required = False
            self.fields['password'].widget.attrs['placeholder'] = 'Leave blank to keep existing password'
        
        # Apply Tailwind classes to all fields
        for field_name, field in self.fields.items():
            if field_name not in ['is_active']:
                field.widget.attrs.update({
                    'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
                })
            if field_name == 'is_active':
                field.widget = forms.CheckboxInput(attrs={
                    'class': 'form-checkbox h-5 w-5 text-primary rounded border-gray-300 focus:ring-primary dark:border-form-strokedark dark:bg-form-input'
                })
            if field.required:
                field.label = f"{field.label} *"

    class Meta:
        model = BranchEmployee
        fields = [
            'role',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'address',
            'date_of_birth',
            'gender',
            'password',
            'is_active',
            'gov_id_type',
            'gov_id_number',
            'emergency_contact_name',
            'emergency_contact_number',
            'emergency_contact_relation'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
            }),
            'address': forms.Textarea(attrs={
                'rows': 3,
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
            }),
            'role': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
            }),
            'gov_id_type': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        # Only validate passwords if they are provided
        if password or confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords don't match")
        # If in edit mode and no password provided, remove the password from cleaned_data
        elif self.is_edit and not password and not confirm_password:
            if 'password' in cleaned_data:
                del cleaned_data['password']
        # If not in edit mode, both fields are required (handled by required=True)
        
        return cleaned_data

    def save(self, commit=True):
        employee = super().save(commit=False)
        if self.cleaned_data.get('password'):
            employee.password = make_password(self.cleaned_data['password'])
        if commit:
            employee.save()
        return employee
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import Headquarters

class RoleBasedAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Add user's role and permissions to request
            request.user_role = None
            request.user_permissions = set()
            
            # Check if user is a Headquarters instance
            if isinstance(request.user, Headquarters):
                request.user_role = request.user.role
                if request.user.is_headquater_admin:
                    # Super admin has all permissions
                    request.user_permissions = {'*'}
                elif request.user.role:
                    # Add role-specific permissions
                    request.user_permissions = {
                        perm.codename for perm in request.user.role.permissions.all()
                    }
            else:
                # For regular users, check if they have any permissions
                request.user_permissions = {
                    perm.codename for perm in request.user.get_all_permissions()
                }

        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None

        # Skip permission check for login and logout views
        if view_func.__name__ in ['login_view', 'logout_view']:
            return None

        # Check if user is a Headquarters instance and is super admin
        if isinstance(request.user, Headquarters) and request.user.is_headquater_admin:
            return None

        # Check if view requires specific permission
        required_permission = getattr(view_func, 'required_permission', None)
        if required_permission:
            if required_permission not in request.user_permissions:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('hq:dashboard')  # Redirect to dashboard or appropriate page

        return None 
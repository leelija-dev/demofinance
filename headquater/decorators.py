from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from .models import HeadquarterEmployee
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse

from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods

def require_permission(permission):
    """
    Function-based view decorator that checks for a specific permission.
    Usage:
        @require_permission('auth.add_user')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('hq:login')
            
            # Allow superusers
            if getattr(request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)
            
            # Check specific permission
            if not request.user.has_perm(permission):
                page_name = request.resolver_match.url_name if request.resolver_match else 'unknown page'
                messages.error(
                    request,
                    f'You do not have permission to access {page_name}.',
                    extra_tags='permerror'
                )
                return redirect(request.META.get('HTTP_REFERER', 'hq_dashboard'))

            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def require_permissions_for_class(*perms):
    """
    Class-based view decorator that checks for one or more permissions.
    Usage:
        @require_permissions('app_label.permission1', 'app_label.permission2')
        class MyView(View):
            ...
    """
    def decorator(cls):
        original_dispatch = cls.dispatch

        @wraps(original_dispatch)
        def wrapped_dispatch(self, request, *args, **kwargs):
            # Skip permission check if we're already on the dashboard
            if request.resolver_match and request.resolver_match.url_name == 'hq_dashboard':
                return original_dispatch(self, request, *args, **kwargs)
            
            if not request.user.is_authenticated:
                return redirect('hq:login')
                
            has_permission = (request.user.is_superuser or 
                            any(request.user.has_perm(perm) for perm in perms))
            
            if not has_permission:
                # messages.error(request, "You don't have permission to access this page.")
                page_name = request.resolver_match.url_name if request.resolver_match else 'unknown page'
                messages.add_message(
                    request, 
                    messages.ERROR, 
                    f"You don't have permission to access {page_name}.", 
                    extra_tags='permerror'
                )
                return redirect(request.META.get('HTTP_REFERER', 'hq_dashboard'))
                
            return original_dispatch(self, request, *args, **kwargs)

        cls.dispatch = method_decorator(require_http_methods(["GET", "POST"]))(wrapped_dispatch)
        return cls

    return decorator


def require_role(role_name):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('hq:login')
            
            if request.user.is_headquarter_admin:
                return view_func(request, *args, **kwargs)
            
            if not request.user.role or request.user.role.name != role_name:
                messages.error(request, 'You do not have the required role to access this page.')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def require_super_admin(view_func):
    """Decorator to require super admin access"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('hq:login')
        
        # Check if user is a superuser or HeadquarterEmployee admin
        if request.user.is_superuser or (isinstance(request.user, HeadquarterEmployee) and request.user.is_headquater_admin):
            return view_func(request, *args, **kwargs)
        
        messages.error(request, "You must be a superuser or a HeadquarterEmployee admin to access this page.")
        return redirect('hq:login')
    return wrapper

def require_user_management_access(view_func):
    """Decorator to require user management access"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('hq:login')
        
        # Django superuser has all permissions
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not isinstance(request.user, HeadquarterEmployee):
            messages.error(request, "You must be a HeadquarterEmployee user to access this page.")
            return redirect('hq:dashboard')
        
        if not request.user.can_access_user_management():
            messages.error(request, "You don't have permission to access user management.")
            return redirect('hq:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def require_role_management_access(view_func):
    """Decorator to require role management access"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('hq:login')
        
        # Django superuser has all permissions
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # if not isinstance(request.user, HeadquarterEmployee):
        #     messages.error(request, "You must be a HeadquarterEmployee user to access this page.")
        #     return redirect('hq:dashboard')
        
        if not request.user.can_access_role_management():
            messages.error(request, "You don't have permission to access role management.")
            return redirect('hq:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def require_create_user_permission(view_func):
    """Decorator to require create user permission"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('hq:login')
        
        # Django superuser has all permissions
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not isinstance(request.user, HeadquarterEmployee):
            messages.error(request, "You must be a HeadquarterEmployee user to access this page.")
            return redirect('hq:dashboard')
        
        if not request.user.can_create_users():
            messages.error(request, "You don't have permission to create users.")
            return redirect('hq:user_management')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def require_edit_user_permission(view_func):
    """Decorator to require edit user permission"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('hq:login')
        
        # Django superuser has all permissions
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not isinstance(request.user, HeadquarterEmployee):
            messages.error(request, "You must be a HeadquarterEmployee user to access this page.")
            return redirect('hq:dashboard')
        
        if not request.user.can_edit_users():
            messages.error(request, "You don't have permission to edit users.")
            return redirect('hq:user_management')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def require_delete_user_permission(view_func):
    """Decorator to require delete user permission"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('hq:login')
        
        # Django superuser has all permissions
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        if not isinstance(request.user, HeadquarterEmployee):
            messages.error(request, "You must be a HeadquarterEmployee user to access this page.")
            return redirect('hq:dashboard')
        
        if not request.user.can_delete_users():
            messages.error(request, "You don't have permission to delete users.")
            return redirect('hq:user_management')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def require_branch_management_access(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Django superuser has all permissions
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
            
        # Check if user is a headquarters admin
        if isinstance(request.user, HeadquarterEmployee) and request.user.is_headquater_admin:
            return view_func(request, *args, **kwargs)
            
        # For AJAX requests, return JSON response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'You do not have permission to manage branches.',
                'errors': {}
            }, status=403)
        
        messages.error(request, 'You do not have permission to manage branches.')
        return redirect('hq:dashboard')
    
    return _wrapped_view
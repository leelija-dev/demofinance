from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from functools import wraps
from django.core.exceptions import PermissionDenied
from .models import BranchEmployee

# def branch_manager_required(view_func):
#     """
#     Decorator to check if user is authenticated as a branch manager.
#     If not authenticated, redirect to login page.
#     """
#     @wraps(view_func)
#     def _wrapped_view(request, *args, **kwargs):
#         # Check if branch manager is logged in via session
#         logged_user_id = request.session.get('logged_user_id')
        
#         if not logged_user_id:
#             # Not logged in, redirect to login with next parameter
#             messages.warning(request, 'Please log in to access this page.')
#             return redirect(f"{reverse('branch:login')}?next={request.path}")
        
#         # Check if branch manager still exists and is active
#         try:
#             from .models import BranchEmployee
#             branch_manager = BranchEmployee.objects.get(
#                 id=logged_user_id, 
#                 is_active=True
#             )
#             # Add branch manager to request for easy access
#             request.branch_employee = branch_manager
#             request.branch_manager = branch_manager  # For backward compatibility
#             return view_func(request, *args, **kwargs)
#         except BranchEmployee.DoesNotExist:
#             # Branch manager no longer exists or is inactive
#             request.session.flush()
#             messages.error(request, 'Your account is no longer active. Please contact headquarters.')
#             return redirect('branch:login')
#     return _wrapped_view



def branch_permission_required(*permission_codename, redirect_url='branch:dashboard'):
    """
    Decorator to check if a user has a specific permission or is a manager.
    
    Args:
        permission_codename (str, optional): The codename of the permission to check.
        redirect_url (str): URL to redirect if user doesn't have permission.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):

            logged_user_id = request.session.get('logged_user_id')
            if not logged_user_id:
                messages.error(request, 'You must be logged in to access this page.')
                return redirect(f"/branch/login/?next={request.path}")
            
            # Get branch employee
            try:
                branch_employee = BranchEmployee.objects.get(
                    id=logged_user_id,
                    is_active=True
                )
            except BranchEmployee.DoesNotExist:
                # Clear session if employee doesn't exist
                request.session.flush()
                messages.error(request, 'Your account is no longer active. Please contact headquarters.')
                return redirect(f"/branch/login/?next={request.path}")

            # Add branch employee to request for easy access
            request.branch_employee = branch_employee
            
            
            has_permission = (branch_employee.is_manager or 
                            any(branch_employee.has_perm(perm) for perm in permission_codename))
            
            if not has_permission:
                # messages.error(request, "You must have the required permission to access this page.")
                page_name = request.resolver_match.url_name if request.resolver_match else 'unknown page'
                page_name = page_name.replace('_', ' ').title()
                messages.add_message(
                    request, 
                    messages.ERROR,  # Default to ERROR for permission denied
                    f"You don't have permission to access {page_name}.", 
                    extra_tags='permerror error'  # Added 'error' class for styling
                )
                return redirect(request.META.get('HTTP_REFERER', redirect_url))
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
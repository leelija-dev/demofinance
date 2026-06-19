from django.shortcuts import redirect
from django.contrib import messages
from django.utils import timezone
from django.conf import settings

class TrialUserExpiryMiddleware:
    """Check trial expiry and logout expired users"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            # Check if user has trial expiry date
            if hasattr(request.user, 'trial_expiry_date') and request.user.trial_expiry_date:
                
                # Check if trial has expired
                if request.user.trial_expiry_date <= timezone.now():
                    # Deactivate user
                    request.user.is_active = False
                    request.user.save()
                    
                    # Cascade logout: deactivate branches and agents
                    self._cascade_deactivate(request.user)
                    
                    # Show message and logout
                    messages.error(request, "Your trial period has expired.")
                    from django.contrib.auth import logout
                    logout(request)
                    
                    return redirect(settings.LOGIN_URL)
        
        return self.get_response(request)
    
    def _cascade_deactivate(self, user):
        """Deactivate branches and agents created by this HQ user"""
        try:
            from headquater.models import Branch
            from agent.models import Agent
            
            # Deactivate all branches created by this HQ user (Branch.status is boolean)
            branches_deactivated = Branch.objects.filter(
                created_by=user,
                status=True
            ).update(status=False)
            
            # Deactivate all agents under those branches (Agent.status is 'active'/'inactive')
            agents_deactivated = Agent.objects.filter(
                branch__created_by=user,
                status='active'
            ).update(status='inactive')
            
            if branches_deactivated > 0 or agents_deactivated > 0:
                print(f"Cascade logout: {branches_deactivated} branches and {agents_deactivated} agents deactivated")
                
        except ImportError:
            # Models not available, skip cascade
            pass
        except Exception as e:
            # Log error but don't break the main flow
            print(f"Error in cascade deactivation: {e}")

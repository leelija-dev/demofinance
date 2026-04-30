# Landing page view for root URL
from django.shortcuts import render
from django.views import View
from django.contrib import messages
from django.utils import timezone
from headquater.models import HeadquarterEmployee

def landing_page(request):
    return render(request, 'landing.html')

class TrialCheckView(View):
    """View for non-admin users to check their trial days by email"""
    template_name = 'hq/trial_check.html'
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, self.template_name)
        
        try:
            user = HeadquarterEmployee.objects.get(email=email)
            
            # Check if user is non-admin with no role
            if user.is_headquater_admin and user.role_id == 1:
                if user.trial_expiry_date:
                    if user.trial_expiry_date > timezone.now():
                        days_left = (user.trial_expiry_date - timezone.now()).days
                        hours_left = (user.trial_expiry_date - timezone.now()).seconds // 3600
                        context = {
                            'user': user,
                            'days_left': days_left,
                            'hours_left': hours_left,
                            'trial_active': True,
                            'expiry_date': user.trial_expiry_date
                        }
                    else:
                        context = {
                            'user': user,
                            'trial_expired': True,
                            'expired_date': user.trial_expiry_date
                        }
                else:
                    context = {
                        'user': user,
                        'no_trial': True
                    }
            else:
                context = {
                    'not_trial_user': True,
                    'message': 'This account is not a trial user.'
                }
                
        except HeadquarterEmployee.DoesNotExist:
            context = {
                'user_not_found': True,
                'message': 'No account found with this email address.'
            }
        
        return render(request, self.template_name, context) 
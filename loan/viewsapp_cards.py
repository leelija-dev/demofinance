from django.shortcuts import render, redirect
from django.views.generic import TemplateView
from django.urls import reverse

from loan.forms import AutoPaymentForm
from loan.models import Agent, Shop

from agent.decorators import AgentSessionRequiredMixin

from django.contrib import messages

from loan.services.bank import AutoPaymentService

# Agent Side View
class NewLoanApplicationCardsView(AgentSessionRequiredMixin, TemplateView):
    template_name = 'loan/new-application-cards.html'

    def get(self, request, *args, **kwargs):
        context = {
            "is_active": True,
            "error_message": None,
            "agent_id": request.session.get("agent_id"),
            "branch_manager_id": request.session.get("logged_user_id"),
            "base_template": "agent/base.html",
        }

        agent_id = request.session.get("agent_id")

        if agent_id:
            try:
                agent = Agent.objects.get(agent_id=agent_id)
                if agent.status == "inactive":
                    context["is_active"] = False
                    context["error_message"] = (
                        "Cannot create loan application. Agent is currently inactive."
                    )

                # Active shops for this agent (exclude inactive shops)
                shops_qs = Shop.objects.filter(agent__agent_id=agent_id).exclude(status='inactive').order_by('name')
                shops = list(shops_qs)
                context['agent_shops'] = shops
                context['default_shop_id'] = shops[0].shop_id if len(shops) == 1 else ''
            except Agent.DoesNotExist:
                context["is_active"] = False
                context["error_message"] = "Agent not found."
                context['agent_shops'] = []
                context['default_shop_id'] = ''
        else:
            context["is_active"] = False
            context["error_message"] = "Authentication required."
            context['agent_shops'] = []
            context['default_shop_id'] = ''

        print(context)
        print(self.template_name)
        print(request)
        context['page_title'] = 'New Loan Application - Card Based'

        return render(request, self.template_name, context)





# ==========================================
# Auto Payment (eNACH) Flow Views
# ==========================================


class AutoPaymentCheckoutView(AgentSessionRequiredMixin, TemplateView):
    """View to select subscription plan and initialize Cashfree Subscription"""
    template_name = 'auto-pay/auto_payment.html'

    def get(self, request, *args, **kwargs):
        form = AutoPaymentForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request, *args, **kwargs):
        form = AutoPaymentForm(request.POST)
        if form.is_valid():
            params = form.cleaned_data
            
            plan_amount = params['plan']
            plan_name = dict(AutoPaymentForm.PLAN_CHOICES).get(plan_amount, "Custom SIP")
            
            # Use request.build_absolute_uri to construct a webhook/return URL
            # Note: 127.0.0.1 cannot receive callbacks from Cashfree Production, but sandbox redirects will work.
            return_url = request.build_absolute_uri(reverse('agent:auto_payment_success'))
            
            response = AutoPaymentService.create_subscription(
                customer_name=params['account_holder_name'],
                customer_email=params.get('email', 'test@example.com'),
                customer_phone=params['phone_number'],
                plan_name=plan_name,
                amount=plan_amount,
                return_url=return_url
            )
            
            if response['status'] == 'success':
                if 'checkout_url' in response:
                    # Mock mode or direct checkout link
                    return redirect(response['checkout_url'])
                    
                # Render the Cashfree JS SDK checkout embed page
                return render(request, 'auto-pay/auto_payment_redirect.html', {
                    'subscription_session_id': response['subscription_session_id'],
                    'is_sandbox': 'sandbox' in AutoPaymentService.BASE_URL.lower()
                })
            else:
                messages.error(request, f"Failed to initialize subscription: {response.get('message')}")
        else:
            messages.error(request, "Please correct the errors in the form.")
        return render(request, self.template_name, {'form': form})


class AutoPaymentSuccessView(AgentSessionRequiredMixin, TemplateView):
    """View to handle redirect from Cashfree after mandate authorization attempt"""
    template_name = 'auto-pay/auto_payment_success.html'

    def get(self, request, *args, **kwargs):
        sub_id = request.GET.get('subscription_id')
        status = request.GET.get('status', 'PENDING')
        
        if not sub_id:
            messages.warning(request, "Invalid return from payment gateway. No subscription ID found.")
            return redirect('agent:dashboard')
        
        return render(request, self.template_name, {
            'subscription_id': sub_id,
            'status': status
        })
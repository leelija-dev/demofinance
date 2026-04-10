from django import forms
from django.core.validators import RegexValidator

# ----- Auto Payment Form -----
class AutoPaymentForm(forms.Form):
    PLAN_CHOICES = [
        ('1', 'Basic SIP - ₹1 / month'),
        ('1000', 'Basic SIP - ₹1,000 / month'),
        ('5000', 'Premium SIP - ₹5,000 / month'),
        ('10000', 'Elite SIP - ₹10,000 / month'),
    ]
    
    plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        label="Select Mutual Fund SIP Plan",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg', 'id': 'sip_plan'})
    )
    
    account_holder_name = forms.CharField(
        label="Account Holder Name",
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Name as per bank account'})
    )
    
    phone_number = forms.CharField(
        label="Mobile Number (Linked to Bank)",
        max_length=10, min_length=10,
        validators=[RegexValidator(r'^\d{10}$', 'Enter a valid 10-digit mobile number.')],
        widget=forms.TextInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'Enter 10-digit mobile number'})
    )
    
    email = forms.EmailField(
        label="Email Address",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control form-control-lg', 'placeholder': 'your@email.com'})
    )


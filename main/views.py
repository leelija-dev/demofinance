# Landing page view for root URL
from django.shortcuts import render

def landing_page(request):
    return render(request, 'landing.html') 
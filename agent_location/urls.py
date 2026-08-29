from django.urls import path

from . import views

app_name = 'agent_location'

# Agent portal — location upload only
agent_urlpatterns = [
    path('api/ping/', views.AgentLocationPingAPI.as_view(), name='agent_ping'),
]

# Branch portal — own agents map + API
branch_urlpatterns = [
    path('', views.BranchAgentLocationMapView.as_view(), name='branch_map'),
    path('api/locations/', views.BranchAgentLocationListAPI.as_view(), name='branch_api'),
]

# HQ portal — all agents map + API
hq_urlpatterns = [
    path('', views.HQAgentLocationMapView.as_view(), name='hq_map'),
    path('api/locations/', views.HQAgentLocationListAPI.as_view(), name='hq_api'),
]

# Default empty — mounted selectively from main.urls
urlpatterns = []

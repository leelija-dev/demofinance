from django.urls import path
from django.conf import settings

from .views import CreateTrialUserView, ReactivateTrialUserView


app_name = 'hq-demo'

# handler403 = permission_denied_view

urlpatterns = []

if settings.IS_DEMO:
    urlpatterns += [
        path('create-trial-user/', CreateTrialUserView.as_view(), name='create_trial_user'),
        path('reactivate-trial-user/', ReactivateTrialUserView.as_view(), name='reactivate_trial_user'),
    ]
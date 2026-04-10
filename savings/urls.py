from django.urls import path
from .views import NewSavingsApplication, PendingSavingsApplications, NewSavingsApplicationAPI, CustomerLookupAPI, SavingsMasterDataAPI, AgentSavingsCollectionCreateAPI

app_name = 'savings'

urlpatterns = [
    path('new-application/', NewSavingsApplication.as_view(), name='new_application'),
    path('pending-applications/', PendingSavingsApplications.as_view(), name='pending_applications'),
    path('api/application/', NewSavingsApplicationAPI.as_view(), name='api_savings_application'),
    path('api/customer-lookup/', CustomerLookupAPI.as_view(), name='api_customer_lookup'),
    path('api/master-data/', SavingsMasterDataAPI.as_view(), name='api_savings_master_data'),
    path('api/collect/', AgentSavingsCollectionCreateAPI.as_view(), name='api_savings_collect'),
]

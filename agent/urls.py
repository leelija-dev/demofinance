from django.urls import path
from django.views.generic import RedirectView, TemplateView
from .views import (
    AgentDashboardView,
    AgentProfileView,
    AgentLoginAPI,
    AgentLoginPageView,
    AgentLogoutView,
    change_password,
    agent_info_api,
    agent_image_update_api,
    AgentDashboardStatsAPI,
)
from .views_shop import ShopView, ShopListPagePartialView, ShopCreateAPI, ShopDetailUpdateAPI, ShopDeleteAPI, ShopBankAccountCreateAPI, ShopLoansAPI, ShopTransactionsAPI
from loan.views import ( 
    LoanApplicationView, NewLoanApplication,
    LoanApplicationEdit, NewLoanApplicationAPI, AgentApplicationDetailView, DocumentReuploadAPI,
    LoanRejectApplication, LoanApproveApplication, LoanDocumentRequest, LoanApplicationAPI,
    LoanDocumentRequestAPI, LoanRejectApplicationAPI, LoanApproveApplicationAPI, AgentApplicationDetailAPI, 
    ApplicationTrackingAPI, LoanCategoryListAPI, LoanTenureListAPI, LoanMainCategoryListAPI, LoanSubCategoryListAPI, LoanSubCategoryTenureListAPI, ProductCategoryListAPI, ProductSubCategoryListAPI, ProductListAPI, OverdueEmiCollectView, EmiCollectView, CollectedEMIView, EmiCollectionListAPIView,
    EmiCollectedAPIView, GetEmiCollectionDetailAPI, EmiLateFeeAPIView, EmiRescheduleLateFeeAPIView, AssignedEMIView,
    AgentEmiStatementAPIView, AgentLoanEmiCollectedAPIView, AgentLoanRemainingAPIView,
    SaveDraftAPI, GetDraftAPI, DeleteDraftAPI, GetEmiCollectedDetailAPI, NextEmiForLoanAPIView,
    LoanDueEmisAPIView, AgentEmiRejectAPIView, EmiCollectionListPagePartialView,
    OverdueEmiListPagePartialView,
    AssignedEmiListPagePartialView,
    LoanApplicationListPagePartialView, BankAccountVerificationAPI, LoanDeductionsListAPI
)
from loan.viewsapi import AssignedEmiListAPIView, OverdueEmiList
from loan.viewsapp_cards import AutoPaymentCheckoutView, AutoPaymentSuccessView, NewLoanApplicationCardsView
from loan.viewsapi_v2 import NewLoanApplicationAPIV2, ShopBankAccountsAPI
from loan.otp_apis import PANVerificationAPI, SendMobileOTPAPI, VerifyMobileOTPAPI, SendAadhaarOTPAPI, VerifyAadhaarOTPAPI

from savings.views import (
    AgentSavingsCollectionsAccountsListView,
    AgentSavingsCollectionsListView,
    AgentSavingsPendingCollectionsListView,
    AgentSavingsAssignedCollectionsListView,
    AgentSavingsCollectedInstallmentsView,
    AgentSavingsCollectionCreateAPI,
    AgentSavingsCloseRequestAPI,
    SavingsApplicationPDFDownloadAPI,
    AgentMySavingsApplicationsView,
    AgentSavingsApplicationDetailView,
    AgentSavingsDocumentRequestsView,
    AgentSavingsDocumentUploadAPI,
    NewSavingsApplication,
    NewSavingsApplicationAPI,
    CustomerLookupAPI,
    SavingsMasterDataAPI,
)
app_name = 'agent'

# handler403 = permission_denied_view

urlpatterns = [
    # Show login page for GET, API login for POST
    path('', AgentLoginPageView.as_view(), name='home'),
    path('login/', AgentLoginPageView.as_view(), name='login'),
    path('logout/', AgentLogoutView.as_view(), name='agent_logout'),

    # Dashboard (requires authentication)
    path('dashboard/', AgentDashboardView.as_view(), name='dashboard'),
    path('profile/', AgentProfileView.as_view(), name='profile'),
    path('shop/', ShopView.as_view(), name='shop'),
    path('api/shops-page/', ShopListPagePartialView.as_view(), name='api_shops_page'),
    path('api/shops/', ShopCreateAPI.as_view(), name='api_shops_create'),
    path('api/shops/<str:shop_id>/', ShopDetailUpdateAPI.as_view(), name='api_shop_detail_update'),
    path('api/shops/<str:shop_id>/delete/', ShopDeleteAPI.as_view(), name='api_shop_delete'),
    path('api/shop-bank-accounts/', ShopBankAccountCreateAPI.as_view(), name='api_shop_bank_accounts_create'),
    path('api/shop-loans/', ShopLoansAPI.as_view(), name='api_shop_loans'),
    path('api/shop-transactions/', ShopTransactionsAPI.as_view(), name='api_shop_transactions'),

    # REST API login endpoint
    path('api/login/', AgentLoginAPI.as_view(), name='api_login'),
    path('api/change-password', change_password, name='api_change_password'),
    path('api/agent-info/', agent_info_api, name='agent_info_api'),
    path('api/image-update/', agent_image_update_api, name='agent_image_update_api'),
    path('api/dashboard-stats/', AgentDashboardStatsAPI.as_view(), name='agent_dashboard_stats'),

    # customer loan #
    path('new-application/', NewLoanApplication.as_view(), name='new_application'),
    path('new-application-cards/', NewLoanApplicationCardsView.as_view(), name='new_loan_application_cards'),

    path('application/', LoanApplicationView.as_view(), name='loan_applications'),
    path('document-request/', LoanDocumentRequest.as_view(), name='loan_document_request'),
    path('reject-application/', LoanRejectApplication.as_view(), name='loan_reject_application'),
    path('approve-application/', LoanApproveApplication.as_view(), name='loan_approve_application'),
    path('application-detail/<str:customer_id>/<str:loan_ref_no>/', AgentApplicationDetailView.as_view(), name='application_detail'),

    # API views
    path('api/application/', NewLoanApplicationAPI.as_view(), name='api_loan_application'),
    path('api/application-v2/', NewLoanApplicationAPIV2.as_view(), name='api_loan_application_v2'),
    
    # OTP APIs
    path('api/send-mobile-otp/', SendMobileOTPAPI.as_view(), name='send_mobile_otp'),
    path('api/verify-mobile-otp/', VerifyMobileOTPAPI.as_view(), name='verify_mobile_otp'),
    path('api/send-aadhaar-otp/', SendAadhaarOTPAPI.as_view(), name='send_aadhaar_otp'),
    path('api/verify-aadhaar-otp/', VerifyAadhaarOTPAPI.as_view(), name='verify_aadhaar_otp'),
    path('api/verify-pan-aadhaar/', PANVerificationAPI.as_view(), name='verify_pan_aadhaar'),
    path('api/loan-applications/', LoanApplicationAPI.as_view(), name='api_loan_applications'),
    path('api/loan-applications-page/', LoanApplicationListPagePartialView.as_view(), name='api_loan_applications_page'),
    path('api/document-requests/', LoanDocumentRequestAPI.as_view(), name='api_document_requests'),
    path('api/document-reupload/', DocumentReuploadAPI.as_view(), name='api_document_reupload'),
    path('api/rejected-applications/', LoanRejectApplicationAPI.as_view(), name='api_rejected_applications'),
    path('api/approved_application/', LoanApproveApplicationAPI.as_view(), name='api_approved_application'),
    path('api/application-detail/<str:customer_id>/<str:loan_ref_no>/', AgentApplicationDetailAPI.as_view(), name='api_application_detail'),
    path('api/application-tracking/<str:loan_ref_no>/', ApplicationTrackingAPI.as_view(), name='api_application_tracking'),
    path('api/product-category', ProductCategoryListAPI.as_view(), name='product_category_list_api'),
    path('api/product-sub-category', ProductSubCategoryListAPI.as_view(), name='product_sub_category_list_api'),
    path('api/product-type', ProductListAPI.as_view(), name='product_type_list_api'),
    path('api/loan-category', LoanCategoryListAPI.as_view(), name='loan_category_list_api'),
    path('api/loan-tenure', LoanTenureListAPI.as_view(), name='loan_tenure_list_api'),
    path('api/loan-main-category', LoanMainCategoryListAPI.as_view(), name='loan_main_category_list_api'),
    path('api/loan-sub-category', LoanSubCategoryListAPI.as_view(), name='loan_sub_category_list_api'),
    path('api/loan-sub-category-tenure', LoanSubCategoryTenureListAPI.as_view(), name='loan_sub_category_tenure_list_api'),
    path('api/loan-deductions', LoanDeductionsListAPI.as_view(), name='loan_deductions_list_api'),
    path('api/shop-bank-accounts', ShopBankAccountsAPI.as_view(), name='shop_bank_accounts_api'),

    # In your main urls.py or loan/urls.py
    path('api/save-draft/', SaveDraftAPI.as_view(), name='save_draft'),
    path('api/get-draft/', GetDraftAPI.as_view(), name='get_draft'),
    path('api/delete-draft/', DeleteDraftAPI.as_view(), name='delete_draft'),
    path('api/verify-bank-account/', BankAccountVerificationAPI.as_view(), name='verify_bank_account'),
]

urlpatterns += [
    path('api/edit-customer/<str:customer_id>/', LoanApplicationEdit.as_view(), name='api_edit_customer'),
]

# Savings Collections
urlpatterns += [
    path('savings/new-application/', NewSavingsApplication.as_view(), name='new_savings_application'),
    path('savings/my-applications/', AgentMySavingsApplicationsView.as_view(), name='my_savings_applications'),
    path('savings/application/<str:application_id>/', AgentSavingsApplicationDetailView.as_view(), name='savings_application_detail'),
    path('savings/document-requests/', AgentSavingsDocumentRequestsView.as_view(), name='savings_document_requests'),
    path('savings/api/document-upload/', AgentSavingsDocumentUploadAPI.as_view(), name='api_savings_document_upload'),
    path('savings/api/application/', NewSavingsApplicationAPI.as_view(), name='api_savings_application'),
    path('savings/api/application/<str:application_id>/pdf/', SavingsApplicationPDFDownloadAPI.as_view(), name='api_savings_application_pdf'),
    path('savings/api/customer-lookup/', CustomerLookupAPI.as_view(), name='api_savings_customer_lookup'),
    path('savings/api/master-data/', SavingsMasterDataAPI.as_view(), name='api_savings_master_data'),
    path('savings/api/close-request/', AgentSavingsCloseRequestAPI.as_view(), name='api_savings_close_request'),
    path('savings/collections/', AgentSavingsCollectionsAccountsListView.as_view(), name='savings_collections_accounts'),
    path('savings/pending-collections/', AgentSavingsPendingCollectionsListView.as_view(), name='savings_pending_collections'),
    path('savings/assigned-collections/', AgentSavingsAssignedCollectionsListView.as_view(), name='savings_assigned_collections'),
    path('savings/collected-installments/', AgentSavingsCollectedInstallmentsView.as_view(), name='savings_collected_installments'),
    path('savings/application/<str:application_id>/collections/', AgentSavingsCollectionsListView.as_view(), name='savings_collections_list'),
]

# for EMI collection #
urlpatterns += [
    path('overdue-emi', OverdueEmiCollectView.as_view(), name='overdue_emi'),
    path('emi-collect/', EmiCollectView.as_view(), name='emi_collect_view'),
    path('collected-emi/', CollectedEMIView.as_view(), name='collect_emi_view'),
    path('assigned-emi/', AssignedEMIView.as_view(), name='assigned_emi_view'),

    path('api/overdue-emis/', OverdueEmiList.as_view(), name='api_overdue_emis'),
    path('api/overdue-emis-page/', OverdueEmiListPagePartialView.as_view(), name='api_overdue_emis_page'),
    path('api/emi-collection-list/', EmiCollectionListAPIView.as_view(), name='api_emi_collection_List'),
    path('api/emi-collection-list-page/', EmiCollectionListPagePartialView.as_view(), name='api_emi_collection_list_page'),
    path('api/emi-collected/', EmiCollectedAPIView.as_view(), name='api_emi_collected'),
    path('api/emi-collected-detail/', GetEmiCollectionDetailAPI.as_view(), name='api_emi_collected_details'),
    path('api/collect-emi-detail/<str:collected_id>/', GetEmiCollectedDetailAPI.as_view(), name='api_collect_emi_detail'),
    path('api/assigned-emis/', AssignedEmiListAPIView.as_view(), name='api_assigned_emis'),
    path('api/assigned-emis-page/', AssignedEmiListPagePartialView.as_view(), name='api_assigned_emis_page'),
    path('api/emi-reject/', AgentEmiRejectAPIView.as_view(), name='api_emi_reject'),

    path('api/emi-late-fee/<int:emi_id>/', EmiLateFeeAPIView.as_view(), name='api_emi_late_fee'),
    path('api/reschedule-emi-late-fee/<int:res_emi_id>/', EmiRescheduleLateFeeAPIView.as_view(), name='api_reschedule_emi_late_fee'),

    path('api/emi-statement/', AgentEmiStatementAPIView.as_view(), name='agent_api_emi_statement'),
    path('api/loan-emi-collected/<str:loan_ref_no>/', AgentLoanEmiCollectedAPIView.as_view(), name='agent_api_loan_emi_collected'),
    path('api/loan-emi-remaining/<str:loan_ref_no>/', AgentLoanRemainingAPIView.as_view(), name='agent_api_loan_emi_remaining'),
    path('api/next-emi/<str:loan_ref_no>/', NextEmiForLoanAPIView.as_view(), name='api_next_emi_for_loan'),
    path('api/loan-due-emis/<str:loan_ref_no>/', LoanDueEmisAPIView.as_view(), name='api_loan_due_emis'),
]



    # Auto Payment (eNACH)

urlpatterns += [
    path('api/edit-customer/<str:customer_id>/', LoanApplicationEdit.as_view(), name='api_edit_customer'),
    path('services/auto-payment/', AutoPaymentCheckoutView.as_view(), name='auto_payment'),
    path('services/auto-payment/success/', AutoPaymentSuccessView.as_view(), name='auto_payment_success'),
]
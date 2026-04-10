from django.urls import path
from . import views
from .views import (
    HQDashboardView, HQHomeView, HQLogin, HQLogoutView, ProfileView, RoleManagementView,
    register_role_user, update_user, photo_update, user_list, create_role, edit_role, 
    # role_list, 
    add_user, edit_user,
    # permission_denied_view, 
    # get_user_data, 
    delete_user, branch_list, register_branch, branch_overview,
    get_branch_data, edit_branch, delete_branch, HQLoanListView, HQLoanDetailView, HQLoanApproveRejectView,
    branch_activity_summary,
    HQDocumentRequestAPI, HQDocumentReviewAPI,
    # loan_category_list, loan_category_create, loan_category_edit,
    # loan_interest_list, loan_interest_create, loan_interest_edit,
    # loan_tenure_list, loan_tenure_create, loan_tenure_edit,
    loan_management, loan_monitoring, chartOf_accountmanagement, LoanDisbursementList, LoanDisbursementDetail, DisbursementHold, DisbursementHoldDetail, DisbursedAndFundRelease, HQWallet, generate_loan_pdf,
    # HQAddAccount,
    # BranchTransferView
    EmiLoanListView,
    EmiScheduleView,
)

from .savingviews import (
    saving_management,
    HQSavingsBranchApprovedListView,
    HQSavingsHQApprovedListView,
    HQSavingsRejectedListView,
    HQSavingsAllOpenedAccountsListView,
    HQSavingsRDAccountsListView,
    HQSavingsFDAccountsListView,
    HQSavingsApplicationDetailView,
    HQApproveSavingsApplicationView,
    HQSavingsDocumentRequestAPI,
    HQSavingsSurrenderRequestsListView,
    HQSavingsSurrenderDecisionView,
    HQSavingsSurrenderAccountDetailView,
)
from loan.views import LoanNocPDF, LoanCategoryListAPI

# from branch.views import RepaymentView, upcomingEMIView, EmiScheduleView, upcomingEMIAPIView

app_name = 'hq'

# handler403 = permission_denied_view

urlpatterns = [
    path('dashboard/', HQDashboardView.as_view(), name='dashboard'),
    path('', HQLogin.as_view(), name='login'),
    path('login/', HQLogin.as_view(), name='login'),
    path('logout/', HQLogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    
    path('role-management/', RoleManagementView.as_view(), name='role_management'),
    # path('roles/', role_list, name='role_list'),
    path('roles/create/', create_role, name='create_role'),
    path('roles/<int:role_id>/edit/', edit_role, name='edit_role'),
    
    path('users/', user_list, name='user_management'),
    path('users/add/', add_user, name='add_user'),
    path('users/register/', register_role_user, name='register_role_user'),
    path('users/<int:user_id>/edit/', edit_user, name='edit_user'),
    path('users/<int:user_id>/update/', update_user, name='update_user'),
    path('users/<int:user_id>/photo-update/', photo_update, name='photo_update'),
    # path('users/<int:user_id>/data/', get_user_data, name='get_user_data'),
    path('users/<int:user_id>/delete/', delete_user, name='delete_user'),
    path('users/<int:user_id>/activity-summary/', views.user_activity_summary, name='user_activity_summary'),
    path('users/<int:user_id>/toggle-active/', views.toggle_user_active, name='toggle_user_active'),

    path('branch/', branch_list, name='branch_management'),
    path('branch/register/', register_branch, name='register_branch'),
    path('branch/<int:branch_id>/data/', get_branch_data, name='get_branch_data'),
    path('branch/<int:branch_id>/edit/', edit_branch, name='edit_branch'),
    path('branch/<int:branch_id>/activity-summary/', branch_activity_summary, name='branch_activity_summary'),
    path('branch/<int:branch_id>/activate/', views.activate_branch, name='activate_branch'),
    path('branch/<int:branch_id>/delete/', delete_branch, name='delete_branch'),
    path('branch/<int:branch_id>/overview/', branch_overview, name='branch_overview'),

    path('loan-applications/', HQLoanListView.as_view(), name='hq_loan_list'),
    path('loan-applications/<str:loan_ref_no>/', HQLoanDetailView.as_view(), name='hq_loan_detail'),
    path('loan-applications/<str:loan_ref_no>/review/', HQLoanApproveRejectView.as_view(), name='hq_loan_review'),
    path('api/document-request/', HQDocumentRequestAPI.as_view(), name='hq_document_request_api'),
    path('api/savings/document-request/', HQSavingsDocumentRequestAPI.as_view(), name='hq_savings_document_request_api'),
    path('api/document-review/', HQDocumentReviewAPI.as_view(), name='hq_api_document_review'),

    # Loan Close Requests (NOC) listing
    # path('loan-close-list-view/', loan_close_list_view, name='loan_close_list_view'),
    path('loan-close-requests/', views.loan_close_requests_list, name='loan_close_requests'),
    path('loan-close-requests/<str:request_id>/action/', views.loan_close_request_action, name='loan_close_request_action'),
    path('close-requests/<str:request_id>/noc.pdf', LoanNocPDF.as_view(), name='loan_noc_pdf'),
    path('loan-close-email/', views.loan_close_email, name='loan_close_email')
    
    # Loan Management URLs
    # path('loan/categories/', loan_category_list, name='loan_category_list'),
    # path('loan/categories/create/', loan_category_create, name='loan_category_create'),
    # path('loan/categories/<str:category_id>/edit/', loan_category_edit, name='loan_category_edit'),
    
    # path('loan/interests/', loan_interest_list, name='loan_interest_list'),
    # path('loan/interests/create/', loan_interest_create, name='loan_interest_create'),
    # path('loan/interests/<str:interest_id>/edit/', loan_interest_edit, name='loan_interest_edit'),
    
    # path('loan/tenures/', loan_tenure_list, name='loan_tenure_list'),
    # path('loan/tenures/create/', loan_tenure_create, name='loan_tenure_create'),
    # path('loan/tenures/<str:tenure_id>/edit/', loan_tenure_edit, name='loan_tenure_edit'),
]

urlpatterns += [
    path('loan-manage/management/', loan_management, name='loan_management'),
    path('saving-manage/management/', saving_management, name='saving_management'),
    path('product-manage/management/', views.product_management, name='product_management'),
    path('agents/', views.HQAgentListView.as_view(), name='hq_agent_list'),
    path('agents/<str:agent_id>/', views.HQAgentDetailView.as_view(), name='hq_agent_detail'),
    path('customers/', views.HQCustomerListView.as_view(), name='hq_customer_list'),
    path('customers/<str:customer_id>/', views.HQCustomerDetailView.as_view(), name='hq_customer_detail'),
    path('savings/applications/branch-approved/', HQSavingsBranchApprovedListView.as_view(), name='hq_savings_branch_approved'),
    path('savings/applications/hq-approved/', HQSavingsHQApprovedListView.as_view(), name='hq_savings_hq_approved'),
    path('savings/applications/rejected/', HQSavingsRejectedListView.as_view(), name='hq_savings_rejected'),
    path('savings/accounts/all/', HQSavingsAllOpenedAccountsListView.as_view(), name='hq_savings_accounts_all'),
    path('savings/accounts/rd/', HQSavingsRDAccountsListView.as_view(), name='hq_savings_accounts_rd'),
    path('savings/accounts/fd/', HQSavingsFDAccountsListView.as_view(), name='hq_savings_accounts_fd'),
    path('savings/surrender-requests/', HQSavingsSurrenderRequestsListView.as_view(), name='hq_savings_surrender_requests'),
    path('savings/surrender-requests/<str:application_id>/decision/', HQSavingsSurrenderDecisionView.as_view(), name='hq_savings_surrender_decision'),
    path('savings/surrender-requests/<str:application_id>/', HQSavingsSurrenderAccountDetailView.as_view(), name='hq_savings_surrender_account_detail'),
    path('savings/application/<str:application_id>/', HQSavingsApplicationDetailView.as_view(), name='hq_savings_application_detail'),
    path('savings/application/<str:application_id>/approve/', HQApproveSavingsApplicationView.as_view(), name='hq_approve_savings_application'),
    path('loan-manage/loan_monitoring/', loan_monitoring, name='loan_monitoring'),
    path('chart-of-account/management/', chartOf_accountmanagement, name='chartOf_accountmanagement'),
    path('loan/document-requests/', views.hq_document_requests_list, name='hq_document_requests'),
    path('loan/approved/', views.hq_approved_applications_list, name='hq_approved_applications'),
    path('loan/rejected/', views.hq_rejected_applications_list, name='hq_rejected_applications'),
]

# API endpoints for dashboard data
urlpatterns += [
    path('api/dashboard-data/', views.hq_dashboard_data, name='hq_dashboard_data'),
    path('api/loan-categories/', LoanCategoryListAPI.as_view(), name='loan_category_list_api'),
]

# for loan disbursed 
urlpatterns += [
    path('loan-disbursement/', LoanDisbursementList.as_view(), name='loan_disbursement'),
    path('loan-disbursement/<str:loan_ref_no>/', LoanDisbursementDetail.as_view(),
    name='loan_disbursement_detail'),
    path('disbursement-on-hold/', DisbursementHold.as_view(), name='disburesement_on_hold'),
    path('disbursement-on-hold/<str:loan_ref_no>/', DisbursementHoldDetail.as_view(), name='disburesement_on_hold_detail'),
    path('disbursed-fund-release/', DisbursedAndFundRelease.as_view(), name='disbursed_fund_release'),
]

# for repayment
urlpatterns += [
    path('emi-loan-list/', EmiLoanListView.as_view(), name='emi_loan_list'),
    path('emi-schedule/<str:loan_ref_no>/', EmiScheduleView.as_view(), name='emi_schedule'),
]

# for wallet 
urlpatterns += [
    path('wallet/', HQWallet.as_view(), name='wallet'),
    # path('wallet/add-account/', HQAddAccount.as_view(), name='add_hq_account'),
    # path('wallet/branch-transfer/', BranchTransferView.as_view(), name='branch_transfer'),
]

urlpatterns += [
    path('generate-loan-pdf/<str:loan_ref_no>/', generate_loan_pdf, name='generate_loan_pdf'),
]
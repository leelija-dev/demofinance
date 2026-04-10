from django.urls import path
from django.views.generic import RedirectView, TemplateView
from .views import (
    DisburLoadPDF,
    BranchDashboardView,
    branch_home,
    BranchProfileView,
    profile_image_update,
    change_password,
    BranchManagerLoginAPIView,
    branch_login_page,
    branch_logout,
    NewLaonApplication,
    PendingApplicationView,
    DocumentRequestHq,
    branchApplicationRejectView,
    branchApplicationApproveView,
    PendingApplicationsAPI,
    ApplicationDetailView,
    DocumentRequestAPIView,
    DocumentReviewAPIView,
    ApproveApplicationAPIView,
    RejectApplicationAPIView,
    BranchApplicationDetailAPI,
    DocumentRequestHqAPI,
    DocumentReuploadBranchAPI,
    BranchApplicationApprovedViewByHQAPI,
    BranchApplicationRejectedViewByHQAPI,
    branch_manager_info_api,
    #### for after applied application edit ####
    LoanApplicationEdit,
    #### for disbursement ###
    DisbursedByHQView,
    DisbursedDetailByHQView,
    DisbursedFundRelease,
    DisbursedByHQAPI,
    DisbursedDetailByHQAPI,
    DisbursementSubmitAPIView,
    DisbursedFundReleaseAPI,
    GenerateLoanPDFAPI,
    ### for wallet ###
    WalletView,
    MoneyTransferToHQAPI,
    MoneyTransfer,
    AddAccount,
    # UpdateAccountBalance,
    ### for repayment ###
    RepaymentView,
    EmiPaymentRowsView,
    EmiStatementAPIView,
    LoanRescheduleAPIView,
    LoanRescheduleEmiListAPIView,
    EmiScheduleView,
    upcomingEMIView,
    upcomingEMIAPIView,
    AssignAgentToEMI,
    AssignAgentToRescheduleEMI,
    UnassignAgentFromEMI,
    DueEmiView,
    DueEmiAPIView,
    OverDueEmiView,
    OverDueEmiAPIView,
    ### for EMI ###
    receiveEmiDetailAPI,
    receiveRescheduleEmiDetailAPI,
    RescheduleEmiCollectedAPIView,
    GetEmiScedulePaidDataAPI,
    LoanRemainingAPI,
    loanPaidEmiCollectedAPI,
    BranchDashboardStatsAPI,
    LoanCloseRequestAPI,
    ### completed close loan ###
    CompletedLoansView, CompletedLoansAPI, AgentTodayCollectionsView,
    AgentDepositReceiveAPIView, AgentDepositPreviousAPIView,
)
from loan.views import (
    NewLoanApplicationAPI, EmiCollectedAPIView, EmiCollectionRejectAPI, 
    GetEmiCollectionDetailAPI, EmiReCollectAPI, GetEmiCollectionDetailByEmiAPI, 
    NewLaonApplicationPdf, EmiCollectedOnlyDataAPI, EmiLateFeeAPIView,
    # Draft APIs reused for branch portal
    SaveDraftAPI, GetDraftAPI, DeleteDraftAPI,
    # Auto-pay APIs
    LoanAutoPaySetupAPI, LoanAutoPayCancelAPI, LoanAutoPayStatusAPI,
)
from branch.viewsapp import NewLoanApplicationCardsView
from loan.viewsapi_v2 import NewLoanApplicationAPIV2

from savings.views import (
    BranchNewSavingsApplication,
    BranchPendingSavingsApplications,
    BranchNewSavingsApplicationAPI,
    SavingsApplicationPDFDownloadAPI,
    BranchCustomerLookupAPI,
    BranchSavingsMasterDataAPI,
    BranchSavingsApplicationDetail,
    BranchSavingsAllAccountsListView,
    BranchSavingsWithdrawCloseListView,
    BranchSavingsCollectionsAccountsListView,
    BranchSavingsCollectionsListView,
    BranchSavingsSurrenderRequestsListView,
    BranchSavingsSurrenderVerifyAPI,
    BranchSavingsSurrenderRequestAPI,
    BranchSavingsAssignAgentView,
    BranchSavingsDocumentRequestsView,
    BranchSavingsDocumentUploadAPI,
    BranchSavingsDocumentRequestAPI,
    BranchSavingsDocumentReviewAPI,
    BranchAcceptSavingsDocumentsView,
    BranchReviewSavingsDocumentRequestView,
    BranchApproveSavingsApplicationView,
    BranchRejectSavingsApplicationView,
    BranchResubmitSavingsApplicationView,
    BranchSavingsCollectionCreateAPI,
)
from .agentview import AgentCreateAPIView, AgentListAPIView, AgentUpdateAPIView, AgentListView, AgentOverviewView, AgentCreateView, AgentEditView, AgentDeleteAPIView, AgentActivateAPIView, AgentDeactivateInfoAPIView
from .viewsreport import DailyReceiptsPaymentsView

from .customerview import customer_list, customer_detail

from .rbacview import role_list, role_create, role_edit
from .empview import (
    employee_list,
    employee_create,
    employee_edit,
    employee_detail,
    employee_deactivate_info,
    employee_deactive,
    employee_active,
)

from .views_shop import BranchShopView, BranchShopDetailView, BranchShopBankAccountAPI
app_name = 'branch'

# handler403 = permission_denied_view

urlpatterns = [
    # Home route - redirects based on authentication status
    path('', branch_home, name='home'),

    # Login page (frontend)
    path('login/', branch_login_page, name='branch_login_page'),

    # Branch manager logout
    path('logout/', branch_logout, name='branch_logout'),

    # Branch manager login API
    path('api/branch_manager/login/', BranchManagerLoginAPIView.as_view(), name='api_branch_manager_login'),
     path('api/manager-info/', branch_manager_info_api, name='branch_manager_info_api'),
    

    #Role & Permission Management
    path('roles/', role_list, name='role_list'),
    path('roles/create/', role_create, name='role_create'),
    path('role/<str:role_id>/edit', role_edit, name='role_edit'),
    # path('role/<str:role_id>/detail', role_create, name='role_detail'),

    #Employee Management
    path('employees/', employee_list, name='employee_list'),
    path('employees/create/', employee_create, name='employee_create'),
    path('employee/<str:employee_id>/edit', employee_edit, name='employee_edit'),
    path('employee/<str:employee_id>/detail', employee_detail, name='employee_detail'),

    path('employee/<str:employee_id>/deactivate-info/', employee_deactivate_info, name='employee_deactivate_info'),
    path('employee/<str:employee_id>/deactivate/', employee_deactive, name='employee_deactive'),
    path('employee/<str:employee_id>/activate/', employee_active, name='employee_active'),

    # path('api/role-management/', RoleManagementAPIView.as_view(), name='api_role_management'),


    
    # Dashboard (requires authentication)
    path('dashboard/', BranchDashboardView.as_view(), name='dashboard'),
    path('api/dashboard-stats/', BranchDashboardStatsAPI.as_view(), name='api_dashboard_stats'),
    # Profile (requires authentication)
    path('profile/', BranchProfileView.as_view(), name='profile'),
    path('profile/image-update/', profile_image_update, name='profile_image_update'),
    path('api/change-password/', change_password, name='change_password'),

    # Shop (read-only: shows shops created by agents in this branch)
    path('shop/', BranchShopView.as_view(), name='shop'),
    path('shop/<str:shop_id>/', BranchShopDetailView.as_view(), name='shop_detail'),
    path('api/shop-bank-accounts/', BranchShopBankAccountAPI.as_view(), name='api_shop_bank_accounts'),
    
    # Agent pages (protected)
    path('agent/', AgentListView.as_view(), name='agent'),
    path('agent/create/', AgentCreateView.as_view(), name='agent_create'),
    path('agent/edit/<str:agent_id>/', AgentEditView.as_view(), name='agent_edit'),
    path('agent/overview/<str:agent_id>/', AgentOverviewView.as_view(), name='agent_overview'),
    
    ## Agent API URLs for data submit or fetch ##
    path('api/agent/create/', AgentCreateAPIView.as_view(), name='api_agent_create'),
    path('api/agent/list/', AgentListAPIView.as_view(), name='api_agent_list'),
    path('api/agent/update/<str:agent_id>/', AgentUpdateAPIView.as_view(), name='api_agent_update'),
    path('api/agent/delete/', AgentDeleteAPIView.as_view(), name='api_agent_delete'),
    path('api/agent/deactivate-info/', AgentDeactivateInfoAPIView.as_view(), name='api_agent_deactivate_info'),
    path('api/agent/activate/', AgentActivateAPIView.as_view(), name='api_agent_activate'),
    path('api/agent/<str:agent_id>/today-collections/', AgentTodayCollectionsView.as_view(), name='agent_today_collections'),
    path('api/agent/<str:agent_id>/deposit/receive/', AgentDepositReceiveAPIView.as_view(), name='api_agent_deposit_receive'),
    path('api/agent/<str:agent_id>/deposit/previous/', AgentDepositPreviousAPIView.as_view(), name='api_agent_deposit_previous'),

    # loan application #
    path('new-application/', NewLaonApplication.as_view(), name='new_loan_application'),
    path('new-application-cards/', NewLoanApplicationCardsView.as_view(), name='new_loan_application_cards'),
    path('api/application-v2/', NewLoanApplicationAPIV2.as_view(), name='new_loan_application_api_v2'),
    path('loan-pending/', PendingApplicationView.as_view(), name='loan_pending_application'),
    path('document-request/', DocumentRequestHq.as_view(), name='document_request_Hq'),
    path('application-detail/<str:customer_id>/<str:loan_ref_no>/', ApplicationDetailView.as_view(), name='application_detail'),
    path('reject-application/', branchApplicationRejectView.as_view(), name='branch_application_reject_view'),
    path('approve-application/', branchApplicationApproveView.as_view(), name='branch_application_approve_view'),

    # customer management
    path('customers/', customer_list, name='customer_list'),
    path('customers/<str:customer_id>/', customer_detail, name='customer_detail'),
    
    # completed close loans ##
    path('completed-closed/', CompletedLoansView.as_view(), name='completed_closed_loans'),
    path('api/completed-closed-loans/', CompletedLoansAPI.as_view(), name='api_completed_closed_loans'),

    path('api/application/', NewLoanApplicationAPI.as_view(), name='api_loan_application'),
    path('api/pending-applications/', PendingApplicationsAPI.as_view(), name='api_pending_applications'),
    path('api/document-request/', DocumentRequestAPIView.as_view(), name='api_document_request'),
    path('api/document-review/', DocumentReviewAPIView.as_view(), name='api_document_review'),
    path('api/approve-application/', ApproveApplicationAPIView.as_view(), name='api_approve_application'),
    path('api/reject-application/', RejectApplicationAPIView.as_view(), name='api_reject_application'),
    path('api/application-detail/<str:customer_id>/<str:loan_ref_no>/', BranchApplicationDetailAPI.as_view(), name='api_application_detail'),
    path('api/document-requests-hq/', DocumentRequestHqAPI.as_view(), name='api_document_requests_hq'),
    path('api/document-reupload/', DocumentReuploadBranchAPI.as_view(), name='api_document_reupload'),

    path('api/hq_approved_applications/', BranchApplicationApprovedViewByHQAPI.as_view(),
    name='api_hq_approved_applications'),
    path('api/hq-rejected-applications/', BranchApplicationRejectedViewByHQAPI.as_view(), name='api_hq_rejected_applications'),
    path('loan/new-loan-application-pdf/', NewLaonApplicationPdf.as_view(), name='new_loan_application_pdf'),
    path('loan/loan-disbursed-pdf/', DisburLoadPDF.as_view(), name='loan_disbursed_pdf'),

]

# after applied form details edit #

urlpatterns +=[
    path('api/edit-customer/<str:customer_id>/', LoanApplicationEdit.as_view(), name='api_edit_customer'),
]

# disbursement url & api #

urlpatterns +=[
    path('disbursement/', DisbursedByHQView.as_view(), name='disbursement_list'),
    path('disbursement-details/<str:loan_ref_no>/', DisbursedDetailByHQView.as_view(), name='disbursement_detail'),
    path('disbursed-fund-release/', DisbursedFundRelease.as_view(), name='disbursed_fund_relese'),

    # API #
    path('api/disbursedbyhq/', DisbursedByHQAPI.as_view(), name='api_disbursed_by_hq'),
    path('api/disbursement-details/<str:loan_ref_no>/', DisbursedDetailByHQAPI.as_view(), name='api_disbursement_detail'),
    path('api/disbursement-submit/', DisbursementSubmitAPIView.as_view(), name='api_disbursement_submit'),
    path('api/disbursed-fund-release/', DisbursedFundReleaseAPI.as_view(), name='api_disbursed_fund_release'),
    path('api/generate-pdf/', GenerateLoanPDFAPI.as_view(), name='api_generate_pdf')
]

# wallet #

urlpatterns +=[
    path('wallet/', WalletView.as_view(), name='branch_wallet'),
    path('api/money-transfer-to-hq/', MoneyTransferToHQAPI.as_view(), name='api_money_Transfer_to_branch'),
    path('api/money-transfer/', MoneyTransfer.as_view(), name='api_money_tranfer'),
    # add account api #
    path('api/add-account/', AddAccount.as_view(), name='api_add_account'),
    # path('api/update-account-balance/<str:account_id>/', UpdateAccountBalance.as_view(), name='api_update_account_balance'),
]

# repayment #
urlpatterns +=[
    path('repayment/', RepaymentView.as_view(), name='emi_payment'),
    path('emi-schedule/', EmiScheduleView.as_view(), name='emi_schedule'),
    path('api/paid-emi-scedule/', GetEmiScedulePaidDataAPI.as_view(), name='api_paid_emi_scedule'),
    path('api/emi-payment-rows/', EmiPaymentRowsView.as_view(), name='api_emi_payment_rows'),
    path('api/emi-statement/', EmiStatementAPIView.as_view(), name='api_emi_statement'),
    path('api/loan-reschedule/<str:loan_ref_no>/', LoanRescheduleAPIView.as_view(), name='api_loan_reschedule'),
    path('api/loan-reschedule-emis/<str:loan_ref_no>/', LoanRescheduleEmiListAPIView.as_view(), name='api_loan_reschedule_emis'),
    path('upcoming-emi/', upcomingEMIView.as_view(), name='upcoming_emi_payment'),
    path('api/upcoming-emi/', upcomingEMIAPIView.as_view(), name='api_upcoming_emi'),
    path('api/assign-agent-to-emi/', AssignAgentToEMI.as_view(), name='assign_agent_to_emi'),
    path('api/assign-agent-to-reschedule-emi/', AssignAgentToRescheduleEMI.as_view(), name='assign_agent_to_reschedule_emi'),
    path('api/unassign-agent-from-emi/<int:emi_id>/', UnassignAgentFromEMI.as_view(), name='unassign_agent_from_emi'),
    path('due-emi/', DueEmiView.as_view(), name='due_emi_view'),
    path('api/due-emi/', DueEmiAPIView.as_view(), name='api_due_emi_view'),
    path('over-due-emi/', OverDueEmiView.as_view(), name='over_due_emi_view'),
    path('api/over-due-emi/', OverDueEmiAPIView.as_view(), name='api_over_due_emi'),
    path('api/emi-late-fee/<int:emi_id>/', EmiLateFeeAPIView.as_view(), name='api_emi_late_fee'),
    path('api/loan-close-request/<str:loan_ref_no>/', LoanCloseRequestAPI.as_view(), name='api_loan_close_request'),
]

# emi collect detail #
urlpatterns +=[
    path('api/emi-collect/', EmiCollectedAPIView.as_view(), name='api_emi_collect'),
    path('api/reschedule-emi-collect/', RescheduleEmiCollectedAPIView.as_view(), name='api_reschedule_emi_collect'),
    path('api/emi-collection-reject/<int:emi_id>/', EmiCollectionRejectAPI.as_view(), name='api_collection_reject'),
    path('api/emi-re-collected/<int:emi_id>/', EmiReCollectAPI.as_view(), name='api_emi_re_collect'),
    path('api/emi-receive/<int:emi_id>/', receiveEmiDetailAPI.as_view(), name='api_emi_receive_detail'),
    path('api/reschedule-emi-receive/<int:reschedule_emi_id>/', receiveRescheduleEmiDetailAPI.as_view(), name='api_reschedule_emi_receive_detail'),
    path('api/emi-collected-detail/', GetEmiCollectionDetailAPI.as_view(), name='api_emi_collected_details'),
    path('api/emi-collection-detail/<int:emi_id>/', GetEmiCollectionDetailByEmiAPI.as_view(), name='api_emi_collection_detail_by_emi'),
    path('api/loan-emi-collected/<str:loan_ref_no>/', loanPaidEmiCollectedAPI.as_view(), name='api_paid_emi_collected'),
    path('api/loan-emi-remaining/<str:loan_ref_no>/', LoanRemainingAPI.as_view(), name='loan-remaining'),
    path('api/emi-collect-only-data/<str:loan_ref_no>/', EmiCollectedOnlyDataAPI.as_view(), name='api_emi_collect_only_data'),
]

# draft save/load/delete for branch portal (same URLs as agent side but under /branch/)
urlpatterns += [
    path('api/save-draft/', SaveDraftAPI.as_view(), name='branch_save_draft'),
    path('api/get-draft/', GetDraftAPI.as_view(), name='branch_get_draft'),
    path('api/delete-draft/', DeleteDraftAPI.as_view(), name='branch_delete_draft'),
    # Auto-pay APIs
    path('api/loan/<str:loan_ref_no>/auto-pay/setup/', LoanAutoPaySetupAPI.as_view(), name='api_loan_auto_pay_setup'),
    path('api/loan/<str:loan_ref_no>/auto-pay/cancel/', LoanAutoPayCancelAPI.as_view(), name='api_loan_auto_pay_cancel'),
    path('api/loan/<str:loan_ref_no>/auto-pay/status/', LoanAutoPayStatusAPI.as_view(), name='api_loan_auto_pay_status'),
]



# Daily Transaction and Summary Reports #
urlpatterns += [
    path('daily-receipt-payment/', DailyReceiptsPaymentsView.as_view(), name='daily_receipts_payments'),
]


# Saving account #

urlpatterns += [
    path('savings/document-requests/', BranchSavingsDocumentRequestsView.as_view(), name='savings_document_requests'),
    path('savings/api/document-upload/', BranchSavingsDocumentUploadAPI.as_view(), name='api_savings_document_upload'),
    path('savings/api/document-request/', BranchSavingsDocumentRequestAPI.as_view(), name='api_savings_document_request'),
    path('savings/api/document-review/', BranchSavingsDocumentReviewAPI.as_view(), name='api_savings_document_review'),  # New endpoint
    path('savings/api/collect/', BranchSavingsCollectionCreateAPI.as_view(), name='api_savings_collect'),
    path('savings/new-application/', BranchNewSavingsApplication.as_view(), name='new_savings_application'),
    path('savings/pending-applications/', BranchPendingSavingsApplications.as_view(), name='pending_savings_applications'),
    path('savings/accounts/', BranchSavingsAllAccountsListView.as_view(), name='savings_all_accounts'),
    path('savings/withdraw-close/', BranchSavingsWithdrawCloseListView.as_view(), name='savings_withdraw_close'),
    path('savings/collections/', BranchSavingsCollectionsAccountsListView.as_view(), name='savings_collections_accounts'),
    path('savings/surrender-requests/', BranchSavingsSurrenderRequestsListView.as_view(), name='savings_surrender_requests'),
    path('savings/api/surrender/verify/', BranchSavingsSurrenderVerifyAPI.as_view(), name='api_savings_surrender_verify'),
    path('savings/api/surrender/request/', BranchSavingsSurrenderRequestAPI.as_view(), name='api_savings_surrender_request'),
    path('savings/document-request/<int:document_request_id>/review/', BranchReviewSavingsDocumentRequestView.as_view(), name='review_savings_document_request'),
    path('savings/application/<str:application_id>/', BranchSavingsApplicationDetail.as_view(), name='savings_application_detail'),
    path('savings/application/<str:application_id>/collections/', BranchSavingsCollectionsListView.as_view(), name='savings_collections_list'),
    path('savings/application/<str:application_id>/assign-agent/', BranchSavingsAssignAgentView.as_view(), name='savings_assign_agent'),
    path('savings/application/<str:application_id>/accept-documents/', BranchAcceptSavingsDocumentsView.as_view(), name='accept_savings_documents'),
    path('savings/application/<str:application_id>/approve/', BranchApproveSavingsApplicationView.as_view(), name='approve_savings_application'),
    path('savings/application/<str:application_id>/reject/', BranchRejectSavingsApplicationView.as_view(), name='reject_savings_application'),
    path('savings/application/<str:application_id>/resubmit/', BranchResubmitSavingsApplicationView.as_view(), name='resubmit_savings_application'),
    path('savings/api/application/', BranchNewSavingsApplicationAPI.as_view(), name='api_savings_application'),
    path('savings/api/application/<str:application_id>/pdf/', SavingsApplicationPDFDownloadAPI.as_view(), name='api_savings_application_pdf'),
    path('savings/api/customer-lookup/', BranchCustomerLookupAPI.as_view(), name='api_savings_customer_lookup'),
    path('savings/api/master-data/', BranchSavingsMasterDataAPI.as_view(), name='api_savings_master_data'),
]

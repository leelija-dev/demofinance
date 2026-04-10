from django.contrib import admin
from .models import (
    LoanApplication, CustomerDetail, CustomerAddress, CustomerLoanDetail,
    CustomerDocument, DocumentRequest, DocumentReupload, DocumentReview, LoanCategory, LoanInterest, LoanTenure,
    LoanEMISchedule, EmiCollectionDetail, LoanPeriod
)

# Register your models here.

class AllFieldsListDisplayAdmin(admin.ModelAdmin):
    def get_list_display(self, request):
        return [field.name for field in self.model._meta.fields]

@admin.register(LoanCategory)
class LoanCategoryAdmin(admin.ModelAdmin):
    list_display = ['category_id', 'name', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'category_id']
    readonly_fields = ['category_id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category_id')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(LoanInterest)
class LoanInterestAdmin(admin.ModelAdmin):
    list_display = ['interest_id', 'rate_of_interest', 'description', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at', 'rate_of_interest']
    search_fields = ['interest_id', 'description']
    readonly_fields = ['interest_id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('rate_of_interest', 'description', 'interest_id')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(LoanTenure)
class LoanTenureAdmin(admin.ModelAdmin):
    list_display = ['tenure_id', 'interest_rate', 'value', 'unit', 'is_active']
    list_filter = ['is_active', 'interest_rate', 'created_at']
    search_fields = ['tenure_id', 'interest_rate__rate_of_interest']
    readonly_fields = ['tenure_id', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('interest_rate', 'value', 'unit', 'tenure_id')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Audit Information', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by for new objects
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

@admin.register(LoanApplication)
class LoanApplicationAdmin(admin.ModelAdmin):
    list_display = ['loan_ref_no', 'customer', 'status', 'branch', 'agent', 'submitted_at']
    list_filter = ['status', 'submitted_at', 'branch', 'agent']
    search_fields = ['loan_ref_no', 'customer__full_name', 'customer__customer_id']
    readonly_fields = ['loan_ref_no', 'submitted_at', 'disbursed_at']
    date_hierarchy = 'submitted_at'

@admin.register(CustomerDetail)
class CustomerDetailAdmin(admin.ModelAdmin):
    list_display = ['customer_id', 'full_name', 'contact', 'email', 'agent', 'branch', 'submitted_at']
    list_filter = ['submitted_at', 'agent', 'branch', 'gender']
    search_fields = ['customer_id', 'full_name', 'contact', 'email', 'adhar_number', 'pan_number']
    readonly_fields = ['customer_id', 'submitted_at', 'last_update']

@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = ['customer', 'city_or_town', 'state', 'current_city_or_town', 'current_state', 'submitted_at']
    list_filter = ['submitted_at', 'agent', 'branch', 'state', 'current_state']
    search_fields = ['customer__full_name', 'customer__customer_id', 'city_or_town', 'current_city_or_town']

@admin.register(CustomerLoanDetail)
class CustomerLoanDetailAdmin(admin.ModelAdmin):
    list_display = ['loan_application', 'loan_category', 'loan_amount', 'tenure', 'interest_rate', 'emi_amount']
    list_filter = ['loan_category', 'tenure', 'submitted_at', 'agent', 'branch']
    search_fields = ['loan_application__loan_ref_no', 'loan_purpose']

@admin.register(CustomerDocument)
class CustomerDocumentAdmin(admin.ModelAdmin):
    list_display = ['loan_application', 'agent', 'branch', 'submitted_at']
    list_filter = ['submitted_at', 'agent', 'branch']
    search_fields = ['loan_application__loan_ref_no']

@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    list_display = ['loan_application', 'document_type', 'reason', 'requested_by', 'requested_by_hq', 'is_resolved', 'requested_at']
    list_filter = ['document_type', 'reason', 'is_resolved', 'requested_at', 'branch']
    search_fields = ['loan_application__loan_ref_no', 'comment']
    readonly_fields = ['requested_at', 'resolved_at']

@admin.register(DocumentReupload)
class DocumentReuploadAdmin(admin.ModelAdmin):
    list_display = ['loan_application', 'document_type', 'uploaded_by', 'uploaded_at']
    list_filter = ['document_type', 'uploaded_at', 'uploaded_by']
    search_fields = ['loan_application__loan_ref_no', 'agent_note']

@admin.register(DocumentReview)
class DocumentReviewAdmin(admin.ModelAdmin):
    list_display = ['loan_application', 'decision', 'reviewed_by', 'reviewed_at']
    list_filter = ['decision', 'reviewed_at', 'branch']
    search_fields = ['loan_application__loan_ref_no', 'review_comment']
    readonly_fields = ['reviewed_at']

@admin.register(LoanEMISchedule)
class LoanEMIScheduleAdmin(AllFieldsListDisplayAdmin):
    list_filter = ['frequency', 'paid', 'is_overdue', 'reschedule']
    search_fields = ['loan_application__loan_ref_no', 'payment_reference']

@admin.register(EmiCollectionDetail)
class EmiCollectionDetailAdmin(AllFieldsListDisplayAdmin):
    list_filter = ['status', 'payment_mode', 'collected_at']
    search_fields = ['collected_id', 'loan_application__loan_ref_no', 'payment_reference']
    readonly_fields = ['collected_id', 'collected_at', 'verified_at', 'agent_rejected_at']

@admin.register(LoanPeriod)
class LoanPeriodAdmin(AllFieldsListDisplayAdmin):
    search_fields = ['loan_application__loan_ref_no']

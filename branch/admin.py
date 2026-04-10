from django.contrib import admin
from .models import BranchEmployee, BranchPermission, BranchRole

@admin.register(BranchEmployee)
class BranchEmployeeAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'email', 'first_name', 'last_name', 'branch', 'is_active', 'created_at')
    list_filter = ('is_active', 'branch', 'gender', 'gov_id_type')
    search_fields = ('employee_id', 'email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    fieldsets = (
        ('Basic Information', {
            'fields': ('employee_id', 'branch', 'email', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'phone_number', 'address', 'date_of_birth', 'gender')
        }),
        ('Identity Documents', {
            'fields': ('gov_id_type', 'gov_id_number')
        }),
        ('System Information', {
            'fields': ('is_active', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

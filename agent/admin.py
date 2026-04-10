from django.contrib import admin
from .models import Agent

@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ['agent_id', 'full_name', 'email', 'phone', 'branch', 'role', 'status', 'created_at']
    list_filter = ['status', 'role', 'branch', 'created_at']
    search_fields = ['agent_id', 'full_name', 'email', 'phone', 'area']
    readonly_fields = ['agent_id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('agent_id', 'full_name', 'email', 'phone', 'password_hash')
        }),
        ('Branch & Role', {
            'fields': ('branch', 'role', 'area')
        }),
        ('Files', {
            'fields': ('id_proof', 'photo'),
            'classes': ('collapse',)
        }),
        ('Status & Timestamps', {
            'fields': ('status', 'created_at', 'updated_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by when creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

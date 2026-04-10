from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import HeadquarterEmployee, Role, Branch

class RoleTypeFilter(admin.SimpleListFilter):
    title = _('role type')
    parameter_name = 'role_type'

    def lookups(self, request, model_admin):
        return Role.ROLE_TYPES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(role__role_type=self.value())
        return queryset

@admin.register(HeadquarterEmployee)
class HeadquarterEmployeesAdmin(UserAdmin):
    list_display = ('username', 'email', 'get_role_name', 'first_name', 'last_name', 'is_headquater_admin', 'is_active')
    list_filter = ('is_headquater_admin', 'is_active', RoleTypeFilter)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'address')}),
        ('Permissions', {'fields': ('is_active', 'is_headquater_admin', 'role', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    def get_role_name(self, obj):
        return obj.role.name if obj.role else 'No Role'
    get_role_name.short_description = 'Role'

    def get_role_type(self, obj):
        return obj.role.role_type if obj.role else 'No Role'
    get_role_type.short_description = 'Role Type'

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'role_type', 'description')
    list_filter = ('role_type',)
    search_fields = ('name', 'role_type')
    ordering = ('name',)

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('branch_id', 'branch_name', 'address_line_1', 'address_line_2', 'contact_number', 'email', 'manager_id', 'status', 'created_at', 'updated_at', 'created_by')
    search_fields = ('branch_id', 'branch_name', 'address_line_1', 'address_line_2', 'contact_number', 'email', 'manager_id', 'created_by__username')
    list_filter = ('status', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Branch Information', {
            'fields': ('branch_id', 'branch_name', 'address_line_1', 'address_line_2', 'contact_number', 'email', 'manager_id', 'status', 'created_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

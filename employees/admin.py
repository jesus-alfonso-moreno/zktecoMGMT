from django.contrib import admin
from .models import Employee, Fingerprint


class FingerprintInline(admin.TabularInline):
    """Inline admin for fingerprints"""
    model = Fingerprint
    extra = 0
    fields = ['finger_index', 'created_at']
    readonly_fields = ['created_at']


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Admin interface for Employee model"""
    list_display = ['employee_id', 'full_name', 'department', 'user_id', 'is_active', 'synced_to_device', 'device']
    list_filter = ['is_active', 'synced_to_device', 'privilege', 'department', 'device']
    search_fields = ['employee_id', 'first_name', 'last_name', 'department']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [FingerprintInline]

    fieldsets = (
        ('Employee Information', {
            'fields': ('employee_id', 'user_id', 'first_name', 'last_name', 'department')
        }),
        ('Device Settings', {
            'fields': ('card_number', 'password', 'privilege', 'device')
        }),
        ('Status', {
            'fields': ('is_active', 'synced_to_device')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Fingerprint)
class FingerprintAdmin(admin.ModelAdmin):
    """Admin interface for Fingerprint model"""
    list_display = ['employee', 'finger_index', 'created_at']
    list_filter = ['created_at']
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__employee_id']
    readonly_fields = ['created_at']

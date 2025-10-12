from django.contrib import admin
from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """Admin interface for Device model"""
    list_display = ['name', 'ip_address', 'port', 'is_active', 'last_sync', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'ip_address', 'serial_number']
    readonly_fields = ['serial_number', 'firmware_version', 'last_sync', 'created_at', 'updated_at']

    fieldsets = (
        ('Device Information', {
            'fields': ('name', 'ip_address', 'port', 'device_id', 'is_active')
        }),
        ('Device Details', {
            'fields': ('serial_number', 'firmware_version', 'last_sync'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

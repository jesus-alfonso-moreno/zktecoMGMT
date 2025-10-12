from django.contrib import admin
from django.utils.html import format_html
from .models import Device, DeviceLog


class DeviceLogInline(admin.TabularInline):
    """Inline admin for device logs"""
    model = DeviceLog
    extra = 0
    can_delete = False
    fields = ['timestamp', 'action', 'status_badge', 'message', 'duration', 'user']
    readonly_fields = ['timestamp', 'action', 'status_badge', 'message', 'duration', 'user']
    ordering = ['-timestamp']

    def status_badge(self, obj):
        colors = {
            'success': 'green',
            'failed': 'red',
            'error': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """Admin interface for Device model"""
    list_display = ['name', 'ip_address', 'port', 'is_active', 'last_sync', 'log_count', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'ip_address', 'serial_number']
    readonly_fields = ['serial_number', 'firmware_version', 'last_sync', 'created_at', 'updated_at']
    inlines = [DeviceLogInline]

    fieldsets = (
        ('Device Information', {
            'fields': ('name', 'ip_address', 'port', 'device_id', 'is_active')
        }),
        ('Authentication & Connection', {
            'fields': ('password', 'force_udp', 'ommit_ping'),
            'description': 'Optional connection settings for devices requiring authentication or special protocols'
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

    def log_count(self, obj):
        return obj.logs.count()
    log_count.short_description = 'Logs'


@admin.register(DeviceLog)
class DeviceLogAdmin(admin.ModelAdmin):
    """Admin interface for DeviceLog model"""
    list_display = ['timestamp', 'device', 'action', 'status_badge', 'user', 'duration_display', 'ip_address']
    list_filter = ['status', 'action', 'device', 'timestamp']
    search_fields = ['device__name', 'message', 'user__username']
    readonly_fields = ['device', 'action', 'status', 'user', 'message', 'details', 'ip_address', 'duration', 'timestamp']
    date_hierarchy = 'timestamp'

    fieldsets = (
        ('Log Information', {
            'fields': ('device', 'action', 'status', 'timestamp')
        }),
        ('Details', {
            'fields': ('message', 'details', 'duration')
        }),
        ('User Information', {
            'fields': ('user', 'ip_address')
        }),
    )

    def status_badge(self, obj):
        colors = {
            'success': 'green',
            'failed': 'red',
            'error': 'orange'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def duration_display(self, obj):
        if obj.duration:
            return f"{obj.duration:.2f}s"
        return "-"
    duration_display.short_description = 'Duration'

    def has_add_permission(self, request):
        # Logs should only be created by the system
        return False

    def has_delete_permission(self, request, obj=None):
        # Allow deletion for cleanup
        return request.user.is_superuser

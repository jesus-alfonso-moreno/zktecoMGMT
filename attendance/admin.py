from django.contrib import admin
from .models import AttendanceEvent


@admin.register(AttendanceEvent)
class AttendanceEventAdmin(admin.ModelAdmin):
    """Admin interface for AttendanceEvent model"""
    list_display = ['timestamp', 'employee', 'user_id', 'punch_type', 'verify_mode', 'device']
    list_filter = ['punch_type', 'verify_mode', 'device', 'timestamp']
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__employee_id', 'user_id']
    readonly_fields = ['created_at']
    date_hierarchy = 'timestamp'

    fieldsets = (
        ('Event Information', {
            'fields': ('device', 'employee', 'user_id', 'timestamp')
        }),
        ('Event Details', {
            'fields': ('punch_type', 'verify_mode', 'work_code')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Attendance events should come from device, not added manually
        return False

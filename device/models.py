from django.db import models
from django.contrib.auth.models import User


class Device(models.Model):
    """Stores ZKTeco K40 device connection information"""
    name = models.CharField(max_length=100)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField(default=4370)
    device_id = models.IntegerField(default=1)
    password = models.CharField(max_length=50, blank=True, help_text="Device communication password (optional)")
    force_udp = models.BooleanField(default=False, help_text="Force UDP protocol instead of TCP")
    ommit_ping = models.BooleanField(default=False, help_text="Skip ping test before connecting")
    serial_number = models.CharField(max_length=100, blank=True)
    firmware_version = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_sync = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        permissions = [
            ('view_device_section', 'Can access device management section'),
            ('manage_devices', 'Can manage device configurations'),
        ]

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class DeviceLog(models.Model):
    """Logs all device connection attempts and operations"""

    ACTION_CHOICES = (
        ('connect', 'Connection Attempt'),
        ('test', 'Connection Test'),
        ('sync_employees_to', 'Sync Employees To Device'),
        ('sync_employees_from', 'Sync Employees From Device'),
        ('download_attendance', 'Download Attendance'),
        ('get_info', 'Get Device Info'),
        ('clear_attendance', 'Clear Attendance'),
    )

    STATUS_CHOICES = (
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('error', 'Error'),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)  # Additional data like counts, errors
    ip_address = models.GenericIPAddressField(null=True, blank=True)  # User's IP who triggered action
    duration = models.FloatField(null=True, blank=True)  # Operation duration in seconds
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Device Log'
        verbose_name_plural = 'Device Logs'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['device', '-timestamp']),
            models.Index(fields=['status', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]

    def __str__(self):
        return f"{self.device.name} - {self.get_action_display()} - {self.status} - {self.timestamp}"

    @property
    def is_success(self):
        return self.status == 'success'

    @property
    def is_failed(self):
        return self.status in ['failed', 'error']

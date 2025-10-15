from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class Device(models.Model):
    """Stores ZKTeco K40 device connection information"""
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    ip_address = models.GenericIPAddressField(verbose_name=_("IP Address"))
    port = models.IntegerField(default=4370, verbose_name=_("Port"))
    device_id = models.IntegerField(default=1, verbose_name=_("Device ID"))
    password = models.CharField(max_length=50, blank=True, verbose_name=_("Password"), help_text=_("Device communication password (optional)"))
    force_udp = models.BooleanField(default=False, verbose_name=_("Force UDP"), help_text=_("Force UDP protocol instead of TCP"))
    ommit_ping = models.BooleanField(default=False, verbose_name=_("Omit Ping"), help_text=_("Skip ping test before connecting"))
    serial_number = models.CharField(max_length=100, blank=True, verbose_name=_("Serial Number"))
    firmware_version = models.CharField(max_length=50, blank=True, verbose_name=_("Firmware Version"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    last_sync = models.DateTimeField(null=True, blank=True, verbose_name=_("Last Sync"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('Device')
        verbose_name_plural = _('Devices')
        permissions = [
            ('view_device_section', 'Can access device management section'),
            ('manage_devices', 'Can manage device configurations'),
        ]

    def __str__(self):
        return f"{self.name} ({self.ip_address})"


class DeviceLog(models.Model):
    """Logs all device connection attempts and operations"""

    ACTION_CHOICES = (
        ('connect', _('Connection Attempt')),
        ('test', _('Connection Test')),
        ('sync_employees_to', _('Sync Employees To Device')),
        ('sync_employees_from', _('Sync Employees From Device')),
        ('download_attendance', _('Download Attendance')),
        ('get_info', _('Get Device Info')),
        ('clear_attendance', _('Clear Attendance')),
    )

    STATUS_CHOICES = (
        ('success', _('Success')),
        ('failed', _('Failed')),
        ('error', _('Error')),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='logs', verbose_name=_("Device"))
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, verbose_name=_("Action"))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, verbose_name=_("Status"))
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("User"))
    message = models.TextField(blank=True, verbose_name=_("Message"))
    details = models.JSONField(default=dict, blank=True, verbose_name=_("Details"))
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_("IP Address"))
    duration = models.FloatField(null=True, blank=True, verbose_name=_("Duration (seconds)"))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_("Timestamp"))

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Device Log')
        verbose_name_plural = _('Device Logs')
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

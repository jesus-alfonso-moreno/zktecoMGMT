from django.db import models
from django.utils.translation import gettext_lazy as _
from device.models import Device
from employees.models import Employee


class AttendanceEvent(models.Model):
    """Attendance punch events from device"""
    PUNCH_TYPES = (
        (0, _('Check In')),
        (1, _('Check Out')),
        (2, _('Break Out')),
        (3, _('Break In')),
        (4, _('Overtime In')),
        (5, _('Overtime Out')),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE, verbose_name=_("Device"))
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Employee"))
    user_id = models.IntegerField(verbose_name=_("User ID"), help_text=_("Device user ID"))
    timestamp = models.DateTimeField(verbose_name=_("Timestamp"))
    punch_type = models.IntegerField(choices=PUNCH_TYPES, default=0, verbose_name=_("Punch Type"))
    verify_mode = models.IntegerField(default=0, verbose_name=_("Verify Mode"), help_text=_("1=Fingerprint, 2=Card, etc."))
    work_code = models.IntegerField(default=0, verbose_name=_("Work Code"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))

    class Meta:
        unique_together = ['device', 'user_id', 'timestamp']
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['employee', '-timestamp']),
        ]
        verbose_name = _('Attendance Event')
        verbose_name_plural = _('Attendance Events')
        permissions = [
            ('view_attendance_section', 'Can access attendance tracking section'),
            ('manage_attendance', 'Can manage attendance data'),
            ('download_attendance', 'Can download attendance from devices'),
        ]

    def __str__(self):
        employee_name = self.employee.full_name if self.employee else f'User {self.user_id}'
        return f"{employee_name} - {self.get_punch_type_display()} at {self.timestamp}"

    def get_verify_mode_display_custom(self):
        """Get human-readable verify mode"""
        modes = {
            0: _('Password'),
            1: _('Fingerprint'),
            2: _('Card'),
            3: _('Face'),
            4: _('Iris'),
            15: _('Others'),
        }
        return modes.get(self.verify_mode, _('Unknown'))

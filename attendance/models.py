from django.db import models
from device.models import Device
from employees.models import Employee


class AttendanceEvent(models.Model):
    """Attendance punch events from device"""
    PUNCH_TYPES = (
        (0, 'Check In'),
        (1, 'Check Out'),
        (2, 'Break Out'),
        (3, 'Break In'),
        (4, 'Overtime In'),
        (5, 'Overtime Out'),
    )

    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True)
    user_id = models.IntegerField()  # Device user ID
    timestamp = models.DateTimeField()
    punch_type = models.IntegerField(choices=PUNCH_TYPES, default=0)
    verify_mode = models.IntegerField(default=0)  # 1=Fingerprint, 2=Card, etc.
    work_code = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['device', 'user_id', 'timestamp']
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['employee', '-timestamp']),
        ]
        verbose_name = 'Attendance Event'
        verbose_name_plural = 'Attendance Events'
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
            0: 'Password',
            1: 'Fingerprint',
            2: 'Card',
            3: 'Face',
            4: 'Iris',
            15: 'Others',
        }
        return modes.get(self.verify_mode, 'Unknown')

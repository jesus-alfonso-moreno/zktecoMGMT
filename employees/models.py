from django.db import models
from device.models import Device


class Employee(models.Model):
    """Employee/User that exists in Django and on device"""
    user_id = models.IntegerField(unique=True)  # Device user ID (1-65535)
    employee_id = models.CharField(max_length=50, unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    department = models.CharField(max_length=100, blank=True)
    card_number = models.CharField(max_length=50, blank=True)
    password = models.CharField(max_length=50, blank=True)  # Device password, not web login
    privilege = models.IntegerField(default=0)  # 0=User, 14=Admin
    is_active = models.BooleanField(default=True)
    synced_to_device = models.BooleanField(default=False)
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_id']
        verbose_name = 'Employee'
        verbose_name_plural = 'Employees'
        permissions = [
            ('view_employee_section', 'Can access employee management section'),
            ('manage_employees', 'Can manage employee data'),
            ('manage_fingerprints', 'Can manage employee fingerprints'),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.employee_id})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class Fingerprint(models.Model):
    """Stores fingerprint templates for employees"""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='fingerprints')
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    finger_index = models.IntegerField()  # 0-9 for 10 fingers
    template = models.BinaryField()  # Binary fingerprint template data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['employee', 'finger_index']
        verbose_name = 'Fingerprint'
        verbose_name_plural = 'Fingerprints'

    def __str__(self):
        return f"{self.employee.full_name} - Finger {self.finger_index}"

from django.db import models
from django.utils.translation import gettext_lazy as _
from device.models import Device


class Employee(models.Model):
    """Employee/User that exists in Django and on device"""
    user_id = models.IntegerField(unique=True, verbose_name=_("User ID"), help_text=_("Device user ID (1-65535)"))
    employee_id = models.CharField(max_length=50, unique=True, verbose_name=_("Employee ID"))
    first_name = models.CharField(max_length=100, verbose_name=_("First Name"))
    last_name = models.CharField(max_length=100, verbose_name=_("Last Name"))
    department = models.CharField(max_length=100, blank=True, verbose_name=_("Department"))
    card_number = models.CharField(max_length=50, blank=True, verbose_name=_("Card Number"))
    password = models.CharField(max_length=50, blank=True, verbose_name=_("Device Password"), help_text=_("Device password, not web login"))
    privilege = models.IntegerField(default=0, verbose_name=_("Privilege"), help_text=_("0=User, 14=Admin"))
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))
    synced_to_device = models.BooleanField(default=False, verbose_name=_("Synced to Device"))
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Device"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        ordering = ['employee_id']
        verbose_name = _('Employee')
        verbose_name_plural = _('Employees')
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
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='fingerprints', verbose_name=_("Employee"))
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Device"))
    finger_index = models.IntegerField(verbose_name=_("Finger Index"), help_text=_("0-9 for 10 fingers"))
    template = models.BinaryField(verbose_name=_("Template"), help_text=_("Binary fingerprint template data"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created At"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated At"))

    class Meta:
        unique_together = ['employee', 'finger_index']
        verbose_name = _('Fingerprint')
        verbose_name_plural = _('Fingerprints')

    def __str__(self):
        return f"{self.employee.full_name} - Finger {self.finger_index}"

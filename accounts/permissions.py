"""
Permission mixins and decorators for role-based access control
"""
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from functools import wraps


# Reusable mixins for class-based views
class DeviceSectionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Require login and device section access permission"""
    permission_required = 'device.view_device_section'
    permission_denied_message = 'You do not have permission to access the device management section.'


class EmployeeSectionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Require login and employee section access permission"""
    permission_required = 'employees.view_employee_section'
    permission_denied_message = 'You do not have permission to access the employee management section.'


class AttendanceSectionMixin(LoginRequiredMixin, PermissionRequiredMixin):
    """Require login and attendance section access permission"""
    permission_required = 'attendance.view_attendance_section'
    permission_denied_message = 'You do not have permission to access the attendance tracking section.'


# Decorators for function-based views
def device_section_required(view_func):
    """Decorator to require device section permission"""
    @wraps(view_func)
    @login_required
    @permission_required('device.view_device_section', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


def employee_section_required(view_func):
    """Decorator to require employee section permission"""
    @wraps(view_func)
    @login_required
    @permission_required('employees.view_employee_section', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


def attendance_section_required(view_func):
    """Decorator to require attendance section permission"""
    @wraps(view_func)
    @login_required
    @permission_required('attendance.view_attendance_section', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


def manage_devices_required(view_func):
    """Decorator to require device management permission"""
    @wraps(view_func)
    @login_required
    @permission_required('device.manage_devices', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


def manage_employees_required(view_func):
    """Decorator to require employee management permission"""
    @wraps(view_func)
    @login_required
    @permission_required('employees.manage_employees', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


def manage_fingerprints_required(view_func):
    """Decorator to require fingerprint management permission"""
    @wraps(view_func)
    @login_required
    @permission_required('employees.manage_fingerprints', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


def manage_attendance_required(view_func):
    """Decorator to require attendance management permission"""
    @wraps(view_func)
    @login_required
    @permission_required('attendance.manage_attendance', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper


def download_attendance_required(view_func):
    """Decorator to require attendance download permission"""
    @wraps(view_func)
    @login_required
    @permission_required('attendance.download_attendance', raise_exception=True)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapper

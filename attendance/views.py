from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.generic import ListView
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from datetime import datetime, timedelta
import csv

from .models import AttendanceEvent
from .reports import get_daily_summary, get_weekly_summary, get_monthly_summary
from employees.models import Employee
from device.models import Device
from device.zk_connector import ZKDeviceConnector
from accounts.permissions import (
    AttendanceSectionMixin, attendance_section_required,
    download_attendance_required, manage_attendance_required
)


class AttendanceListView(AttendanceSectionMixin, ListView):
    """List all attendance events with filters"""
    model = AttendanceEvent
    template_name = 'attendance/attendance_list.html'
    context_object_name = 'events'
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().select_related('employee', 'device')

        # Filter by employee
        employee_id = self.request.GET.get('employee')
        if employee_id:
            queryset = queryset.filter(employee_id=employee_id)

        # Filter by device
        device_id = self.request.GET.get('device')
        if device_id:
            queryset = queryset.filter(device_id=device_id)

        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            queryset = queryset.filter(timestamp__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__lte=date_to)

        # Filter by punch type
        punch_type = self.request.GET.get('punch_type')
        if punch_type:
            queryset = queryset.filter(punch_type=punch_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['employees'] = Employee.objects.filter(is_active=True)
        context['devices'] = Device.objects.filter(is_active=True)
        context['punch_types'] = AttendanceEvent.PUNCH_TYPES
        return context


@download_attendance_required
def download_attendance(request):
    """Download attendance events from device"""
    device_id = request.GET.get('device')
    if not device_id:
        messages.error(request, 'Please select a device')
        return redirect('attendance:attendance_list')

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        messages.error(request, 'Device not found')
        return redirect('attendance:attendance_list')

    connector = ZKDeviceConnector(device)

    success_count = 0
    error_count = 0
    duplicate_count = 0

    try:
        conn = connector.connect()
        attendance_records = connector.get_attendance(conn)
        conn.disconnect()

        for record in attendance_records:
            try:
                # Try to match employee
                employee = None
                try:
                    employee = Employee.objects.get(user_id=record.user_id)
                except Employee.DoesNotExist:
                    pass

                # Create or skip if duplicate
                _, created = AttendanceEvent.objects.get_or_create(
                    device=device,
                    user_id=record.user_id,
                    timestamp=record.timestamp,
                    defaults={
                        'employee': employee,
                        'punch_type': record.punch,
                        'verify_mode': getattr(record, 'status', 0),
                        'work_code': 0,
                    }
                )

                if created:
                    success_count += 1
                else:
                    duplicate_count += 1

            except Exception as e:
                error_count += 1

        device.last_sync = timezone.now()
        device.save()

        if success_count > 0:
            messages.success(request, f'Downloaded {success_count} new attendance events')
        if duplicate_count > 0:
            messages.info(request, f'{duplicate_count} duplicate events skipped')
        if error_count > 0:
            messages.warning(request, f'{error_count} events failed to import')

    except Exception as e:
        messages.error(request, f'Error connecting to device: {str(e)}')

    return redirect('attendance:attendance_list')


@attendance_section_required
def attendance_report(request):
    """Generate attendance reports"""
    report_type = request.GET.get('type', 'daily')
    employee_id = request.GET.get('employee')
    device_id = request.GET.get('device')
    date_str = request.GET.get('date', datetime.now().strftime('%Y-%m-%d'))

    employee = None
    device = None
    summary = {}

    if employee_id:
        try:
            employee = Employee.objects.get(pk=employee_id)
        except Employee.DoesNotExist:
            pass

    if device_id:
        try:
            device = Device.objects.get(pk=device_id)
        except Device.DoesNotExist:
            pass

    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = datetime.now().date()

    if report_type == 'daily':
        summary = get_daily_summary(date, employee, device)
    elif report_type == 'weekly':
        summary = get_weekly_summary(date, employee, device)
    elif report_type == 'monthly':
        summary = get_monthly_summary(date.year, date.month, employee, device)

    context = {
        'report_type': report_type,
        'date': date,
        'summary': summary,
        'employee': employee,
        'device': device,
        'employees': Employee.objects.filter(is_active=True),
        'devices': Device.objects.filter(is_active=True),
    }
    return render(request, 'attendance/attendance_report.html', context)


@attendance_section_required
def export_attendance(request):
    """Export attendance events to CSV"""
    # Get filtered queryset
    queryset = AttendanceEvent.objects.all().select_related('employee', 'device')

    employee_id = request.GET.get('employee')
    if employee_id:
        queryset = queryset.filter(employee_id=employee_id)

    device_id = request.GET.get('device')
    if device_id:
        queryset = queryset.filter(device_id=device_id)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        queryset = queryset.filter(timestamp__gte=date_from)
    if date_to:
        queryset = queryset.filter(timestamp__lte=date_to)

    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Date',
        'Time',
        'Employee ID',
        'Employee Name',
        'User ID',
        'Punch Type',
        'Verify Mode',
        'Device'
    ])

    for event in queryset:
        writer.writerow([
            event.timestamp.strftime('%Y-%m-%d'),
            event.timestamp.strftime('%H:%M:%S'),
            event.employee.employee_id if event.employee else '',
            event.employee.full_name if event.employee else f'User {event.user_id}',
            event.user_id,
            event.get_punch_type_display(),
            event.get_verify_mode_display_custom(),
            event.device.name
        ])

    return response

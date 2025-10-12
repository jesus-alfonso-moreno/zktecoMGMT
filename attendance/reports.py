"""
Helper functions for generating attendance reports
"""
from datetime import datetime, timedelta
from django.db.models import Count, Q
from django.utils import timezone
from .models import AttendanceEvent


def get_daily_summary(date, employee=None, device=None):
    """Get attendance summary for a specific day"""
    start = datetime.combine(date, datetime.min.time())
    end = datetime.combine(date, datetime.max.time())

    events = AttendanceEvent.objects.filter(
        timestamp__range=(start, end)
    )

    if employee:
        events = events.filter(employee=employee)
    if device:
        events = events.filter(device=device)

    # Group by employee
    summary = {}
    for event in events.select_related('employee'):
        emp_id = event.employee.id if event.employee else event.user_id
        emp_name = event.employee.full_name if event.employee else f'User {event.user_id}'

        if emp_id not in summary:
            summary[emp_id] = {
                'employee': event.employee,
                'name': emp_name,
                'check_in': None,
                'check_out': None,
                'events': []
            }

        summary[emp_id]['events'].append(event)

        # Track first check-in and last check-out
        if event.punch_type == 0:  # Check In
            if not summary[emp_id]['check_in']:
                summary[emp_id]['check_in'] = event.timestamp
        elif event.punch_type == 1:  # Check Out
            summary[emp_id]['check_out'] = event.timestamp

    # Calculate work hours
    for emp_id, data in summary.items():
        if data['check_in'] and data['check_out']:
            delta = data['check_out'] - data['check_in']
            data['hours_worked'] = delta.total_seconds() / 3600
        else:
            data['hours_worked'] = 0

    return summary


def get_weekly_summary(start_date, employee=None, device=None):
    """Get attendance summary for a week"""
    end_date = start_date + timedelta(days=7)

    events = AttendanceEvent.objects.filter(
        timestamp__range=(start_date, end_date)
    )

    if employee:
        events = events.filter(employee=employee)
    if device:
        events = events.filter(device=device)

    # Group by employee and day
    summary = {}
    for event in events.select_related('employee'):
        emp_id = event.employee.id if event.employee else event.user_id
        day = event.timestamp.date()

        if emp_id not in summary:
            summary[emp_id] = {
                'employee': event.employee,
                'name': event.employee.full_name if event.employee else f'User {event.user_id}',
                'days': {},
                'total_days': 0,
                'total_hours': 0,
            }

        if day not in summary[emp_id]['days']:
            summary[emp_id]['days'][day] = {
                'check_in': None,
                'check_out': None,
                'hours': 0
            }

        if event.punch_type == 0:
            summary[emp_id]['days'][day]['check_in'] = event.timestamp
        elif event.punch_type == 1:
            summary[emp_id]['days'][day]['check_out'] = event.timestamp

    # Calculate totals
    for emp_id, data in summary.items():
        for day, day_data in data['days'].items():
            if day_data['check_in'] and day_data['check_out']:
                delta = day_data['check_out'] - day_data['check_in']
                day_data['hours'] = delta.total_seconds() / 3600
                data['total_hours'] += day_data['hours']
                data['total_days'] += 1

    return summary


def get_monthly_summary(year, month, employee=None, device=None):
    """Get attendance summary for a month"""
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)

    events = AttendanceEvent.objects.filter(
        timestamp__range=(start_date, end_date)
    )

    if employee:
        events = events.filter(employee=employee)
    if device:
        events = events.filter(device=device)

    # Count days present
    summary = {}
    for event in events.select_related('employee'):
        emp_id = event.employee.id if event.employee else event.user_id
        day = event.timestamp.date()

        if emp_id not in summary:
            summary[emp_id] = {
                'employee': event.employee,
                'name': event.employee.full_name if event.employee else f'User {event.user_id}',
                'days_present': set(),
                'total_events': 0,
            }

        summary[emp_id]['days_present'].add(day)
        summary[emp_id]['total_events'] += 1

    # Convert sets to counts
    for emp_id, data in summary.items():
        data['days_present'] = len(data['days_present'])

    return summary


def get_employee_attendance_rate(employee, start_date, end_date):
    """Calculate attendance rate for an employee"""
    total_days = (end_date - start_date).days
    work_days = total_days  # Simplified - could exclude weekends

    events = AttendanceEvent.objects.filter(
        employee=employee,
        timestamp__range=(start_date, end_date),
        punch_type=0  # Count check-ins
    )

    days_present = events.values('timestamp__date').distinct().count()

    attendance_rate = (days_present / work_days * 100) if work_days > 0 else 0

    return {
        'total_days': total_days,
        'days_present': days_present,
        'days_absent': work_days - days_present,
        'attendance_rate': attendance_rate
    }

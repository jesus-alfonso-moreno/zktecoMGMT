"""
Helper functions for generating attendance reports with event pairing logic
"""
from datetime import datetime, timedelta, time
from django.db.models import Count, Q
from django.utils import timezone
from .models import AttendanceEvent


def filter_working_hours(events):
    """
    Filter events to only include those between 6:00 and 22:00

    Args:
        events: QuerySet of AttendanceEvent objects

    Returns:
        Filtered list of events within working hours
    """
    filtered = []
    for event in events:
        event_time = event.timestamp.time()
        if time(6, 0) <= event_time <= time(22, 0):
            filtered.append(event)
    return filtered


def pair_events(events):
    """
    Pair attendance events using sequential pairing logic.
    - Events are ordered by timestamp
    - Pair 1st with 2nd, 3rd with 4th, etc.
    - If delta between pair is < 30 minutes, skip the 2nd event and pair 1st with 3rd

    Args:
        events: List of AttendanceEvent objects for a single employee/day

    Returns:
        List of tuples: [(event1, event2, duration_minutes), ...]
    """
    if len(events) < 2:
        return []

    # Sort events by timestamp
    sorted_events = sorted(events, key=lambda e: e.timestamp)

    pairs = []
    i = 0

    while i < len(sorted_events) - 1:
        first_event = sorted_events[i]
        j = i + 1

        # Try to find a valid pair
        while j < len(sorted_events):
            second_event = sorted_events[j]
            delta = second_event.timestamp - first_event.timestamp
            delta_minutes = delta.total_seconds() / 60

            # If delta is at least 30 minutes, we have a valid pair
            if delta_minutes >= 30:
                pairs.append((first_event, second_event, delta_minutes))
                i = j + 1  # Move to next unpaired event
                break
            else:
                # Skip this event and try the next one
                j += 1

        # If no valid pair found, move to next event
        if j >= len(sorted_events):
            i += 1

    return pairs


def get_daily_summary(date, employee=None, device=None):
    """
    Get attendance summary for a specific day with event pairing

    Args:
        date: Date object for the day
        employee: Optional Employee filter
        device: Optional Device filter

    Returns:
        Dictionary with employee summaries including paired events
    """
    start = datetime.combine(date, datetime.min.time())
    end = datetime.combine(date, datetime.max.time())

    events = AttendanceEvent.objects.filter(
        timestamp__range=(start, end)
    ).select_related('employee', 'device').order_by('employee', 'timestamp')

    if employee:
        events = events.filter(employee=employee)
    if device:
        events = events.filter(device=device)

    # Filter to working hours (6:00-22:00)
    events = filter_working_hours(events)

    # Group by employee
    employee_events = {}
    for event in events:
        emp_id = event.employee.id if event.employee else f'user_{event.user_id}'
        if emp_id not in employee_events:
            employee_events[emp_id] = {
                'employee': event.employee,
                'name': event.employee.full_name if event.employee else f'User {event.user_id}',
                'events': []
            }
        employee_events[emp_id]['events'].append(event)

    # Generate summary with pairs
    summary = {}
    for emp_id, data in employee_events.items():
        pairs = pair_events(data['events'])

        # Calculate totals
        total_work_minutes = sum(duration for _, _, duration in pairs)
        total_work_hours = total_work_minutes / 60

        summary[emp_id] = {
            'employee': data['employee'],
            'name': data['name'],
            'date': date,
            'pairs': pairs,
            'total_pairs': len(pairs),
            'total_work_minutes': total_work_minutes,
            'total_work_hours': round(total_work_hours, 2),
            'first_entry': pairs[0][0].timestamp if pairs else None,
            'last_exit': pairs[-1][1].timestamp if pairs else None,
            'unpaired_events': len(data['events']) - (len(pairs) * 2),
        }

    return summary


def get_date_range_summary(start_date, end_date, employee=None, device=None):
    """
    Get attendance summary for a date range, grouped by date and employee

    Args:
        start_date: Start date
        end_date: End date
        employee: Optional Employee filter
        device: Optional Device filter

    Returns:
        Dictionary with date -> employee summaries
    """
    start = datetime.combine(start_date, datetime.min.time())
    end = datetime.combine(end_date, datetime.max.time())

    events = AttendanceEvent.objects.filter(
        timestamp__range=(start, end)
    ).select_related('employee', 'device').order_by('timestamp')

    if employee:
        events = events.filter(employee=employee)
    if device:
        events = events.filter(device=device)

    # Filter to working hours
    events = filter_working_hours(events)

    # Group by date and employee
    date_employee_events = {}
    for event in events:
        event_date = event.timestamp.date()
        emp_id = event.employee.id if event.employee else f'user_{event.user_id}'

        if event_date not in date_employee_events:
            date_employee_events[event_date] = {}

        if emp_id not in date_employee_events[event_date]:
            date_employee_events[event_date][emp_id] = {
                'employee': event.employee,
                'name': event.employee.full_name if event.employee else f'User {event.user_id}',
                'events': []
            }

        date_employee_events[event_date][emp_id]['events'].append(event)

    # Generate summary with pairs for each date/employee combination
    summary = {}
    for date, employees in sorted(date_employee_events.items()):
        summary[date] = {}

        for emp_id, data in employees.items():
            pairs = pair_events(data['events'])

            total_work_minutes = sum(duration for _, _, duration in pairs)
            total_work_hours = total_work_minutes / 60

            summary[date][emp_id] = {
                'employee': data['employee'],
                'name': data['name'],
                'date': date,
                'pairs': pairs,
                'total_pairs': len(pairs),
                'total_work_minutes': total_work_minutes,
                'total_work_hours': round(total_work_hours, 2),
                'first_entry': pairs[0][0].timestamp if pairs else None,
                'last_exit': pairs[-1][1].timestamp if pairs else None,
                'unpaired_events': len(data['events']) - (len(pairs) * 2),
            }

    return summary


def get_weekly_summary(start_date, employee=None, device=None):
    """Get attendance summary for a week"""
    end_date = start_date + timedelta(days=7)
    return get_date_range_summary(start_date, end_date, employee, device)


def get_monthly_summary(year, month, employee=None, device=None):
    """Get attendance summary for a month"""
    start_date = datetime(year, month, 1).date()
    if month == 12:
        end_date = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        end_date = datetime(year, month + 1, 1).date() - timedelta(days=1)

    return get_date_range_summary(start_date, end_date, employee, device)


def get_employee_summary_for_period(employee, start_date, end_date):
    """
    Get summary statistics for a single employee across a date range

    Returns:
        Dictionary with aggregate statistics
    """
    date_range_data = get_date_range_summary(start_date, end_date, employee=employee)

    total_days_present = len(date_range_data)
    total_work_hours = 0
    total_pairs = 0

    for date, employees in date_range_data.items():
        for emp_id, data in employees.items():
            total_work_hours += data['total_work_hours']
            total_pairs += data['total_pairs']

    total_days_in_range = (end_date - start_date).days + 1

    return {
        'employee': employee,
        'start_date': start_date,
        'end_date': end_date,
        'total_days_in_range': total_days_in_range,
        'days_present': total_days_present,
        'days_absent': total_days_in_range - total_days_present,
        'attendance_rate': round((total_days_present / total_days_in_range * 100), 2) if total_days_in_range > 0 else 0,
        'total_work_hours': round(total_work_hours, 2),
        'average_hours_per_day': round(total_work_hours / total_days_present, 2) if total_days_present > 0 else 0,
        'total_clock_pairs': total_pairs,
    }

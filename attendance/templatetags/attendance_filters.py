"""
Custom template filters for attendance app
"""
from django import template

register = template.Library()


@register.filter
def minutes_to_hours_minutes(minutes):
    """
    Convert minutes to formatted hours and minutes string

    Example:
        90 -> "1h 30m"
        120 -> "2h 0m"
        45 -> "0h 45m"
    """
    if not minutes:
        return "0h 0m"

    hours = int(minutes // 60)
    remaining_minutes = int(minutes % 60)

    return f"{hours}h {remaining_minutes}m"

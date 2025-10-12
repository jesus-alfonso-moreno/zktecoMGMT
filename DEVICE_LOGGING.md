# Device Authentication Logging

This document describes the device authentication and operation logging system.

## Overview

The ZKTeco K40 Django project now includes comprehensive logging for all device operations, including:
- Connection attempts (success/failure)
- Employee synchronization
- Attendance downloads
- Device information retrieval

## Logging Locations

### 1. Database Logs (`DeviceLog` Model)

All device operations are logged to the database in the `device_devicelog` table.

**Fields:**
- `device` - The device being accessed
- `action` - Type of operation (connect, test, sync_employees_to, sync_employees_from, download_attendance, get_info, clear_attendance)
- `status` - Operation status (success, failed, error)
- `user` - Django user who triggered the operation (if applicable)
- `message` - Human-readable log message
- `details` - JSON field with additional data (counts, errors, etc.)
- `ip_address` - IP address of user who triggered the operation
- `duration` - Operation duration in seconds
- `timestamp` - When the operation occurred

**Viewing Logs:**
1. **Django Admin**: `/admin/device/devicelog/`
   - Filterable by status, action, device, date
   - Searchable by device name, message, username
   - Color-coded status badges
   - Duration displayed in seconds

2. **Device Detail Page**: Each device in admin shows recent logs inline

### 2. File Logs

Logs are written to rotating log files in the `logs/` directory:

**`logs/device_auth.log`**
- All device operations (INFO level and above)
- Connection attempts
- Sync operations
- Format: `[LEVEL] YYYY-MM-DD HH:MM:SS logger_name message`
- Rotates at 10MB, keeps 5 backups

**`logs/device_errors.log`**
- Only ERROR level messages
- Connection failures
- Operation errors
- Same format and rotation as above

### 3. Console Output

When running `python manage.py runserver` or management commands, logs are printed to console with simplified format.

## Log Levels

- **INFO**: Successful operations, connection attempts
- **WARNING**: Partial failures, deprecated features
- **ERROR**: Connection failures, operation errors
- **DEBUG**: Detailed debugging information (not enabled by default)

## Example Log Entries

### Successful Connection Test
```
Database:
- device: Main Office K40
- action: test
- status: success
- message: Connection successful
- duration: 0.15
- timestamp: 2024-10-12 10:30:45

File (device_auth.log):
[INFO] 2024-10-12 10:30:45 device.auth ✓ Connection successful (took 0.15s)
```

### Failed Connection
```
Database:
- device: Branch Office K40
- action: test
- status: failed
- message: Connection timeout
- duration: 5.02
- timestamp: 2024-10-12 10:31:10

File (device_errors.log):
[ERROR] 2024-10-12 10:31:10 device.auth ✗ Connection failed: Connection timeout
```

### Employee Sync
```
Database:
- device: Main Office K40
- action: sync_employees_to
- status: success
- message: Successfully synced 25 employees
- details: {"success_count": 25, "error_count": 0}
- duration: 2.34
- timestamp: 2024-10-12 10:35:20
```

## Querying Logs

### Django ORM Examples

```python
from device.models import DeviceLog, Device

# Get all failed operations
failed_logs = DeviceLog.objects.filter(status='failed')

# Get logs for specific device
device = Device.objects.get(name='Main Office K40')
device_logs = device.logs.all()

# Get connection attempts in last 24 hours
from django.utils import timezone
from datetime import timedelta
recent = DeviceLog.objects.filter(
    action='test',
    timestamp__gte=timezone.now() - timedelta(days=1)
)

# Get failed operations with details
failures = DeviceLog.objects.filter(
    status__in=['failed', 'error']
).select_related('device', 'user')

# Statistics
from django.db.models import Count
stats = DeviceLog.objects.values('status').annotate(count=Count('id'))
```

### Admin Filters

In Django admin (`/admin/device/devicelog/`), you can filter by:
- Status (success/failed/error)
- Action type
- Device
- Date (using date hierarchy)

Search by:
- Device name
- Log message
- Username

## Configuration

### Enable/Disable File Logging

Edit `zkteco_project/settings.py`:

```python
LOGGING = {
    'loggers': {
        'device.auth': {
            'handlers': ['console', 'device_file', 'device_error_file'],  # Remove handlers to disable
            'level': 'INFO',  # Change to DEBUG for more verbose logging
        },
    },
}
```

### Change Log File Location

```python
'device_file': {
    'filename': BASE_DIR / 'custom_logs' / 'device.log',  # Custom path
},
```

### Log Retention

Log files rotate automatically:
- **Max Size**: 10 MB per file
- **Backups**: 5 files kept
- **Total**: Up to 50 MB per log type

To change:
```python
'device_file': {
    'maxBytes': 1024 * 1024 * 20,  # 20 MB
    'backupCount': 10,  # Keep 10 backups
},
```

### Database Log Cleanup

Create a management command or scheduled task to clean old logs:

```python
from datetime import timedelta
from django.utils import timezone
from device.models import DeviceLog

# Delete logs older than 90 days
DeviceLog.objects.filter(
    timestamp__lt=timezone.now() - timedelta(days=90)
).delete()
```

## Viewing Logs

### 1. Django Admin (Web Interface)

Visit `/admin/device/devicelog/` to:
- Browse all logs with pagination
- Filter by status, action, device, date
- Search logs
- View details including JSON data
- See color-coded status indicators

### 2. Command Line (Log Files)

```bash
# View recent logs
tail -f logs/device_auth.log

# Search for errors
grep ERROR logs/device_errors.log

# View logs from specific date
grep "2024-10-12" logs/device_auth.log

# Count failed connections
grep "Connection failed" logs/device_auth.log | wc -l
```

### 3. Python Shell

```bash
python manage.py shell
```

```python
from device.models import DeviceLog

# Recent 10 logs
for log in DeviceLog.objects.all()[:10]:
    print(f"{log.timestamp} - {log.device.name} - {log.get_action_display()} - {log.status}")

# Failed operations with details
for log in DeviceLog.objects.filter(status='failed'):
    print(f"{log.timestamp}: {log.message}")
    if log.details:
        print(f"  Details: {log.details}")
```

## Monitoring and Alerts

### Check for Recent Failures

```python
from datetime import timedelta
from django.utils import timezone
from device.models import DeviceLog

recent_failures = DeviceLog.objects.filter(
    status__in=['failed', 'error'],
    timestamp__gte=timezone.now() - timedelta(hours=1)
).count()

if recent_failures > 5:
    # Send alert
    print(f"Alert: {recent_failures} failed operations in the last hour")
```

### Device Health Check

```python
from device.models import Device, DeviceLog

for device in Device.objects.filter(is_active=True):
    recent_logs = device.logs.all()[:10]
    failure_rate = recent_logs.filter(status='failed').count() / max(recent_logs.count(), 1)

    if failure_rate > 0.5:
        print(f"Warning: {device.name} has high failure rate ({failure_rate:.1%})")
```

## Security Considerations

- Logs may contain IP addresses and usernames
- Do not log sensitive data (passwords, fingerprint templates)
- Restrict access to logs to authorized personnel only
- Consider GDPR/privacy regulations when storing user data
- Implement log retention policies

## Troubleshooting

### Logs Not Appearing in Files

1. Check logs directory exists: `mkdir -p logs`
2. Check permissions: `chmod 755 logs`
3. Check Django settings `LOGGING` configuration
4. Restart Django server

### Logs Not Appearing in Database

1. Run migrations: `python manage.py migrate`
2. Check `DeviceLog` model exists: `python manage.py showmigrations device`
3. Check for exceptions in console output
4. Verify database connection

### Too Many Logs

1. Adjust log level from INFO to WARNING:
   ```python
   'device.auth': {
       'level': 'WARNING',  # Only warnings and errors
   }
   ```

2. Implement log rotation/cleanup
3. Filter logs by importance before storing

## Future Enhancements

Potential improvements:
- Real-time log viewer web interface
- Email/SMS alerts for critical failures
- Log aggregation and analytics dashboard
- Integration with monitoring tools (Grafana, Prometheus)
- Audit trail for compliance
- Log export to external systems

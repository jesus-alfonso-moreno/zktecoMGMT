#!/bin/bash
# Test async task system
# This script checks if the async task endpoints are working

set -e

PROJECT_DIR="/opt/CCP/zktecoMGMT"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/test_async_tasks_$(date +%Y%m%d_%H%M%S).log"

mkdir -p "$LOG_DIR"

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

log "=== Testing Async Task System ==="
log "Started at: $(date '+%Y-%m-%d %H:%M:%S')"
log ""

cd "$PROJECT_DIR"
source zkteco_env/bin/activate

log "Step 1: Check if Django-Q is running..."
if systemctl is-active --quiet django-q; then
    log "✓ Django-Q is running"
else
    log "✗ Django-Q is NOT running"
    exit 1
fi

log ""
log "Step 2: Check Q_CLUSTER configuration..."
python manage.py shell << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from django.conf import settings
import pprint

if hasattr(settings, 'Q_CLUSTER'):
    print("Q_CLUSTER configuration:")
    pprint.pprint(settings.Q_CLUSTER)
else:
    print("✗ Q_CLUSTER NOT configured!")
PYEOF

log ""
log "Step 3: Check task URLs..."
python manage.py shell << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from django.urls import reverse

try:
    print("Task URLs:")
    print("  Sync to device:", reverse('tasks:start_sync_to_device', kwargs={'device_id': 1}))
    print("  Sync from device:", reverse('tasks:start_sync_from_device', kwargs={'device_id': 1}))
    print("  Download attendance:", reverse('tasks:start_download_attendance', kwargs={'device_id': 1}))
    print("  Task status:", reverse('tasks:task_status', kwargs={'task_id': 'test'}))
    print("✓ All task URLs are configured")
except Exception as e:
    print(f"✗ Error with task URLs: {e}")
PYEOF

log ""
log "Step 4: Check if devices exist..."
python manage.py shell << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from device.models import Device

count = Device.objects.count()
print(f"Devices in database: {count}")

if count > 0:
    for device in Device.objects.all():
        print(f"  - {device.name} (ID: {device.pk}, IP: {device.ip_address})")
else:
    print("✗ No devices found - create a device first")
PYEOF

log ""
log "Step 5: Check Gunicorn error logs..."
tail -50 /var/log/nginx/zkteco_error.log 2>&1 | tee -a "$LOG_FILE"

log ""
log "Step 6: Test task creation directly..."
python manage.py shell << 'PYEOF' 2>&1 | tee -a "$LOG_FILE"
from django.contrib.auth.models import User
from django_q.tasks import async_task
from tasks.models import TaskProgress
import uuid

# Get first user
user = User.objects.first()
if not user:
    print("✗ No users found")
else:
    print(f"✓ Using user: {user.username}")

    # Create a test task
    task_id = str(uuid.uuid4())
    print(f"Creating test task: {task_id}")

    try:
        task = TaskProgress.objects.create(
            task_id=task_id,
            task_type='sync_to_device',
            user=user,
            status='pending',
            message='Test task'
        )
        print(f"✓ TaskProgress created: {task.pk}")

        # Try to queue a task
        result = async_task(
            'time.sleep',
            1,
            task_name='test_task'
        )
        print(f"✓ Task queued successfully with ID: {result}")

    except Exception as e:
        print(f"✗ Error creating task: {e}")
        import traceback
        traceback.print_exc()
PYEOF

log ""
log "Step 7: Check recent Django-Q logs..."
journalctl -u django-q -n 30 --no-pager 2>&1 | tee -a "$LOG_FILE"

log ""
log "=== Test Complete ==="
log "Log file: $LOG_FILE"

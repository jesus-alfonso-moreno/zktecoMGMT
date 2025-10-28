#!/bin/bash
# Diagnose async task system issues

cd /home/almita/CCP/zktecoMGMT
source zkteco_env/bin/activate

echo "=== 1. Checking Services Status ==="
echo ""
sudo systemctl is-active gunicorn || echo "Gunicorn NOT running"
sudo systemctl is-active django-q || echo "Django-Q NOT running"

echo ""
echo "=== 2. Checking Django-Q2 Logs (last 30 lines) ==="
echo ""
sudo journalctl -u django-q -n 30 --no-pager

echo ""
echo "=== 3. Checking Gunicorn Logs (last 30 lines) ==="
echo ""
sudo journalctl -u gunicorn -n 30 --no-pager

echo ""
echo "=== 4. Checking Task URLs ==="
echo ""
python manage.py shell << 'PYEOF'
from django.urls import reverse
try:
    print("Testing task URL patterns:")
    print("  Sync to device:", reverse('tasks:start_sync_to_device', kwargs={'device_id': 1}))
    print("  Sync from device:", reverse('tasks:start_sync_from_device', kwargs={'device_id': 1}))
    print("  Download attendance:", reverse('tasks:start_download_attendance', kwargs={'device_id': 1}))
    print("  Task status:", reverse('tasks:task_status', kwargs={'task_id': 'test'}))
    print("✓ All task URLs working")
except Exception as e:
    print(f"✗ Error: {e}")
PYEOF

echo ""
echo "=== 5. Checking TaskProgress Model ==="
echo ""
python manage.py shell << 'PYEOF'
from tasks.models import TaskProgress
from django.utils import timezone
from datetime import timedelta

count = TaskProgress.objects.count()
print(f"Total tasks in database: {count}")

if count > 0:
    recent = TaskProgress.objects.order_by('-created_at')[:5]
    print("\nRecent tasks:")
    for task in recent:
        print(f"  - {task.task_type}: {task.status} ({task.message})")
PYEOF

echo ""
echo "=== 6. Checking Q_CLUSTER Configuration ==="
echo ""
python manage.py shell << 'PYEOF'
from django.conf import settings
import pprint
if hasattr(settings, 'Q_CLUSTER'):
    print("Q_CLUSTER configuration:")
    pprint.pprint(settings.Q_CLUSTER)
else:
    print("✗ Q_CLUSTER NOT configured!")
PYEOF

echo ""
echo "=== 7. Testing Task Creation ==="
echo ""
python manage.py shell << 'PYEOF'
from django_q.tasks import async_task
from tasks.models import TaskProgress
from django.contrib.auth.models import User
import uuid

# Get or create a test user
user = User.objects.first()
if not user:
    print("No users found - cannot test")
else:
    task_id = str(uuid.uuid4())
    print(f"Creating test task with ID: {task_id}")
    
    # Create TaskProgress
    task = TaskProgress.objects.create(
        task_id=task_id,
        task_type='sync_to_device',
        user=user,
        status='pending',
        message='Test task'
    )
    print(f"✓ TaskProgress created: {task.pk}")
    
    # Try to queue a simple task
    try:
        from django_q.tasks import async_task
        result = async_task(
            'time.sleep',
            1,
            task_name='test_task'
        )
        print(f"✓ Test task queued successfully")
    except Exception as e:
        print(f"✗ Failed to queue task: {e}")
PYEOF

echo ""
echo "=== 8. Checking if taskTracker JavaScript is loaded ==="
echo ""
if grep -q "taskTracker" templates/base.html; then
    echo "✓ taskTracker JavaScript reference found in base.html"
else
    echo "✗ taskTracker JavaScript NOT found in base.html"
fi

if [ -f "static/js/task_progress.js" ]; then
    echo "✓ task_progress.js file exists"
else
    echo "✗ task_progress.js file NOT found"
fi

echo ""
echo "=== Diagnosis Complete ==="

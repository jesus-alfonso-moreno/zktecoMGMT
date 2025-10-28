#!/bin/bash
# Check Django-Q2 configuration and status

cd /home/almita/CCP/zktecoMGMT
source zkteco_env/bin/activate

echo "=== Django-Q2 Service Status ==="
sudo systemctl status django-q --no-pager | head -20

echo ""
echo "=== Django-Q2 Recent Logs ==="
sudo journalctl -u django-q -n 30 --no-pager

echo ""
echo "=== Checking Django-Q2 Configuration ==="
python manage.py shell << PYEOF
from django.conf import settings
import pprint

print("\n=== Q_CLUSTER Settings ===")
if hasattr(settings, 'Q_CLUSTER'):
    pprint.pprint(settings.Q_CLUSTER)
else:
    print("WARNING: Q_CLUSTER not configured in settings!")
    
print("\n=== Installed Apps (checking django_q) ===")
if 'django_q' in settings.INSTALLED_APPS:
    print("✓ django_q is in INSTALLED_APPS")
else:
    print("✗ django_q is NOT in INSTALLED_APPS")

print("\n=== Checking task models ===")
from tasks.models import TaskProgress
task_count = TaskProgress.objects.count()
print(f"TaskProgress records in database: {task_count}")
PYEOF

echo ""
echo "=== Testing Django-Q2 Task Queue ==="
python manage.py qmonitor


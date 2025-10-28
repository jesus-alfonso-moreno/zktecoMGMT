# Django-Q2 Verification and Setup

## Confirming Django-Q2 Installation

### 1. Check requirements.txt

Your `requirements.txt` should have:
```
django-q2>=1.8.0
```

**NOT** `django-q` (the old unmaintained version)

### 2. Verify Installation

```bash
python -m pip show django-q2
```

Should show:
```
Name: django-q2
Version: 1.8.0 (or higher)
Summary: A multiprocessing distributed task queue for Django
```

### 3. Settings Configuration

In `settings.py`, you should have:

```python
INSTALLED_APPS = [
    # ...
    'django_q',  # Note: app name is still 'django_q' even for django-q2
    # ...
]

Q_CLUSTER = {
    'name': 'zkteco',
    'workers': 2,
    'timeout': 300,
    'retry': 600,
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',
}
```

✅ This is already correct in your project!

### 4. Import Statements

Django-Q2 maintains backward compatibility, so imports use `django_q`:

```python
from django_q.tasks import async_task, result
from django_q.models import Task, Schedule
```

This is **correct** for django-q2!

### 5. Management Commands

All django-q2 commands:

```bash
# Start worker cluster
python manage.py qcluster

# Monitor tasks
python manage.py qmonitor

# Get task info
python manage.py qinfo

# Clear completed tasks
python manage.py qclear
```

### 6. Differences from Django-Q (old)

Django-Q2 improvements:
- ✅ Python 3.8+ support
- ✅ Django 4.x and 5.x support
- ✅ Active maintenance
- ✅ Bug fixes and security updates
- ✅ Better async support

### 7. Our Implementation Status

✅ Using django-q2 (version >= 1.8.0)
✅ Correct import statements
✅ Correct settings configuration
✅ Proper async_task usage

## Testing Django-Q2

### Start the cluster:

```bash
python manage.py qcluster
```

You should see:
```
INFO Q Cluster zkteco-<id> starting.
INFO Process-1:1 ready for work at <pid>
INFO Process-1:2 ready for work at <pid>
INFO Q Cluster zkteco-<id> running.
```

### Test with Python shell:

```python
python manage.py shell

from django_q.tasks import async_task

def test_task():
    return "Hello from Django-Q2!"

task_id = async_task(test_task)
print(f"Task queued: {task_id}")
```

Check the qcluster terminal - you should see the task execute!

### Verify task in database:

```python
from django_q.models import Task
Task.objects.all()
```

## Production Systemd Service

File: `/etc/systemd/system/django-q.service`

```ini
[Unit]
Description=Django-Q2 Worker Cluster
After=network.target postgresql.service

[Service]
User=root
WorkingDirectory=/home/almita/CCP/zktecoMGMT
Environment="PATH=/home/almita/CCP/zktecoMGMT/zkenvpy/bin"
ExecStart=/home/almita/CCP/zktecoMGMT/zkenvpy/bin/python manage.py qcluster
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable django-q
sudo systemctl start django-q
sudo systemctl status django-q
```

## Summary

✅ Your project is correctly set up for **django-q2**
✅ All imports use `django_q` (correct for django-q2)
✅ Configuration in settings.py is correct
✅ Ready to use for background tasks!

The implementation in `tasks/` directory is fully compatible with django-q2.

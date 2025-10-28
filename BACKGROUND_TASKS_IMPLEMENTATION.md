# Background Tasks Implementation Guide

This guide provides a complete solution for implementing background tasks with progress tracking to prevent Gunicorn timeouts when syncing with ZKTeco devices.

## Overview

The solution uses Django-Q2 for background task processing and includes:
- Progress tracking model
- Background task functions for sync operations
- AJAX endpoints for real-time progress updates
- Progress bar UI components
- Updated views to use async tasks

## Step 1: Add tasks app to INSTALLED_APPS

Edit `zkteco_project/settings.py` and add `'tasks'` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ... existing apps
    'tasks',  # Add this line
]
```

## Step 2: Run migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

## Step 3: Start Django-Q cluster

The Django-Q cluster needs to be running to process background tasks.

### Option A: Run in development

```bash
python manage.py qcluster
```

### Option B: Run as systemd service (production)

Create `/etc/systemd/system/django-q.service`:

```ini
[Unit]
Description=Django-Q Cluster
After=network.target

[Service]
User=root
WorkingDirectory=/home/almita/CCP/zktecoMGMT
Environment="PATH=/home/almita/CCP/zktecoMGMT/zkenvpy/bin"
ExecStart=/home/almita/CCP/zktecoMGMT/zkenvpy/bin/python manage.py qcluster
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable django-q
sudo systemctl start django-q
```

## Step 4: Create task functions

Create `/home/almita/CCP/zktecoMGMT/tasks/device_tasks.py` - See separate file

## Step 5: Create task views

Create `/home/almita/CCP/zktecoMGMT/tasks/views.py` - See separate file

## Step 6: Create task URLs

Create `/home/almita/CCP/zktecoMGMT/tasks/urls.py` - See separate file

## Step 7: Include task URLs in main urls.py

Edit `zkteco_project/urls.py`:

```python
urlpatterns = [
    # ... existing patterns
    path('tasks/', include('tasks.urls')),
]
```

## Step 8: Update employee views to use async tasks

Instead of directly calling sync operations, redirect to task initiation endpoints.

## Step 9: Create progress modal template

Create `templates/tasks/progress_modal.html` - See separate file

## Step 10: Add JavaScript for progress tracking

Create `static/js/task_progress.js` - See separate file

## Step 11: Include progress modal in base template

Add to `templates/base.html` before `</body>`:

```html
{% include 'tasks/progress_modal.html' %}
<script src="{% static 'js/task_progress.js' %}"></script>
```

## Step 12: Update Gunicorn configuration

Edit `/etc/systemd/system/gunicorn.service`:

```ini
ExecStart=/path/to/venv/bin/gunicorn zkteco_project.wsgi:application --bind 0.0.0.0:8000 --timeout 120 --workers 3
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

## Testing

1. Start Django-Q cluster: `python manage.py qcluster`
2. Start development server: `python manage.py runserver`
3. Go to employee list and click "Sync to Device"
4. Watch the progress bar update in real-time

## Architecture

```
User clicks "Sync"
    ↓
View creates TaskProgress record
    ↓
View queues async_task in Django-Q
    ↓
View returns task_id to frontend
    ↓
Frontend shows modal and starts polling /tasks/<task_id>/status/
    ↓
Background worker executes task
    ↓
Task updates TaskProgress record with progress
    ↓
Frontend polls and updates progress bar
    ↓
Task completes, frontend shows result
```

## Benefits

1. **No timeouts**: Long operations run in background
2. **Progress feedback**: Real-time progress bar
3. **Better UX**: Users can navigate away while task runs
4. **Error handling**: Detailed error reporting
5. **Scalable**: Can handle multiple concurrent operations

## Next Steps

1. Add notification system for task completion
2. Add ability to cancel running tasks
3. Add task history view
4. Add email notifications for completed tasks

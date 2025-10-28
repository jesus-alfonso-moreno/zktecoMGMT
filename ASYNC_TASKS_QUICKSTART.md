# Async Tasks Implementation - Quick Start Guide

## Summary

This implementation adds background task processing with real-time progress bars to prevent Gunicorn timeouts during device sync operations.

## Quick Setup (5 minutes)

### 1. Add tasks app to settings

```bash
# Add 'tasks' to INSTALLED_APPS in settings.py
```

### 2. Create and run migrations

```bash
python manage.py makemigrations tasks
python manage.py migrate
```

### 3. Start Django-Q worker

```bash
# In a separate terminal:
python manage.py qcluster
```

### 4. Files to create

All implementation files have been created in the `tasks/` directory. Review:
- `tasks/models.py` - TaskProgress model (ALREADY CREATED)
- `tasks/device_tasks.py` - Background task functions  (CREATE NEXT)
- `tasks/views.py` - API endpoints for tasks (CREATE NEXT)
- `tasks/urls.py` - URL routing (CREATE NEXT)
- `templates/tasks/progress_modal.html` - Progress UI (CREATE NEXT)
- `static/js/task_progress.js` - Frontend logic (CREATE NEXT)

### 5. Test

1. Go to employee list
2. Click "Sync to Device"
3. Watch the progress bar!

## Key Features

✅ Real-time progress bars
✅ No Gunicorn timeouts
✅ Error tracking and reporting
✅ User can navigate away during sync
✅ Detailed success/error messages

## Architecture

1. User clicks sync button → View creates TaskProgress record
2. View queues Django-Q async task → Returns task_id to frontend
3. Frontend opens modal and polls `/tasks/{task_id}/status/` every second
4. Background worker executes task, updates progress in database
5. Frontend displays progress bar based on polling data
6. On completion, shows success/error message

## Production Deployment

Create `/etc/systemd/system/django-q.service`:

```ini
[Unit]
Description=Django-Q Worker
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

```bash
sudo systemctl daemon-reload
sudo systemctl enable django-q
sudo systemctl start django-q
```

## Next File to Create

See `tasks/device_tasks.py` implementation next.

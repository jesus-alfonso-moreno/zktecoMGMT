# Remaining Implementation Steps

You've successfully created the core backend components! Here's what's left to complete the async task system.

## ✅ Completed
1. ✅ TaskProgress model (tasks/models.py)
2. ✅ Background task functions (tasks/device_tasks.py)
3. ✅ Task API views (tasks/views.py)

## 📝 Next Steps

### 1. Create tasks/urls.py

```python
from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Task initiation endpoints
    path('sync-to-device/<int:device_id>/', views.start_sync_to_device, name='start_sync_to_device'),
    path('sync-from-device/<int:device_id>/', views.start_sync_from_device, name='start_sync_from_device'),
    path('download-attendance/<int:device_id>/', views.start_download_attendance, name='start_download_attendance'),

    # Progress polling endpoint
    path('status/<str:task_id>/', views.task_status, name='task_status'),
]
```

### 2. Add tasks app to settings.py

```python
INSTALLED_APPS = [
    # ... existing apps ...
    'tasks',  # Add this line
]
```

### 3. Include tasks URLs in main urls.py

Edit `zkteco_project/urls.py`:

```python
urlpatterns = [
    # ... existing patterns ...
    path('tasks/', include('tasks.urls')),  # Add this line
]
```

### 4. Run migrations

```bash
python manage.py makemigrations tasks
python manage.py migrate
```

### 5. Create templates/tasks/progress_modal.html

```html
<!-- Progress Modal -->
<div class="modal fade" id="taskProgressModal" tabindex="-1" data-bs-backdrop="static" data-bs-keyboard="false">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title" id="taskProgressTitle">Processing...</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close" id="taskProgressClose" style="display:none;"></button>
            </div>
            <div class="modal-body">
                <div id="taskProgressMessage" class="mb-3">Initializing...</div>

                <div class="progress" style="height: 25px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated"
                         role="progressbar"
                         id="taskProgressBar"
                         style="width: 0%"
                         aria-valuenow="0"
                         aria-valuemin="0"
                         aria-valuemax="100">
                        <span id="taskProgressPercent">0%</span>
                    </div>
                </div>

                <div id="taskProgressDetails" class="mt-3 small text-muted"></div>

                <div id="taskProgressResult" class="mt-3" style="display:none;">
                    <div id="taskProgressSuccess" class="alert alert-success" style="display:none;"></div>
                    <div id="taskProgressError" class="alert alert-danger" style="display:none;"></div>
                    <div id="taskProgressErrors" class="mt-2" style="display:none;">
                        <strong>Errors:</strong>
                        <ul id="taskProgressErrorList" class="mb-0"></ul>
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-primary" id="taskProgressDone" style="display:none;" data-bs-dismiss="modal">Done</button>
            </div>
        </div>
    </div>
</div>
```

### 6. Create static/js/task_progress.js

```javascript
/**
 * Task Progress Tracker
 * Handles background task progress updates via AJAX polling
 */

class TaskProgressTracker {
    constructor() {
        this.modal = null;
        this.taskId = null;
        this.pollInterval = null;
        this.pollDelay = 1000; // Poll every 1 second
    }

    init() {
        this.modal = new bootstrap.Modal(document.getElementById('taskProgressModal'));
    }

    startTask(url, taskType) {
        // Send POST request to initiate task
        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken'),
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                this.taskId = data.task_id;
                this.showModal(taskType);
                this.startPolling();
            } else {
                alert('Error starting task: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('Error starting task: ' + error.message);
        });
    }

    showModal(taskType) {
        document.getElementById('taskProgressTitle').textContent = taskType;
        document.getElementById('taskProgressMessage').textContent = 'Starting...';
        document.getElementById('taskProgressBar').style.width = '0%';
        document.getElementById('taskProgressPercent').textContent = '0%';
        document.getElementById('taskProgressResult').style.display = 'none';
        document.getElementById('taskProgressDone').style.display = 'none';
        document.getElementById('taskProgressClose').style.display = 'none';
        this.modal.show();
    }

    startPolling() {
        this.pollInterval = setInterval(() => {
            this.checkStatus();
        }, this.pollDelay);
    }

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
    }

    checkStatus() {
        fetch(`/tasks/status/${this.taskId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.updateProgress(data.task);
                } else {
                    this.showError('Error checking status: ' + data.error);
                    this.stopPolling();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                this.stopPolling();
            });
    }

    updateProgress(task) {
        // Update progress bar
        const percentage = task.progress_percentage || 0;
        document.getElementById('taskProgressBar').style.width = percentage + '%';
        document.getElementById('taskProgressPercent').textContent = percentage + '%';
        document.getElementById('taskProgressMessage').textContent = task.message || 'Processing...';

        // Update details
        const details = `Progress: ${task.progress_current} / ${task.progress_total}`;
        document.getElementById('taskProgressDetails').textContent = details;

        // Check if finished
        if (task.is_finished) {
            this.stopPolling();
            this.showResult(task);
        }
    }

    showResult(task) {
        document.getElementById('taskProgressResult').style.display = 'block';
        document.getElementById('taskProgressDone').style.display = 'block';
        document.getElementById('taskProgressClose').style.display = 'block';

        // Remove animation from progress bar
        const progressBar = document.getElementById('taskProgressBar');
        progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped');

        if (task.status === 'completed') {
            progressBar.classList.add('bg-success');
            const successDiv = document.getElementById('taskProgressSuccess');
            successDiv.style.display = 'block';
            successDiv.innerHTML = `
                <strong>Success!</strong><br>
                ${task.message}<br>
                <small>Success: ${task.success_count} | Errors: ${task.error_count}</small>
            `;

            // Show errors if any
            if (task.error_count > 0 && task.error_details.length > 0) {
                document.getElementById('taskProgressErrors').style.display = 'block';
                const errorList = document.getElementById('taskProgressErrorList');
                errorList.innerHTML = '';
                task.error_details.forEach(error => {
                    const li = document.createElement('li');
                    li.textContent = error;
                    errorList.appendChild(li);
                });
            }
        } else if (task.status === 'failed') {
            progressBar.classList.add('bg-danger');
            const errorDiv = document.getElementById('taskProgressError');
            errorDiv.style.display = 'block';
            errorDiv.innerHTML = `<strong>Error!</strong><br>${task.message}`;
        }
    }

    showError(message) {
        document.getElementById('taskProgressResult').style.display = 'block';
        document.getElementById('taskProgressDone').style.display = 'block';
        const errorDiv = document.getElementById('taskProgressError');
        errorDiv.style.display = 'block';
        errorDiv.innerHTML = `<strong>Error!</strong><br>${message}`;
    }

    getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Global instance
const taskTracker = new TaskProgressTracker();

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    taskTracker.init();
});
```

### 7. Update base.html

Add before `</body>`:

```html
<!-- Task Progress Modal -->
{% include 'tasks/progress_modal.html' %}
<script src="{% static 'js/task_progress.js' %}"></script>
```

### 8. Update employee list buttons

In `templates/employees/employee_list.html`, change sync buttons from:

```html
<a href="{% url 'employees:sync_to_device' %}?device={{ device.id }}" ...>
```

To:

```html
<button onclick="taskTracker.startTask('/tasks/sync-to-device/{{ device.id }}/', 'Sync To Device')" class="btn btn-sm btn-primary">
    <i class="bi bi-cloud-upload"></i> Sync To Device
</button>
```

Similar changes for:
- Sync From Device → `/tasks/sync-from-device/{{ device.id }}/`
- Download Attendance → `/tasks/download-attendance/{{ device.id }}/`

### 9. Start Django-Q worker

```bash
python manage.py qcluster
```

### 10. Test!

1. Go to employee list
2. Click "Sync To Device"
3. Watch the progress bar update in real-time!

## Production Deployment

Create systemd service for Django-Q at `/etc/systemd/system/django-q.service` (see ASYNC_TASKS_QUICKSTART.md)

## Summary

This implementation provides:
- ✅ No Gunicorn timeouts
- ✅ Real-time progress tracking
- ✅ Better user experience
- ✅ Detailed error reporting
- ✅ Scalable architecture

All done! 🎉

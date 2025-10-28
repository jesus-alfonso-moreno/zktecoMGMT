/**
 * Task Progress Tracker
 * Handles background task progress updates via AJAX polling
 * Uses Bootstrap 5 modals and vanilla JavaScript
 */

class TaskProgressTracker {
    constructor() {
        this.modal = null;
        this.taskId = null;
        this.pollInterval = null;
        this.pollDelay = 1000; // Poll every 1 second
        this.maxPollAttempts = 600; // Max 10 minutes
        this.pollAttempts = 0;
    }

    init() {
        const modalElement = document.getElementById('taskProgressModal');
        if (modalElement && typeof bootstrap !== 'undefined') {
            this.modal = new bootstrap.Modal(modalElement);
        } else {
            console.error('Task Progress Modal or Bootstrap not found');
        }
    }

    startTask(url, taskType) {
        if (!this.modal) {
            alert('Progress modal not initialized');
            return;
        }

        // Reset state
        this.pollAttempts = 0;

        // Send POST request to initiate task
        const csrfToken = this.getCookie('csrftoken');
        console.log('Starting task:', { url, csrfToken: csrfToken ? 'present' : 'missing' });

        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json',
            },
        })
        .then(response => {
            console.log('Response status:', response.status);
            if (!response.ok) {
                return response.text().then(text => {
                    throw new Error(`Server returned ${response.status}: ${text.substring(0, 200)}`);
                });
            }
            return response.json();
        })
        .then(data => {
            console.log('Response data:', data);
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
        // Reset modal state
        document.getElementById('taskProgressTitle').textContent = taskType;
        document.getElementById('taskProgressMessage').innerHTML = '<i class="bi bi-hourglass-split me-2"></i><span>Starting...</span>';

        const progressBar = document.getElementById('taskProgressBar');
        progressBar.style.width = '0%';
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated bg-primary';

        document.getElementById('taskProgressPercent').textContent = '0%';
        document.getElementById('taskProgressDetails').textContent = '';
        document.getElementById('taskProgressResult').style.display = 'none';
        document.getElementById('taskProgressSuccess').style.display = 'none';
        document.getElementById('taskProgressError').style.display = 'none';
        document.getElementById('taskProgressErrors').style.display = 'none';
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
        this.pollAttempts++;

        // Stop if max attempts reached
        if (this.pollAttempts >= this.maxPollAttempts) {
            this.stopPolling();
            this.showError('Task timeout - maximum polling attempts reached');
            return;
        }

        fetch(`/tasks/status/${this.taskId}/`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.updateProgress(data.task);
                } else {
                    this.showError('Error checking status: ' + (data.error || 'Unknown error'));
                    this.stopPolling();
                }
            })
            .catch(error => {
                console.error('Polling error:', error);
                // Don't stop on single error, keep polling
                if (this.pollAttempts % 5 === 0) {
                    console.warn('Multiple polling errors detected');
                }
            });
    }

    updateProgress(task) {
        // Update progress bar
        const percentage = task.progress_percentage || 0;
        const progressBar = document.getElementById('taskProgressBar');
        progressBar.style.width = percentage + '%';
        progressBar.setAttribute('aria-valuenow', percentage);
        document.getElementById('taskProgressPercent').textContent = percentage + '%';

        // Update message
        const messageHtml = '<i class="bi bi-hourglass-split me-2"></i><span>' + (task.message || 'Processing...') + '</span>';
        document.getElementById('taskProgressMessage').innerHTML = messageHtml;

        // Update details
        let details = '';
        if (task.progress_total > 0) {
            details = `Progress: ${task.progress_current} / ${task.progress_total}`;
            if (task.duration) {
                const duration = Math.round(task.duration);
                details += ` | Duration: ${duration}s`;
            }
        }
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
            // Success
            progressBar.classList.remove('bg-primary');
            progressBar.classList.add('bg-success');
            progressBar.style.width = '100%';
            document.getElementById('taskProgressPercent').textContent = '100%';

            const successDiv = document.getElementById('taskProgressSuccess');
            successDiv.style.display = 'block';

            let successMessage = task.message || 'Task completed successfully';
            if (task.success_count > 0 || task.error_count > 0) {
                successMessage += `<br><small class="mt-2 d-block">Success: ${task.success_count} | Errors: ${task.error_count}</small>`;
            }

            document.getElementById('taskProgressSuccessMessage').innerHTML = successMessage;
            document.getElementById('taskProgressMessage').innerHTML = '<i class="bi bi-check-circle me-2"></i><span>Completed!</span>';

            // Show errors if any
            if (task.error_count > 0 && task.error_details && task.error_details.length > 0) {
                document.getElementById('taskProgressErrors').style.display = 'block';
                const errorList = document.getElementById('taskProgressErrorList');
                errorList.innerHTML = '';
                task.error_details.forEach(error => {
                    const li = document.createElement('li');
                    li.textContent = error;
                    li.className = 'mb-1';
                    errorList.appendChild(li);
                });
            }

            // Play success sound (optional)
            this.playNotificationSound();

        } else if (task.status === 'failed') {
            // Error
            progressBar.classList.remove('bg-primary');
            progressBar.classList.add('bg-danger');

            const errorDiv = document.getElementById('taskProgressError');
            errorDiv.style.display = 'block';
            document.getElementById('taskProgressErrorMessage').innerHTML = task.message || 'Task failed';
            document.getElementById('taskProgressMessage').innerHTML = '<i class="bi bi-x-circle me-2"></i><span>Failed!</span>';
        }
    }

    showError(message) {
        document.getElementById('taskProgressResult').style.display = 'block';
        document.getElementById('taskProgressDone').style.display = 'block';
        document.getElementById('taskProgressClose').style.display = 'block';

        const progressBar = document.getElementById('taskProgressBar');
        progressBar.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-primary');
        progressBar.classList.add('bg-danger');

        const errorDiv = document.getElementById('taskProgressError');
        errorDiv.style.display = 'block';
        document.getElementById('taskProgressErrorMessage').innerHTML = message;
        document.getElementById('taskProgressMessage').innerHTML = '<i class="bi bi-x-circle me-2"></i><span>Error!</span>';
    }

    playNotificationSound() {
        // Optional: Play a notification sound when task completes
        // This requires an audio file to be available
        try {
            // const audio = new Audio('/static/sounds/notification.mp3');
            // audio.play().catch(e => console.log('Could not play sound:', e));
        } catch (e) {
            // Silently fail if sound not available
        }
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

// Create global instance
const taskTracker = new TaskProgressTracker();

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    taskTracker.init();
});

// Refresh page when modal is closed (to update the list)
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('taskProgressModal');
    if (modal) {
        modal.addEventListener('hidden.bs.modal', function () {
            // Reload page to show updated data
            const shouldReload = modal.getAttribute('data-reload-on-close');
            if (shouldReload === 'true') {
                location.reload();
            }
        });
    }
});

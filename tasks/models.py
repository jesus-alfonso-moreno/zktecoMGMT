from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class TaskProgress(models.Model):
    """Track progress of long-running background tasks"""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    TASK_TYPE_CHOICES = [
        ('sync_to_device', 'Sync To Device'),
        ('sync_from_device', 'Sync From Device'),
        ('download_attendance', 'Download Attendance'),
        ('upload_fingerprints', 'Upload Fingerprints'),
        ('download_fingerprints', 'Download Fingerprints'),
    ]

    # Task identification
    task_id = models.CharField(max_length=255, unique=True, db_index=True)
    task_type = models.CharField(max_length=50, choices=TASK_TYPE_CHOICES)

    # User and device info
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tasks')
    device = models.ForeignKey('device.Device', on_delete=models.CASCADE, null=True, blank=True)

    # Progress tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_current = models.IntegerField(default=0)
    progress_total = models.IntegerField(default=0)
    progress_percentage = models.IntegerField(default=0)

    # Results
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    message = models.TextField(blank=True)
    error_details = models.JSONField(default=list, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.status} ({self.progress_percentage}%)"

    def update_progress(self, current, total=None, message=None):
        """Update task progress"""
        self.progress_current = current
        if total is not None:
            self.progress_total = total

        if self.progress_total > 0:
            self.progress_percentage = int((self.progress_current / self.progress_total) * 100)

        if message:
            self.message = message

        self.save(update_fields=['progress_current', 'progress_total', 'progress_percentage', 'message'])

    def mark_running(self):
        """Mark task as running"""
        self.status = 'running'
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def mark_completed(self, message=None):
        """Mark task as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.progress_percentage = 100
        if message:
            self.message = message
        self.save(update_fields=['status', 'completed_at', 'progress_percentage', 'message'])

    def mark_failed(self, error_message):
        """Mark task as failed"""
        self.status = 'failed'
        self.completed_at = timezone.now()
        self.message = error_message
        self.save(update_fields=['status', 'completed_at', 'message'])

    def add_error(self, error_detail):
        """Add an error to the error details list"""
        if not isinstance(self.error_details, list):
            self.error_details = []
        self.error_details.append(error_detail)
        self.error_count += 1
        self.save(update_fields=['error_details', 'error_count'])

    @property
    def duration(self):
        """Calculate task duration"""
        if not self.started_at:
            return None
        end_time = self.completed_at or timezone.now()
        return (end_time - self.started_at).total_seconds()

    @property
    def is_finished(self):
        """Check if task is finished"""
        return self.status in ['completed', 'failed', 'cancelled']

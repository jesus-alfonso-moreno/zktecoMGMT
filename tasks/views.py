"""
Views for task management and progress tracking.
Provides endpoints for initiating tasks and polling progress.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django_q.tasks import async_task  # django-q2 uses same import path
import uuid

from .models import TaskProgress
from .device_tasks import (
    async_sync_employees_to_device,
    async_sync_employees_from_device,
    async_download_attendance
)
from device.models import Device


@login_required
@require_http_methods(["POST"])
def start_sync_to_device(request, device_id):
    """
    Initiate background task to sync employees TO device.

    Returns JSON with task_id for progress tracking.
    """
    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Device not found'
        }, status=404)

    # Create unique task ID
    task_id = str(uuid.uuid4())

    # Create task progress record
    task = TaskProgress.objects.create(
        task_id=task_id,
        task_type='sync_to_device',
        user=request.user,
        device=device,
        status='pending',
        message=f'Queuing sync to {device.name}...'
    )

    # Queue async task in Django-Q
    async_task(
        async_sync_employees_to_device,
        task_id=task_id,
        device_id=device_id,
        user_id=request.user.id,
        task_name=f'sync_to_device_{device_id}',
    )

    return JsonResponse({
        'success': True,
        'task_id': task_id,
        'message': f'Sync to {device.name} started'
    })


@login_required
@require_http_methods(["POST"])
def start_sync_from_device(request, device_id):
    """
    Initiate background task to sync employees FROM device.

    Returns JSON with task_id for progress tracking.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"start_sync_from_device called: method={request.method}, user={request.user}, device_id={device_id}")
    logger.info(f"Headers: {dict(request.headers)}")

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Device not found'
        }, status=404)

    task_id = str(uuid.uuid4())

    task = TaskProgress.objects.create(
        task_id=task_id,
        task_type='sync_from_device',
        user=request.user,
        device=device,
        status='pending',
        message=f'Queuing sync from {device.name}...'
    )

    async_task(
        async_sync_employees_from_device,
        task_id=task_id,
        device_id=device_id,
        user_id=request.user.id,
        task_name=f'sync_from_device_{device_id}',
    )

    return JsonResponse({
        'success': True,
        'task_id': task_id,
        'message': f'Sync from {device.name} started'
    })


@login_required
@require_http_methods(["POST"])
def start_download_attendance(request, device_id):
    """
    Initiate background task to download attendance FROM device.

    Returns JSON with task_id for progress tracking.
    """
    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Device not found'
        }, status=404)

    task_id = str(uuid.uuid4())

    task = TaskProgress.objects.create(
        task_id=task_id,
        task_type='download_attendance',
        user=request.user,
        device=device,
        status='pending',
        message=f'Queuing attendance download from {device.name}...'
    )

    async_task(
        async_download_attendance,
        task_id=task_id,
        device_id=device_id,
        user_id=request.user.id,
        task_name=f'download_attendance_{device_id}',
    )

    return JsonResponse({
        'success': True,
        'task_id': task_id,
        'message': f'Attendance download from {device.name} started'
    })


@login_required
@require_http_methods(["GET"])
def task_status(request, task_id):
    """
    Get current status of a task.

    This endpoint is polled by the frontend to update progress bars.

    Returns:
        JSON with task status, progress, and messages
    """
    try:
        task = TaskProgress.objects.get(task_id=task_id)

        # Only allow users to view their own tasks
        if task.user != request.user and not request.user.is_staff:
            return JsonResponse({
                'success': False,
                'error': 'Permission denied'
            }, status=403)

        return JsonResponse({
            'success': True,
            'task': {
                'id': task.task_id,
                'type': task.get_task_type_display(),
                'status': task.status,
                'progress_current': task.progress_current,
                'progress_total': task.progress_total,
                'progress_percentage': task.progress_percentage,
                'message': task.message,
                'success_count': task.success_count,
                'error_count': task.error_count,
                'error_details': task.error_details[:10],  # Limit to first 10 errors
                'is_finished': task.is_finished,
                'duration': task.duration,
                'device_name': task.device.name if task.device else None,
            }
        })

    except TaskProgress.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Task not found'
        }, status=404)

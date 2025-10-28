"""
Background tasks for device synchronization operations.
These tasks run asynchronously using Django-Q to prevent Gunicorn timeouts.
"""

import logging
from django.utils import timezone
from device.models import Device
from device.zk_connector import ZKDeviceConnector
from employees.models import Employee, Fingerprint
from attendance.models import AttendanceEvent
from .models import TaskProgress

logger = logging.getLogger(__name__)


def async_sync_employees_to_device(task_id, device_id, user_id):
    """
    Background task: Upload employees to device and remove deleted ones.

    Args:
        task_id: TaskProgress ID for tracking
        device_id: Device ID to sync with
        user_id: User ID who initiated the task
    """
    try:
        # Get task progress object
        task = TaskProgress.objects.get(task_id=task_id)
        task.mark_running()

        # Get device
        device = Device.objects.get(pk=device_id)
        connector = ZKDeviceConnector(device)

        # Get active employees
        employees = Employee.objects.filter(is_active=True)
        total_employees = employees.count()

        # Connect to device
        task.update_progress(0, total_employees + 10, "Connecting to device...")
        conn = connector.connect()
        task.update_progress(5, message="Connected. Fetching device users...")

        # Get current users from device
        device_users = connector.get_users(conn)
        device_user_ids = {user.uid for user in device_users}
        task.update_progress(10, message=f"Found {len(device_user_ids)} users on device")

        # Get database employee user IDs
        db_user_ids = {emp.user_id for emp in employees}

        # Delete users that are on device but not in database
        users_to_delete = device_user_ids - db_user_ids
        deleted_count = 0

        for i, uid in enumerate(users_to_delete):
            try:
                connector.delete_user(conn, uid)
                # Also delete fingerprints
                for finger_idx in range(10):
                    try:
                        connector.delete_fingerprint_template(conn, uid, finger_idx)
                    except:
                        pass
                deleted_count += 1
            except Exception as e:
                task.add_error(f"Failed to delete user {uid}: {str(e)}")

        if deleted_count > 0:
            task.update_progress(10, message=f"Removed {deleted_count} obsolete users")

        # Upload/update active employees
        success_count = 0
        error_count = 0

        for i, emp in enumerate(employees):
            try:
                connector.set_user(
                    conn=conn,
                    uid=emp.user_id,
                    name=emp.full_name,
                    privilege=emp.privilege,
                    password=emp.password or '',
                    group_id='0',
                    user_id=emp.employee_id
                )
                emp.synced_to_device = True
                emp.device = device
                emp.save()
                success_count += 1

                # Update progress
                current_progress = 10 + i + 1
                task.update_progress(
                    current_progress,
                    message=f"Synced {emp.full_name} ({i+1}/{total_employees})"
                )

            except Exception as e:
                error_count += 1
                task.add_error(f"{emp.full_name}: {str(e)}")
                logger.error(f"Error syncing employee {emp.full_name}: {str(e)}")

        conn.disconnect()

        # Update device last sync
        device.last_sync = timezone.now()
        device.save()

        # Update task results
        task.success_count = success_count
        task.error_count = error_count

        # Create summary message
        summary_parts = []
        if success_count > 0:
            summary_parts.append(f"Synced {success_count} employees")
        if deleted_count > 0:
            summary_parts.append(f"removed {deleted_count} obsolete users")
        if error_count > 0:
            summary_parts.append(f"{error_count} errors")

        summary = ", ".join(summary_parts)
        task.mark_completed(f"Completed: {summary}")

    except Exception as e:
        logger.error(f"Fatal error in async_sync_employees_to_device: {str(e)}")
        try:
            task = TaskProgress.objects.get(task_id=task_id)
            task.mark_failed(f"Fatal error: {str(e)}")
        except:
            pass


def async_sync_employees_from_device(task_id, device_id, user_id):
    """
    Background task: Download employees from device and their fingerprints.

    Args:
        task_id: TaskProgress ID for tracking
        device_id: Device ID to sync from
        user_id: User ID who initiated the task
    """
    try:
        task = TaskProgress.objects.get(task_id=task_id)
        task.mark_running()

        device = Device.objects.get(pk=device_id)
        connector = ZKDeviceConnector(device)

        task.update_progress(0, 100, "Connecting to device...")
        conn = connector.connect()

        task.update_progress(10, message="Fetching users from device...")
        users = connector.get_users(conn)
        total_users = len(users)

        task.update_progress(15, 15 + total_users * 85 // 100, f"Found {total_users} users")

        success_count = 0
        updated_count = 0
        error_count = 0
        fingerprints_downloaded = 0

        for i, user in enumerate(users):
            try:
                # Create or update employee
                employee, created = Employee.objects.update_or_create(
                    user_id=user.uid,
                    defaults={
                        'employee_id': user.user_id or f'EMP{user.uid:04d}',
                        'first_name': user.name.split()[0] if user.name else f'User{user.uid}',
                        'last_name': ' '.join(user.name.split()[1:]) if len(user.name.split()) > 1 else '',
                        'privilege': user.privilege,
                        'password': user.password or '',
                        'synced_to_device': True,
                        'device': device,
                    }
                )

                if created:
                    success_count += 1
                else:
                    updated_count += 1

                # Download fingerprint templates
                templates = connector.get_all_fingerprint_templates(conn, user.uid)
                for temp_id, template_data in templates.items():
                    Fingerprint.objects.update_or_create(
                        employee=employee,
                        finger_index=temp_id,
                        defaults={
                            'template': template_data,
                            'device': device
                        }
                    )
                    fingerprints_downloaded += 1

                # Update progress
                progress = 15 + int((i + 1) / total_users * 85)
                task.update_progress(
                    progress,
                    message=f"Processed {user.name or f'User {user.uid}'} ({i+1}/{total_users})"
                )

            except Exception as e:
                error_count += 1
                task.add_error(f"User {user.uid}: {str(e)}")
                logger.error(f"Error syncing user {user.uid}: {str(e)}")

        conn.disconnect()

        device.last_sync = timezone.now()
        device.save()

        task.success_count = success_count
        task.error_count = error_count

        summary_parts = []
        if success_count > 0:
            summary_parts.append(f"{success_count} new employees")
        if updated_count > 0:
            summary_parts.append(f"{updated_count} updated")
        if fingerprints_downloaded > 0:
            summary_parts.append(f"{fingerprints_downloaded} fingerprints")
        if error_count > 0:
            summary_parts.append(f"{error_count} errors")

        summary = "Downloaded: " + ", ".join(summary_parts)
        task.mark_completed(summary)

    except Exception as e:
        logger.error(f"Fatal error in async_sync_employees_from_device: {str(e)}")
        try:
            task = TaskProgress.objects.get(task_id=task_id)
            task.mark_failed(f"Fatal error: {str(e)}")
        except:
            pass


def async_download_attendance(task_id, device_id, user_id):
    """
    Background task: Download attendance events from device.

    Args:
        task_id: TaskProgress ID for tracking
        device_id: Device ID to download from
        user_id: User ID who initiated the task
    """
    try:
        task = TaskProgress.objects.get(task_id=task_id)
        task.mark_running()

        device = Device.objects.get(pk=device_id)
        connector = ZKDeviceConnector(device)

        task.update_progress(0, 100, "Connecting to device...")
        conn = connector.connect()

        task.update_progress(10, message="Downloading attendance records...")
        attendance_records = connector.get_attendance(conn)
        total_records = len(attendance_records)

        task.update_progress(20, 20 + total_records, f"Found {total_records} records")

        conn.disconnect()

        success_count = 0
        error_count = 0
        duplicate_count = 0

        for i, record in enumerate(attendance_records):
            try:
                # Try to match employee
                employee = None
                try:
                    employee = Employee.objects.get(user_id=record.user_id)
                except Employee.DoesNotExist:
                    pass

                # Create or skip if duplicate
                _, created = AttendanceEvent.objects.get_or_create(
                    device=device,
                    user_id=record.user_id,
                    timestamp=record.timestamp,
                    defaults={
                        'employee': employee,
                        'punch_type': record.punch,
                        'verify_mode': getattr(record, 'status', 0),
                        'work_code': 0,
                    }
                )

                if created:
                    success_count += 1
                else:
                    duplicate_count += 1

                # Update progress
                current_progress = 20 + i + 1
                if (i + 1) % 10 == 0 or i == total_records - 1:
                    task.update_progress(
                        current_progress,
                        message=f"Processed {i+1}/{total_records} records"
                    )

            except Exception as e:
                error_count += 1
                task.add_error(f"Record {i+1}: {str(e)}")
                logger.error(f"Error importing attendance record: {str(e)}")

        device.last_sync = timezone.now()
        device.save()

        task.success_count = success_count
        task.error_count = error_count

        summary_parts = []
        if success_count > 0:
            summary_parts.append(f"{success_count} new events")
        if duplicate_count > 0:
            summary_parts.append(f"{duplicate_count} duplicates skipped")
        if error_count > 0:
            summary_parts.append(f"{error_count} errors")

        summary = "Downloaded: " + ", ".join(summary_parts)
        task.mark_completed(summary)

    except Exception as e:
        logger.error(f"Fatal error in async_download_attendance: {str(e)}")
        try:
            task = TaskProgress.objects.get(task_id=task_id)
            task.mark_failed(f"Fatal error: {str(e)}")
        except:
            pass

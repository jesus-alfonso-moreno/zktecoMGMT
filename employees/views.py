from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.utils.translation import gettext as _
import csv
import io
from .models import Employee, Fingerprint
from .forms import EmployeeForm, EmployeeSearchForm
from device.models import Device
from device.zk_connector import ZKDeviceConnector
from accounts.permissions import (
    EmployeeSectionMixin, employee_section_required,
    manage_employees_required, manage_fingerprints_required
)

# Finger mapping for display
FINGER_MAP = {
    0: "Left thumb",
    1: "Left index",
    2: "Left middle",
    3: "Left ring",
    4: "Left pinky",
    5: "Right thumb",
    6: "Right index",
    7: "Right middle",
    8: "Right ring",
    9: "Right pinky"
}


class EmployeeListView(EmployeeSectionMixin, ListView):
    """List all employees with search and pagination"""
    model = Employee
    template_name = 'employees/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset()
        search = self.request.GET.get('search')
        department = self.request.GET.get('department')
        is_active = self.request.GET.get('is_active')

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(employee_id__icontains=search)
            )

        if department:
            queryset = queryset.filter(department__icontains=department)

        if is_active:
            queryset = queryset.filter(is_active=(is_active == 'true'))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = EmployeeSearchForm(self.request.GET)
        context['devices'] = Device.objects.filter(is_active=True)
        return context


class EmployeeCreateView(EmployeeSectionMixin, CreateView):
    """Create new employee"""
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    success_url = reverse_lazy('employees:employee_list')
    permission_required = 'employees.manage_employees'

    def form_valid(self, form):
        messages.success(self.request, 'Employee created successfully!')
        return super().form_valid(form)


class EmployeeUpdateView(EmployeeSectionMixin, UpdateView):
    """Update existing employee"""
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    success_url = reverse_lazy('employees:employee_list')
    permission_required = 'employees.manage_employees'

    def form_valid(self, form):
        # Mark as not synced if data changed
        if form.has_changed():
            form.instance.synced_to_device = False
        messages.success(self.request, 'Employee updated successfully!')
        return super().form_valid(form)


class EmployeeDeleteView(EmployeeSectionMixin, DeleteView):
    """Delete employee"""
    model = Employee
    template_name = 'employees/employee_confirm_delete.html'
    success_url = reverse_lazy('employees:employee_list')
    permission_required = 'employees.manage_employees'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['devices'] = Device.objects.filter(is_active=True)
        return context

    def delete(self, request, *args, **kwargs):
        employee = self.get_object()

        # Store employee info for messages before deletion
        employee_name = employee.full_name
        device_id = request.POST.get('device')

        # Try to delete from device if a device is specified
        if device_id:
            try:
                device = Device.objects.get(pk=device_id, is_active=True)
                connector = ZKDeviceConnector(device)
                conn = connector.connect()

                # Delete user from device
                connector.delete_user(conn, employee.user_id)

                # Also delete all fingerprints for this user
                for finger_idx in range(10):
                    try:
                        connector.delete_fingerprint_template(conn, employee.user_id, finger_idx)
                    except:
                        pass  # Continue even if fingerprint doesn't exist

                conn.disconnect()

                # Delete from database after successful device deletion
                result = super().delete(request, *args, **kwargs)
                messages.success(request, _('Employee %(name)s deleted from database and device %(device)s') % {
                    'name': employee_name, 'device': device.name
                })
                return result

            except Device.DoesNotExist:
                messages.error(request, _('Selected device not found'))
                return redirect('employees:employee_list')
            except Exception as e:
                # Still delete from database even if device deletion fails
                result = super().delete(request, *args, **kwargs)
                messages.warning(request, _('Employee %(name)s deleted from database, but failed to delete from device: %(error)s') % {
                    'name': employee_name, 'error': str(e)
                })
                return result
        else:
            # No device specified - just delete from database
            result = super().delete(request, *args, **kwargs)
            messages.success(request, _('Employee %(name)s deleted from database only (no device selected)') % {'name': employee_name})
            return result


@manage_employees_required
def sync_to_device(request):
    """Upload employees to device and remove deleted ones"""
    device_id = request.GET.get('device')
    if not device_id:
        messages.error(request, 'Please select a device')
        return redirect('employees:employee_list')

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        messages.error(request, 'Device not found')
        return redirect('employees:employee_list')

    connector = ZKDeviceConnector(device)
    employees = Employee.objects.filter(is_active=True)

    success_count = 0
    error_count = 0
    deleted_count = 0
    errors = []

    try:
        conn = connector.connect()

        # Get current users from device
        device_users = connector.get_users(conn)
        device_user_ids = {user.uid for user in device_users}

        # Get database employee user IDs
        db_user_ids = {emp.user_id for emp in employees}

        # Delete users that are on device but not in database (or inactive)
        users_to_delete = device_user_ids - db_user_ids
        for uid in users_to_delete:
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
                errors.append(f"Failed to delete user {uid}: {str(e)}")

        # Upload/update active employees
        for emp in employees:
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
            except Exception as e:
                error_count += 1
                errors.append(f"{emp.full_name}: {str(e)}")

        conn.disconnect()

        device.last_sync = timezone.now()
        device.save()

        if success_count > 0:
            messages.success(request, _('Successfully synced %(count)d employees to device') % {'count': success_count})
        if deleted_count > 0:
            messages.success(request, _('Removed %(count)d users from device that were deleted from database') % {'count': deleted_count})
        if error_count > 0:
            messages.warning(request, _('%(count)d operations failed') % {'count': error_count})
            for error in errors[:5]:  # Show first 5 errors
                messages.error(request, error)

    except Exception as e:
        messages.error(request, f'Error connecting to device: {str(e)}')

    return redirect('employees:employee_list')


@manage_employees_required
def sync_from_device(request):
    """Download employees from device and their fingerprints"""
    device_id = request.GET.get('device')
    if not device_id:
        messages.error(request, 'Please select a device')
        return redirect('employees:employee_list')

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        messages.error(request, 'Device not found')
        return redirect('employees:employee_list')

    connector = ZKDeviceConnector(device)

    success_count = 0
    updated_count = 0
    error_count = 0
    fingerprints_downloaded = 0

    try:
        conn = connector.connect()
        users = connector.get_users(conn)

        for user in users:
            try:
                # Try to find existing employee
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

                # Download fingerprint templates for this employee
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

            except Exception as e:
                error_count += 1

        conn.disconnect()

        device.last_sync = timezone.now()
        device.save()

        if success_count > 0:
            messages.success(request, f'Added {success_count} new employees from device')
        if updated_count > 0:
            messages.success(request, f'Updated {updated_count} existing employees')
        if fingerprints_downloaded > 0:
            messages.success(request, f'Downloaded {fingerprints_downloaded} fingerprint templates')
        if error_count > 0:
            messages.warning(request, f'{error_count} users failed to import')

    except Exception as e:
        messages.error(request, f'Error connecting to device: {str(e)}')

    return redirect('employees:employee_list')


@manage_employees_required
def sync_single_employee_to_device(request, pk):
    """Upload single employee to device"""
    employee = get_object_or_404(Employee, pk=pk)
    device_id = request.GET.get('device')

    if not device_id:
        messages.error(request, 'Please select a device')
        return redirect('employees:employee_list')

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        messages.error(request, 'Device not found')
        return redirect('employees:employee_list')

    connector = ZKDeviceConnector(device)

    try:
        conn = connector.connect()

        connector.set_user(
            conn=conn,
            uid=employee.user_id,
            name=employee.full_name,
            privilege=employee.privilege,
            password=employee.password or '',
            group_id='0',
            user_id=employee.employee_id
        )

        employee.synced_to_device = True
        employee.device = device
        employee.save()

        conn.disconnect()

        messages.success(request, f'Successfully uploaded {employee.full_name} to {device.name}')

    except Exception as e:
        messages.error(request, f'Error uploading employee: {str(e)}')

    return redirect('employees:employee_list')


@manage_employees_required
def sync_single_employee_from_device(request, pk):
    """Download single employee data and fingerprints from device"""
    employee = get_object_or_404(Employee, pk=pk)
    device_id = request.GET.get('device')

    if not device_id:
        messages.error(request, 'Please select a device')
        return redirect('employees:employee_list')

    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        messages.error(request, 'Device not found')
        return redirect('employees:employee_list')

    connector = ZKDeviceConnector(device)
    fingerprints_downloaded = 0

    try:
        conn = connector.connect()
        users = connector.get_users(conn)

        # Find user on device
        device_user = None
        for user in users:
            if user.uid == employee.user_id:
                device_user = user
                break

        if device_user:
            # Update employee info
            employee.employee_id = device_user.user_id or employee.employee_id
            employee.first_name = device_user.name.split()[0] if device_user.name else employee.first_name
            employee.last_name = ' '.join(device_user.name.split()[1:]) if len(device_user.name.split()) > 1 else employee.last_name
            employee.privilege = device_user.privilege
            employee.password = device_user.password or ''
            employee.synced_to_device = True
            employee.device = device
            employee.save()

            # Download fingerprint templates
            templates = connector.get_all_fingerprint_templates(conn, employee.user_id)
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

            conn.disconnect()

            messages.success(request, f'Successfully downloaded {employee.full_name} from {device.name}')
            if fingerprints_downloaded > 0:
                messages.success(request, f'Downloaded {fingerprints_downloaded} fingerprint templates')
        else:
            conn.disconnect()
            messages.warning(request, f'Employee {employee.full_name} (UID: {employee.user_id}) not found on device')

    except Exception as e:
        messages.error(request, f'Error downloading employee: {str(e)}')

    return redirect('employees:employee_list')


# Fingerprint Management Views

@employee_section_required
def manage_fingerprints(request, pk):
    """Display fingerprint management page for an employee"""
    employee = get_object_or_404(Employee, pk=pk)
    devices = Device.objects.filter(is_active=True)

    # Get current fingerprints for this employee
    fingerprints = Fingerprint.objects.filter(employee=employee).select_related('device')

    # Create a dict of enrolled fingers
    enrolled_fingers = {fp.finger_index: fp for fp in fingerprints}

    context = {
        'employee': employee,
        'devices': devices,
        'finger_map': FINGER_MAP,
        'enrolled_fingers': enrolled_fingers,
    }

    return render(request, 'employees/fingerprint_manage.html', context)


@manage_fingerprints_required
def enroll_fingerprint(request, pk):
    """Start fingerprint enrollment on device"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    employee = get_object_or_404(Employee, pk=pk)
    device_id = request.POST.get('device_id')
    temp_id = request.POST.get('temp_id')

    if not device_id or temp_id is None:
        return JsonResponse({'success': False, 'error': 'Missing device or finger selection'})

    try:
        device = Device.objects.get(pk=device_id)
        temp_id = int(temp_id)

        if temp_id < 0 or temp_id > 9:
            return JsonResponse({'success': False, 'error': 'Invalid finger index'})

        connector = ZKDeviceConnector(device)
        conn = connector.connect()

        # Check if fingerprint already exists, delete it first
        existing_template = connector.get_fingerprint_template(conn, employee.user_id, temp_id)
        if existing_template:
            connector.delete_fingerprint_template(conn, employee.user_id, temp_id)

        # Start enrollment on device
        result = connector.enroll_user_fingerprint(conn, employee.user_id, temp_id)
        conn.disconnect()

        if result:
            return JsonResponse({
                'success': True,
                'message': f'Enrollment started for {FINGER_MAP.get(temp_id)}. Please scan finger on device.'
            })
        else:
            return JsonResponse({'success': False, 'error': 'Failed to start enrollment'})

    except Device.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Device not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@manage_fingerprints_required
def download_fingerprints(request, pk):
    """Download fingerprint templates from device to database"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    employee = get_object_or_404(Employee, pk=pk)
    device_id = request.POST.get('device_id')

    if not device_id:
        return JsonResponse({'success': False, 'error': 'Missing device selection'})

    try:
        device = Device.objects.get(pk=device_id)
        connector = ZKDeviceConnector(device)
        conn = connector.connect()

        # Download all fingerprint templates
        templates = connector.get_all_fingerprint_templates(conn, employee.user_id)
        conn.disconnect()

        # Save to database
        success_count = 0
        for temp_id, template_data in templates.items():
            Fingerprint.objects.update_or_create(
                employee=employee,
                finger_index=temp_id,
                defaults={
                    'template': template_data,
                    'device': device
                }
            )
            success_count += 1

        return JsonResponse({
            'success': True,
            'message': f'Downloaded {success_count} fingerprint templates',
            'count': success_count
        })

    except Device.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Device not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@manage_fingerprints_required
def upload_fingerprints(request, pk):
    """Upload fingerprint templates from database to device"""
    employee = get_object_or_404(Employee, pk=pk)

    # Check if this is a redirect from employee list (GET) or AJAX (POST)
    is_redirect = request.GET.get('redirect') == 'list'

    if request.method == 'GET' and is_redirect:
        # Handle redirect from employee list
        device_id = request.GET.get('device')

        if not device_id:
            messages.error(request, 'Missing device selection')
            return redirect('employees:employee_list')

        try:
            device = Device.objects.get(pk=device_id)
            fingerprints = Fingerprint.objects.filter(employee=employee)

            if not fingerprints.exists():
                messages.warning(request, f'No fingerprints found in database for {employee.full_name}')
                return redirect('employees:employee_list')

            connector = ZKDeviceConnector(device)
            conn = connector.connect()

            # Upload all fingerprints
            success_count = 0
            for fingerprint in fingerprints:
                result = connector.set_fingerprint_template(
                    conn,
                    employee.user_id,
                    fingerprint.finger_index,
                    fingerprint.template
                )
                if result:
                    success_count += 1

            conn.disconnect()

            messages.success(request, f'Uploaded {success_count} fingerprint templates for {employee.full_name} to {device.name}')

        except Device.DoesNotExist:
            messages.error(request, 'Device not found')
        except Exception as e:
            messages.error(request, f'Error uploading fingerprints: {str(e)}')

        return redirect('employees:employee_list')

    # Handle AJAX POST request
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    device_id = request.POST.get('device_id')

    if not device_id:
        return JsonResponse({'success': False, 'error': 'Missing device selection'})

    try:
        device = Device.objects.get(pk=device_id)
        fingerprints = Fingerprint.objects.filter(employee=employee)

        if not fingerprints.exists():
            return JsonResponse({'success': False, 'error': 'No fingerprints found in database'})

        connector = ZKDeviceConnector(device)
        conn = connector.connect()

        # Upload all fingerprints
        success_count = 0
        for fingerprint in fingerprints:
            result = connector.set_fingerprint_template(
                conn,
                employee.user_id,
                fingerprint.finger_index,
                fingerprint.template
            )
            if result:
                success_count += 1

        conn.disconnect()

        return JsonResponse({
            'success': True,
            'message': f'Uploaded {success_count} fingerprint templates to device',
            'count': success_count
        })

    except Device.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Device not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@manage_employees_required
def bulk_delete_from_device(request):
    """Delete multiple employees from device and database"""
    if request.method != 'POST':
        messages.error(request, _('Invalid request method'))
        return redirect('employees:employee_list')

    device_id = request.POST.get('bulk_device')
    employee_ids = request.POST.getlist('employee_ids')
    delete_from_device = request.POST.get('delete_from_device') == 'true'

    if not employee_ids:
        messages.error(request, _('Please select at least one employee'))
        return redirect('employees:employee_list')

    # Get employees to delete
    employees = Employee.objects.filter(pk__in=employee_ids)
    total_count = employees.count()

    if not employees.exists():
        messages.error(request, _('No employees found'))
        return redirect('employees:employee_list')

    # If device deletion is requested
    if delete_from_device:
        if not device_id:
            messages.error(request, _('Please select a device'))
            return redirect('employees:employee_list')

        try:
            device = Device.objects.get(pk=device_id, is_active=True)
        except Device.DoesNotExist:
            messages.error(request, _('Device not found'))
            return redirect('employees:employee_list')

        connector = ZKDeviceConnector(device)
        success_count = 0
        db_delete_count = 0
        error_count = 0
        errors = []

        try:
            conn = connector.connect()

            for employee in employees:
                employee_name = employee.full_name
                try:
                    # Delete from device
                    connector.delete_user(conn, employee.user_id)

                    # Delete fingerprints
                    for finger_idx in range(10):
                        try:
                            connector.delete_fingerprint_template(conn, employee.user_id, finger_idx)
                        except:
                            pass

                    # Delete from database
                    employee.delete()
                    success_count += 1

                except Exception as e:
                    # Still try to delete from database
                    try:
                        employee.delete()
                        db_delete_count += 1
                        errors.append(f"{employee_name}: Deleted from database, but device deletion failed - {str(e)}")
                    except:
                        error_count += 1
                        errors.append(f"{employee_name}: Failed to delete - {str(e)}")

            conn.disconnect()

            if success_count > 0:
                messages.success(request, _('Successfully deleted %(count)d employees from device and database') % {'count': success_count})
            if db_delete_count > 0:
                messages.warning(request, _('%(count)d employees deleted from database only (device deletion failed)') % {'count': db_delete_count})
            if error_count > 0:
                messages.error(request, _('%(count)d employees failed to delete') % {'count': error_count})
                for error in errors[:5]:
                    messages.error(request, error)

        except Exception as e:
            messages.error(request, _('Error connecting to device: %(error)s. No employees were deleted.') % {'error': str(e)})

    else:
        # Delete from database only
        try:
            deleted_count = 0
            employee_names = [emp.full_name for emp in employees[:5]]  # Get first 5 names for display

            for employee in employees:
                employee.delete()
                deleted_count += 1

            if deleted_count > 0:
                if deleted_count <= 5:
                    names_str = ", ".join(employee_names)
                    messages.success(request, _('Successfully deleted %(names)s from database') % {'names': names_str})
                else:
                    messages.success(request, _('Successfully deleted %(count)d employees from database') % {'count': deleted_count})
        except Exception as e:
            messages.error(request, _('Error deleting employees: %(error)s') % {'error': str(e)})

    return redirect('employees:employee_list')


@manage_fingerprints_required
def delete_fingerprint(request, pk):
    """Delete fingerprint from device and database"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Invalid request method'})

    employee = get_object_or_404(Employee, pk=pk)
    device_id = request.POST.get('device_id')
    temp_id = request.POST.get('temp_id')

    if not device_id or temp_id is None:
        return JsonResponse({'success': False, 'error': 'Missing device or finger selection'})

    try:
        device = Device.objects.get(pk=device_id)
        temp_id = int(temp_id)

        if temp_id < 0 or temp_id > 9:
            return JsonResponse({'success': False, 'error': 'Invalid finger index'})

        connector = ZKDeviceConnector(device)
        conn = connector.connect()

        # Delete from device
        connector.delete_fingerprint_template(conn, employee.user_id, temp_id)
        conn.disconnect()

        # Delete from database
        Fingerprint.objects.filter(
            employee=employee,
            finger_index=temp_id
        ).delete()

        return JsonResponse({
            'success': True,
            'message': f'Deleted fingerprint for {FINGER_MAP.get(temp_id)}'
        })

    except Device.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Device not found'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@employee_section_required
def export_employees_csv(request):
    """Export employees to CSV file with all visible fields"""
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'

    # Create CSV writer
    writer = csv.writer(response)

    # Write header row
    writer.writerow([
        'Employee ID',
        'First Name',
        'Last Name',
        'Department',
        'User ID',
        'Card Number',
        'Password',
        'Privilege',
        'Is Active',
        'Device'
    ])

    # Get the same queryset as the list view with filters applied
    queryset = Employee.objects.all()
    search = request.GET.get('search')
    department = request.GET.get('department')
    is_active = request.GET.get('is_active')

    if search:
        queryset = queryset.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(employee_id__icontains=search)
        )

    if department:
        queryset = queryset.filter(department__icontains=department)

    if is_active:
        queryset = queryset.filter(is_active=(is_active == 'true'))

    # Write data rows
    for employee in queryset:
        writer.writerow([
            employee.employee_id,
            employee.first_name,
            employee.last_name,
            employee.department or '',
            employee.user_id,
            employee.card_number or '',
            employee.password or '',
            employee.privilege,
            'Yes' if employee.is_active else 'No',
            employee.device.name if employee.device else ''
        ])

    return response


@manage_employees_required
def import_employees_csv(request):
    """Import employees from CSV file and update based on employee_id, user_id, and device"""
    if request.method != 'POST':
        messages.error(request, _('Invalid request method'))
        return redirect('employees:employee_list')

    if 'csv_file' not in request.FILES:
        messages.error(request, _('Please select a CSV file to upload'))
        return redirect('employees:employee_list')

    csv_file = request.FILES['csv_file']

    # Check file extension
    if not csv_file.name.endswith('.csv'):
        messages.error(request, _('File must be a CSV file'))
        return redirect('employees:employee_list')

    # Read CSV file
    try:
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)

        created_count = 0
        updated_count = 0
        error_count = 0
        errors = []

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (row 1 is header)
            try:
                # Extract and validate required fields
                employee_id = row.get('Employee ID', '').strip()
                user_id_str = row.get('User ID', '').strip()
                first_name = row.get('First Name', '').strip()
                last_name = row.get('Last Name', '').strip()

                if not employee_id or not user_id_str or not first_name:
                    errors.append(f"Row {row_num}: Missing required fields (Employee ID, User ID, or First Name)")
                    error_count += 1
                    continue

                try:
                    user_id = int(user_id_str)
                    if user_id < 1 or user_id > 65535:
                        raise ValueError("User ID must be between 1 and 65535")
                except ValueError as e:
                    errors.append(f"Row {row_num}: Invalid User ID '{user_id_str}' - {str(e)}")
                    error_count += 1
                    continue

                # Get optional fields
                department = row.get('Department', '').strip()
                card_number = row.get('Card Number', '').strip()
                password = row.get('Password', '').strip()

                # Parse privilege (default to 0)
                privilege_str = row.get('Privilege', '0').strip()
                try:
                    privilege = int(privilege_str) if privilege_str else 0
                except ValueError:
                    privilege = 0

                # Parse is_active (default to True)
                is_active_str = row.get('Is Active', 'Yes').strip().lower()
                is_active = is_active_str in ['yes', 'true', '1', 'y']

                # Get device if specified
                device = None
                device_name = row.get('Device', '').strip()
                if device_name:
                    try:
                        device = Device.objects.get(name=device_name, is_active=True)
                    except Device.DoesNotExist:
                        # Try to find by IP address
                        try:
                            device = Device.objects.get(ip_address=device_name, is_active=True)
                        except Device.DoesNotExist:
                            errors.append(f"Row {row_num}: Device '{device_name}' not found")
                            # Continue without device

                # Try to find existing employee by employee_id or user_id
                employee = None
                try:
                    employee = Employee.objects.get(employee_id=employee_id)
                except Employee.DoesNotExist:
                    try:
                        employee = Employee.objects.get(user_id=user_id)
                    except Employee.DoesNotExist:
                        pass

                if employee:
                    # Update existing employee
                    employee.employee_id = employee_id
                    employee.user_id = user_id
                    employee.first_name = first_name
                    employee.last_name = last_name
                    employee.department = department
                    employee.card_number = card_number
                    employee.password = password
                    employee.privilege = privilege
                    employee.is_active = is_active
                    if device:
                        employee.device = device
                    employee.synced_to_device = False  # Mark as not synced since data changed
                    employee.save()
                    updated_count += 1
                else:
                    # Create new employee
                    employee = Employee.objects.create(
                        employee_id=employee_id,
                        user_id=user_id,
                        first_name=first_name,
                        last_name=last_name,
                        department=department,
                        card_number=card_number,
                        password=password,
                        privilege=privilege,
                        is_active=is_active,
                        device=device,
                        synced_to_device=False
                    )
                    created_count += 1

            except Exception as e:
                error_count += 1
                errors.append(f"Row {row_num}: {str(e)}")

        # Show summary messages
        if created_count > 0:
            messages.success(request, _('Created %(count)d new employees') % {'count': created_count})
        if updated_count > 0:
            messages.success(request, _('Updated %(count)d existing employees') % {'count': updated_count})
        if error_count > 0:
            messages.warning(request, _('%(count)d rows had errors') % {'count': error_count})
            for error in errors[:10]:  # Show first 10 errors
                messages.error(request, error)
            if len(errors) > 10:
                messages.error(request, _('... and %(count)d more errors') % {'count': len(errors) - 10})

        if created_count == 0 and updated_count == 0 and error_count == 0:
            messages.info(request, _('No changes were made'))

    except Exception as e:
        messages.error(request, _('Error processing CSV file: %(error)s') % {'error': str(e)})

    return redirect('employees:employee_list')

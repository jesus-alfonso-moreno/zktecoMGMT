from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
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

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Employee deleted successfully!')
        return super().delete(request, *args, **kwargs)


@manage_employees_required
def sync_to_device(request):
    """Upload employees to device"""
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
    errors = []

    try:
        conn = connector.connect()

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
            messages.success(request, f'Successfully synced {success_count} employees to device')
        if error_count > 0:
            messages.warning(request, f'{error_count} employees failed to sync')
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

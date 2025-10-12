from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db.models import Q
from django.utils import timezone
from .models import Employee, Fingerprint
from .forms import EmployeeForm, EmployeeSearchForm
from device.models import Device
from device.zk_connector import ZKDeviceConnector


class EmployeeListView(ListView):
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
        return context


class EmployeeCreateView(CreateView):
    """Create new employee"""
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    success_url = reverse_lazy('employees:employee_list')

    def form_valid(self, form):
        messages.success(self.request, 'Employee created successfully!')
        return super().form_valid(form)


class EmployeeUpdateView(UpdateView):
    """Update existing employee"""
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    success_url = reverse_lazy('employees:employee_list')

    def form_valid(self, form):
        # Mark as not synced if data changed
        if form.has_changed():
            form.instance.synced_to_device = False
        messages.success(self.request, 'Employee updated successfully!')
        return super().form_valid(form)


class EmployeeDeleteView(DeleteView):
    """Delete employee"""
    model = Employee
    template_name = 'employees/employee_confirm_delete.html'
    success_url = reverse_lazy('employees:employee_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Employee deleted successfully!')
        return super().delete(request, *args, **kwargs)


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


def sync_from_device(request):
    """Download employees from device"""
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

    try:
        conn = connector.connect()
        users = connector.get_users(conn)
        conn.disconnect()

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
            except Exception as e:
                error_count += 1

        device.last_sync = timezone.now()
        device.save()

        if success_count > 0:
            messages.success(request, f'Added {success_count} new employees from device')
        if updated_count > 0:
            messages.success(request, f'Updated {updated_count} existing employees')
        if error_count > 0:
            messages.warning(request, f'{error_count} users failed to import')

    except Exception as e:
        messages.error(request, f'Error connecting to device: {str(e)}')

    return redirect('employees:employee_list')

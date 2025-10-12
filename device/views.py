from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse
from django.utils import timezone
from .models import Device
from .forms import DeviceForm
from .zk_connector import ZKDeviceConnector


class DeviceListView(ListView):
    """List all devices"""
    model = Device
    template_name = 'device/device_list.html'
    context_object_name = 'devices'
    paginate_by = 10


class DeviceCreateView(CreateView):
    """Create new device"""
    model = Device
    form_class = DeviceForm
    template_name = 'device/device_form.html'
    success_url = reverse_lazy('device:device_list')

    def form_valid(self, form):
        messages.success(self.request, 'Device created successfully!')
        return super().form_valid(form)


class DeviceUpdateView(UpdateView):
    """Update existing device"""
    model = Device
    form_class = DeviceForm
    template_name = 'device/device_form.html'
    success_url = reverse_lazy('device:device_list')

    def form_valid(self, form):
        messages.success(self.request, 'Device updated successfully!')
        return super().form_valid(form)


class DeviceDeleteView(DeleteView):
    """Delete device"""
    model = Device
    template_name = 'device/device_confirm_delete.html'
    success_url = reverse_lazy('device:device_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Device deleted successfully!')
        return super().delete(request, *args, **kwargs)


def test_connection(request, pk):
    """Test device connection via AJAX"""
    device = get_object_or_404(Device, pk=pk)

    try:
        connector = ZKDeviceConnector(device)
        success, message = connector.test_connection()

        return JsonResponse({
            'success': success,
            'message': message
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


def device_info(request, pk):
    """Show detailed device information"""
    device = get_object_or_404(Device, pk=pk)
    info = None
    error = None

    try:
        connector = ZKDeviceConnector(device)
        conn = connector.connect()
        info = connector.get_device_info(conn)

        # Update device with fetched info
        device.serial_number = info['serial_number']
        device.firmware_version = info['firmware_version']
        device.last_sync = timezone.now()
        device.save()

        conn.disconnect()
        messages.success(request, 'Device information retrieved successfully!')
    except Exception as e:
        error = str(e)
        messages.error(request, f'Error retrieving device info: {error}')

    context = {
        'device': device,
        'info': info,
        'error': error,
    }
    return render(request, 'device/device_info.html', context)

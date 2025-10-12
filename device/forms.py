from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import Device


class DeviceForm(forms.ModelForm):
    """Form for creating and editing devices"""

    class Meta:
        model = Device
        fields = ['name', 'ip_address', 'port', 'device_id', 'password', 'force_udp', 'ommit_ping', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g., Main Office K40'}),
            'ip_address': forms.TextInput(attrs={'placeholder': 'e.g., 192.168.1.201'}),
            'port': forms.NumberInput(attrs={'placeholder': '4370'}),
            'device_id': forms.NumberInput(attrs={'placeholder': '1'}),
            'password': forms.PasswordInput(attrs={'placeholder': 'Leave blank if no password'}),
        }
        help_texts = {
            'port': 'Default port is 4370',
            'device_id': 'Device ID (usually 1)',
            'password': 'Communication password (if device requires authentication)',
            'force_udp': 'Use UDP protocol instead of TCP (for some older devices)',
            'ommit_ping': 'Skip initial ping test (useful if device does not respond to ping)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Save Device', css_class='btn-primary'))

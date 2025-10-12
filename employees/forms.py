from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .models import Employee


class EmployeeForm(forms.ModelForm):
    """Form for creating and editing employees"""

    class Meta:
        model = Employee
        fields = [
            'employee_id', 'user_id', 'first_name', 'last_name',
            'department', 'card_number', 'password', 'privilege',
            'is_active', 'device'
        ]
        widgets = {
            'employee_id': forms.TextInput(attrs={'placeholder': 'e.g., EMP001'}),
            'user_id': forms.NumberInput(attrs={'placeholder': 'Device User ID (1-65535)'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Last name'}),
            'department': forms.TextInput(attrs={'placeholder': 'e.g., IT Department'}),
            'card_number': forms.TextInput(attrs={'placeholder': 'Card number (optional)'}),
            'password': forms.TextInput(attrs={'placeholder': 'Device password (optional)'}),
            'privilege': forms.Select(choices=[(0, 'User'), (14, 'Admin')]),
        }
        help_texts = {
            'user_id': 'Unique ID for the device (1-65535)',
            'privilege': 'Admin users can manage the device',
            'password': 'Password for device access (not web login)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', 'Save Employee', css_class='btn-primary'))


class EmployeeSearchForm(forms.Form):
    """Form for searching employees"""
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Search by name, employee ID...',
            'class': 'form-control'
        })
    )
    department = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'Department',
            'class': 'form-control'
        })
    )
    is_active = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('true', 'Active'), ('false', 'Inactive')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

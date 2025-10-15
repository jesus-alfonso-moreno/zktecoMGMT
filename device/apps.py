from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DeviceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'device'
    verbose_name = _('Devices')

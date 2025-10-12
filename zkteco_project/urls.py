"""
URL configuration for zkteco_project project.
"""
from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('device/', include('device.urls')),
    path('employees/', include('employees.urls')),
    path('attendance/', include('attendance.urls')),
]

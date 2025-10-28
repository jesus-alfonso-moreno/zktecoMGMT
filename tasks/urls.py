from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Task initiation endpoints
    path('sync-to-device/<int:device_id>/', views.start_sync_to_device, name='start_sync_to_device'),
    path('sync-from-device/<int:device_id>/', views.start_sync_from_device, name='start_sync_from_device'),
    path('download-attendance/<int:device_id>/', views.start_download_attendance, name='start_download_attendance'),

    # Progress polling endpoint
    path('status/<str:task_id>/', views.task_status, name='task_status'),
]

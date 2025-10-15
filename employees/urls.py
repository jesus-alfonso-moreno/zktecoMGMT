from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    path('', views.EmployeeListView.as_view(), name='employee_list'),
    path('add/', views.EmployeeCreateView.as_view(), name='employee_add'),
    path('<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='employee_edit'),
    path('<int:pk>/delete/', views.EmployeeDeleteView.as_view(), name='employee_delete'),

    # Bulk sync operations
    path('sync-to-device/', views.sync_to_device, name='sync_to_device'),
    path('sync-from-device/', views.sync_from_device, name='sync_from_device'),
    path('bulk-delete/', views.bulk_delete_from_device, name='bulk_delete_from_device'),

    # CSV import/export
    path('export-csv/', views.export_employees_csv, name='export_csv'),
    path('import-csv/', views.import_employees_csv, name='import_csv'),

    # Single employee sync operations
    path('<int:pk>/sync-to-device/', views.sync_single_employee_to_device, name='sync_single_to_device'),
    path('<int:pk>/sync-from-device/', views.sync_single_employee_from_device, name='sync_single_from_device'),

    # Fingerprint management URLs
    path('<int:pk>/fingerprints/', views.manage_fingerprints, name='manage_fingerprints'),
    path('<int:pk>/fingerprints/enroll/', views.enroll_fingerprint, name='enroll_fingerprint'),
    path('<int:pk>/fingerprints/download/', views.download_fingerprints, name='download_fingerprints'),
    path('<int:pk>/fingerprints/upload/', views.upload_fingerprints, name='upload_fingerprints'),
    path('<int:pk>/fingerprints/delete/', views.delete_fingerprint, name='delete_fingerprint'),
]

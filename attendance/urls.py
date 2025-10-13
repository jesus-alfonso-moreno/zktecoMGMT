from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.AttendanceListView.as_view(), name='attendance_list'),
    path('download/', views.download_attendance, name='download_attendance'),
    path('report/', views.attendance_report, name='attendance_report'),
    path('report/export/', views.export_attendance_report, name='export_report'),
    path('export/', views.export_attendance, name='export_attendance'),
]

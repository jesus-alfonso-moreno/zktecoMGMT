from django.urls import path
from . import views

app_name = 'device'

urlpatterns = [
    path('', views.DeviceListView.as_view(), name='device_list'),
    path('add/', views.DeviceCreateView.as_view(), name='device_add'),
    path('<int:pk>/edit/', views.DeviceUpdateView.as_view(), name='device_edit'),
    path('<int:pk>/delete/', views.DeviceDeleteView.as_view(), name='device_delete'),
    path('<int:pk>/test/', views.test_connection, name='test_connection'),
    path('<int:pk>/info/', views.device_info, name='device_info'),
]

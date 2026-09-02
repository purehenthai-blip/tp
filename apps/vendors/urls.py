from django.urls import path
from . import views

app_name = 'vendors'

urlpatterns = [
    path('', views.vendor_directory, name='directory'),
    path('apply/', views.vendor_apply, name='apply'),
    path('dashboard/', views.vendor_dashboard, name='dashboard'),
    path('<slug:shop_slug>/', views.vendor_profile_public, name='profile'),
]

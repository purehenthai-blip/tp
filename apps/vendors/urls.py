from django.urls import path
from . import views

app_name = 'vendors'

urlpatterns = [
    path('', views.vendor_directory, name='directory'),
    path('apply/', views.vendor_apply, name='apply'),
    path('dashboard/', views.vendor_dashboard, name='dashboard'),
    path('dashboard/categories/', views.vendor_categories, name='categories'),
    path('dashboard/categories/create/', views.vendor_category_create, name='category_create'),
    path('dashboard/categories/<uuid:category_id>/edit/', views.vendor_category_edit, name='category_edit'),
    path('dashboard/categories/<uuid:category_id>/delete/', views.vendor_category_delete, name='category_delete'),
    path('<slug:shop_slug>/', views.vendor_profile_public, name='profile'),
]

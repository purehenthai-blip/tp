from django.urls import path
from . import views

app_name = 'listings'

urlpatterns = [
    # IMPORTANT: specific paths BEFORE uuid patterns
    path('', views.listing_list, name='list'),
    path('create/', views.vendor_listing_create, name='create'),

    # UUID patterns
    path('<uuid:listing_id>/', views.listing_detail, name='detail'),
    path('<uuid:listing_id>/edit/', views.vendor_listing_edit, name='edit'),
    path('<uuid:listing_id>/upload-file/', views.upload_listing_file, name='upload_file'),
    path('<uuid:listing_id>/files/<uuid:file_id>/delete/', views.delete_listing_file, name='delete_file'),
    path('files/<uuid:file_id>/download/', views.download_listing_file, name='download_file'),
]

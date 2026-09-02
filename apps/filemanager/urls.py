from django.urls import path
from . import views

app_name = 'filemanager'

urlpatterns = [
    path('', views.file_manager, name='home'),
    path('upload/', views.upload_file, name='upload'),
    path('<uuid:file_id>/download/', views.download_file, name='download'),
    path('<uuid:file_id>/delete/', views.delete_file, name='delete'),
    path('<uuid:file_id>/rename/', views.rename_file, name='rename'),
    path('folder/create/', views.create_folder, name='create_folder'),
    path('folder/<uuid:folder_id>/delete/', views.delete_folder, name='delete_folder'),
    path('folder/<uuid:folder_id>/rename/', views.rename_folder, name='rename_folder'),
]

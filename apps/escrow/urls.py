from django.urls import path
from . import views

app_name = 'escrow'

urlpatterns = [
    path('', views.escrow_list, name='list'),
    path('<uuid:escrow_id>/', views.escrow_detail, name='detail'),
    path('<uuid:escrow_id>/release/', views.release_escrow, name='release'),
]

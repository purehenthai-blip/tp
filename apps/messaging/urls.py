from django.urls import path
from . import views

app_name = 'messaging'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('new/', views.new_thread, name='new_thread'),
    path('<uuid:thread_id>/', views.thread_detail, name='thread'),
    path('<uuid:thread_id>/send/', views.send_message, name='send'),
]

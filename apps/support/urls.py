from django.urls import path
from . import views

app_name = 'support'

urlpatterns = [
    path('', views.ticket_list, name='list'),
    path('new/', views.new_ticket, name='new'),
    path('dashboard/', views.support_dashboard, name='dashboard'),
    path('<uuid:ticket_id>/', views.ticket_detail, name='detail'),
    path('<uuid:ticket_id>/reply/', views.reply_ticket, name='reply'),
    path('faq/', views.faq, name='faq'),
    path('escrow-guide/', views.escrow_guide, name='escrow_guide'),
]

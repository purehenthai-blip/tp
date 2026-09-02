from django.urls import path
from . import views

app_name = 'wallet'

urlpatterns = [
    path('',           views.wallet_home,      name='home'),
    path('deposit/',   views.submit_deposit,   name='deposit'),
    path('withdraw/',  views.request_withdrawal, name='withdraw'),
    path('history/',   views.transaction_history, name='transactions'),
]

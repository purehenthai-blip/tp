from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('crypto-addresses/', views.save_crypto_addresses, name='crypto_addresses'),
    path('set-theme/', views.set_theme, name='set_theme'),
    path('set-language/', views.set_language, name='set_language'),
    path('schedule-deletion/', views.schedule_account_deletion, name='schedule_deletion'),
    path('cancel-deletion/', views.cancel_account_deletion, name='cancel_deletion'),
]

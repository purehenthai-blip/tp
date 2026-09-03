from django.urls import path
from . import views
from apps.cron.views import cron_dashboard

app_name = 'admin_panel'

urlpatterns = [
    path('', views.admin_dashboard, name='dashboard'),
    # Users
    path('users/', views.admin_user_list, name='user_list'),
    path('users/<uuid:user_id>/edit/', views.admin_user_edit, name='user_edit'),
    # Vendors
    path('vendors/', views.admin_vendors_list, name='vendors'),
    path('vendors/<uuid:user_id>/approve/', views.admin_vendor_approve, name='vendor_approve'),
    path('vendors/<uuid:user_id>/reject/', views.admin_vendor_reject, name='vendor_reject'),
    # Listings
    path('listings/', views.admin_listings_list, name='listings'),
    path('categories/', views.admin_categories, name='categories'),
    path('categories/create/', views.admin_category_create, name='category_create'),
    path('categories/<uuid:category_id>/edit/', views.admin_category_edit, name='category_edit'),
    path('categories/<uuid:category_id>/delete/', views.admin_category_delete, name='category_delete'),
    path('listings/<uuid:listing_id>/approve/', views.admin_listing_approve, name='listing_approve'),
    path('listings/<uuid:listing_id>/reject/',  views.admin_listing_reject,  name='listing_reject'),
    path('approval-rules/', views.admin_approval_rules, name='approval_rules'),
    # Orders
    path('orders/', views.admin_orders_list, name='orders'),
    # Escrow
    path('escrow/', views.admin_escrow_list, name='escrow'),
    # Tickets
    path('tickets/', views.admin_tickets_list, name='tickets'),
    # Auctions
    path('auctions/', views.admin_auctions_list, name='auctions'),
    # Withdrawals
    path('withdrawals/', views.admin_withdrawals, name='withdrawals'),
    path('withdrawals/<uuid:withdrawal_id>/approve/', views.admin_withdrawal_approve, name='withdrawal_approve'),
    path('withdrawals/<uuid:withdrawal_id>/reject/',  views.admin_withdrawal_reject,  name='withdrawal_reject'),
    # Deposits
    path('deposits/', views.admin_deposits, name='deposits'),
    path('deposits/<uuid:deposit_id>/approve/', views.admin_deposit_approve, name='deposit_approve'),
    path('deposits/<uuid:deposit_id>/reject/',  views.admin_deposit_reject,  name='deposit_reject'),
    # Platform Wallet
    path('platform-wallet/', views.admin_platform_wallet, name='platform_wallet'),
    # Config
    path('config/', views.admin_site_config, name='site_config'),
    path('audit-log/', views.admin_audit_log, name='audit_log'),
    path('translations/', views.admin_translation_manager, name='translations'),
    path('cron/', cron_dashboard, name='cron'),
    path('cron/run/', cron_dashboard, name='cron_run'),
]

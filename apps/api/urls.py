"""
ToasterPants REST API URLs
============================
All the endpoints. Fully documented below.
JWT-protected where it matters. TP
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from . import views

router = DefaultRouter()
router.register(r'listings', views.ListingViewSet, basename='listing')
router.register(r'orders', views.OrderViewSet, basename='order')

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('auth/token/', views.ToasterPantsTokenView.as_view(), name='token_obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/token/blacklist/', TokenBlacklistView.as_view(), name='token_blacklist'),

    # ── ViewSets ──────────────────────────────────────────────────────────────
    path('', include(router.urls)),

    # ── Auction ───────────────────────────────────────────────────────────────
    path('auctions/<uuid:auction_id>/status/', views.auction_status, name='auction_status'),
    path('auctions/<uuid:auction_id>/bid/', views.place_bid, name='place_bid'),

    # ── Messaging ─────────────────────────────────────────────────────────────
    path('messages/', views.my_threads, name='my_threads'),

    # ── Reseller ──────────────────────────────────────────────────────────────
    path('reseller/upgrade/', views.request_reseller_upgrade, name='reseller_upgrade'),
    path('reseller/daily-status/', views.reseller_daily_status, name='reseller_daily_status'),

    # ── Admin-only ────────────────────────────────────────────────────────────
    path('admin/escrow/<uuid:escrow_id>/release/', views.admin_release_escrow, name='admin_release_escrow'),
    path('admin/deposit/confirm/', views.admin_confirm_deposit, name='admin_confirm_deposit'),
    path('admin/cron/run/', views.admin_run_cron, name='admin_run_cron'),
    path('admin/translate/', views.auto_translate, name='auto_translate'),
]

# API Documentation (human-readable)
from apps.api.views import api_docs
urlpatterns += [
    path('docs/', api_docs, name='api_docs'),
]

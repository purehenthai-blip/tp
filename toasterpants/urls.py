from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from apps.accounts import views as av

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('api/v1/', include('apps.api.urls')),
    # Registered outside i18n_patterns so /terms/ and /privacy/ ALWAYS resolve
    path('terms/', av.terms_of_service, name='terms_direct'),
    path('privacy/', av.privacy_policy, name='privacy_direct'),
]

urlpatterns += i18n_patterns(
    path('', av.homepage, name='home'),
    path('dashboard/', av.dashboard, name='dashboard'),
    path('terms/', av.terms_of_service, name='terms'),
    path('leaderboard/', av.leaderboard, name='leaderboard'),
    path('privacy/', av.privacy_policy, name='privacy'),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('vendors/', include('apps.vendors.urls', namespace='vendors')),
    path('listings/', include('apps.listings.urls', namespace='listings')),
    path('auctions/', include('apps.auctions.urls', namespace='auctions')),
    path('orders/', include('apps.orders.urls', namespace='orders')),
    path('escrow/', include('apps.escrow.urls', namespace='escrow')),
    path('messages/', include('apps.messaging.urls', namespace='messaging')),
    path('reviews/', include('apps.reviews.urls', namespace='reviews')),
    path('support/', include('apps.support.urls', namespace='support')),
    path('wallet/', include('apps.wallet.urls', namespace='wallet')),
    path('files/', include('apps.filemanager.urls', namespace='filemanager')),
    path('admin-panel/', include('apps.accounts.admin_urls', namespace='admin_panel')),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

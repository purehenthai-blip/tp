"""
ToasterPants — Global Template Context
Injects platform-wide variables into every template.
"""
from apps.accounts.models import SiteConfig


def global_context(request):
    """Available in every template automatically."""
    try:
        announcement = SiteConfig.get('SITE_ANNOUNCEMENT', '')
        site_name    = SiteConfig.get('SITE_NAME', 'ToasterPants')
        coin_value   = SiteConfig.get('TP_COIN_VALUE_USD', '10.00')
    except Exception:
        announcement = ''
        site_name    = 'ToasterPants'
        coin_value   = '10.00'

    unread_count = 0
    if request.user.is_authenticated:
        try:
            from apps.messaging.models import MessageThread
            unread_count = MessageThread.objects.filter(
                participants=request.user,
                messages__is_read=False
            ).exclude(
                messages__sender=request.user
            ).distinct().count()
        except Exception:
            unread_count = 0

    return {
        'site_name':            site_name,
        'site_announcement':    announcement,
        'coin_value_usd':       coin_value,
        'current_theme':        getattr(request.user, 'theme', 'dark') if request.user.is_authenticated else 'dark',
        'unread_message_count': unread_count,
    }

"""
ToasterPants — Accounts Middleware
=====================================
LastActiveMiddleware: updates user's last_active timestamp.
ThemeMiddleware: ensures theme is available on every request.
These two were referenced in settings.py but the file was never created. Oops. TP
"""

from django.utils import timezone


class LastActiveMiddleware:
    """
    Update user's last_active timestamp on every authenticated request.
    Throttled to once per 5 minutes to avoid hammering the DB.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            last = request.session.get('last_active_update')
            now = timezone.now()
            should_update = True
            if last:
                try:
                    from datetime import datetime, timezone as dt_timezone
                    last_dt = datetime.fromisoformat(last)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=dt_timezone.utc)
                    if (now - last_dt).total_seconds() < 300:
                        should_update = False
                except Exception:
                    pass
            if should_update:
                try:
                    request.user.last_active = now
                    request.user.save(update_fields=['last_active'])
                    request.session['last_active_update'] = now.isoformat()
                except Exception:
                    pass  # Never crash a request over this
        return self.get_response(request)


class ThemeMiddleware:
    """
    Makes the current theme available on every request object.
    Authenticated users get their saved theme; guests get session/default.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            request.theme = getattr(request.user, 'theme', 'dark')
        else:
            request.theme = request.session.get('theme', 'dark')
        return self.get_response(request)

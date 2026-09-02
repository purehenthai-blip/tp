"""
ToasterPants Celery Configuration
Background tasks are the unsung heroes of every marketplace.
They work while you sleep. Like a toaster, but digital. TP️
"""

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'toasterpants.settings')

app = Celery('toasterpants')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ─── SCHEDULED TASKS (Cron Jobs) ──────────────────────────────────────────────
app.conf.beat_schedule = {
    # Auto-delete inactive accounts with low balance every day at 2 AM
    'auto-delete-inactive-accounts': {
        'task': 'apps.cron.tasks.delete_inactive_accounts',
        'schedule': crontab(hour=2, minute=0),
    },
    # Check and expire listings every hour
    'expire-listings': {
        'task': 'apps.cron.tasks.expire_listings',
        'schedule': crontab(minute=0),
    },
    # Complete ended auctions every minute (anti-sniping needs precision)
    'complete-auctions': {
        'task': 'apps.cron.tasks.complete_ended_auctions',
        'schedule': crontab(minute='*/1'),
    },
    # Auto-release escrow funds every hour
    'auto-release-escrow': {
        'task': 'apps.cron.tasks.auto_release_escrow',
        'schedule': crontab(minute=30),
    },
    # Daily maintenance at 3 AM
    'daily-maintenance': {
        'task': 'apps.cron.tasks.daily_maintenance',
        'schedule': crontab(hour=3, minute=0),
    },
    # Send overdue delivery notifications every 6 hours
    'delivery-notifications': {
        'task': 'apps.cron.tasks.send_delivery_notifications',
        'schedule': crontab(hour='*/6', minute=0),
    },
    # Clean up old message attachments every Sunday at 4 AM
    'cleanup-attachments': {
        'task': 'apps.cron.tasks.cleanup_old_attachments',
        'schedule': crontab(hour=4, minute=0, day_of_week=0),
    },
}

app.conf.timezone = 'UTC'

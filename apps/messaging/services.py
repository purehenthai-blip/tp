"""
ToasterPants — Messaging Services
====================================
Re-exports from accounts.services so cron tasks can import cleanly.
"""
from apps.accounts.services import send_system_message

__all__ = ['send_system_message']

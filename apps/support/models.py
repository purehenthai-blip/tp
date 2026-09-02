"""
ToasterPants — Support App
============================
Ticket system imported from messaging models for clean app separation.
"""

# Re-export from messaging for convenience - actual Ticket model lives in messaging
from apps.messaging.models import Ticket, TicketMessage, TicketAttachment

__all__ = ['Ticket', 'TicketMessage', 'TicketAttachment']

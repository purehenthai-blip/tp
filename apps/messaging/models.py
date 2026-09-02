"""
ToasterPants — Messaging, Reviews & Support Models
======================================================
Talk to vendors without revealing yourself.
Leave reviews. Open tickets. Stay anonymous.
This is the social layer of ToasterPants. TP
"""

import uuid
import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.accounts.models import User
from apps.listings.models import Listing
from apps.vendors.models import VendorProfile


# ══════════════════════════════════════════════════════════════════
# MESSAGING
# ══════════════════════════════════════════════════════════════════

def message_attachment_path(instance, filename):
    return f"messages/{instance.thread.id}/{filename}"


class MessageThread(models.Model):
    """
    A private messaging thread between buyer and vendor.
    Both parties see anonymous display names only.
    Admin can view and moderate all threads.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    participants = models.ManyToManyField(User, related_name='message_threads')
    subject = models.CharField(max_length=200, blank=True)
    related_order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='message_threads')
    related_listing = models.ForeignKey(Listing, on_delete=models.SET_NULL,
                                        null=True, blank=True)
    is_admin_thread = models.BooleanField(default=False, help_text="Thread involves admin/support")
    is_flagged = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Thread: {self.subject or self.id}"

    @property
    def last_message(self):
        return self.messages.order_by('-timestamp').first()


class Message(models.Model):
    """Individual message within a thread."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(MessageThread, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sent_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    is_flagged = models.BooleanField(default=False)
    is_deleted_by_sender = models.BooleanField(default=False)
    admin_removed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Message from {self.sender.display if self.sender else 'deleted'} at {self.timestamp}"


class MessageAttachment(models.Model):
    """Files attached to messages."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=message_attachment_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def delete(self, *args, **kwargs):
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        super().delete(*args, **kwargs)


# ══════════════════════════════════════════════════════════════════
# REVIEWS
# ══════════════════════════════════════════════════════════════════

class Review(models.Model):
    """
    Product reviews. Verified purchase badge = they actually bought it.
    Vendors cannot see reviewer identity.
    Admin can moderate/remove reviews.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='reviews')
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reviews_given')
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=200, blank=True)
    comment = models.TextField()
    verified_purchase = models.BooleanField(default=False)
    is_published = models.BooleanField(default=True)
    is_flagged = models.BooleanField(default=False)
    admin_removed = models.BooleanField(default=False)
    vendor_reply = models.TextField(blank=True)
    vendor_replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        # One review per buyer per listing
        unique_together = ('listing', 'buyer')
        indexes = [
            models.Index(fields=['listing', 'is_published']),
        ]

    def __str__(self):
        return f"Review: {self.rating} on {self.listing.title}"


class VendorReview(models.Model):
    """Overall vendor shop reviews — separate from per-listing reviews."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name='shop_reviews')
    buyer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='vendor_reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    verified_purchase = models.BooleanField(default=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vendor', 'buyer')

    def __str__(self):
        return f"Vendor Review: {self.rating} for {self.vendor.shop_name}"


# ══════════════════════════════════════════════════════════════════
# SUPPORT TICKETS
# ══════════════════════════════════════════════════════════════════

def ticket_attachment_path(instance, filename):
    return f"tickets/{instance.ticket.id}/{filename}"


class Ticket(models.Model):
    """
    Support tickets. Filed by users. Handled by support staff and admin.
    No impersonation. Support can only respond, not act on behalf of users.
    """

    class Status(models.TextChoices):
        OPEN = 'open', _('Open')
        IN_PROGRESS = 'in_progress', _('In Progress')
        WAITING_USER = 'waiting_user', _('Waiting on User')
        RESOLVED = 'resolved', _('Resolved')
        CLOSED = 'closed', _('Closed')

    class Priority(models.TextChoices):
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')
        URGENT = 'urgent', _('Urgent')

    class Category(models.TextChoices):
        ORDER = 'order', _('Order Issue')
        PAYMENT = 'payment', _('Payment / Escrow')
        ACCOUNT = 'account', _('Account')
        DISPUTE = 'dispute', _('Dispute')
        TECHNICAL = 'technical', _('Technical')
        ABUSE = 'abuse', _('Report Abuse')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_number = models.CharField(max_length=20, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='tickets')
    subject = models.CharField(max_length=300)
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    related_order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='assigned_tickets')
    is_anonymous = models.BooleanField(default=False)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority']),
            models.Index(fields=['user', 'status']),
        ]

    def __str__(self):
        return f"Ticket #{self.ticket_number}: {self.subject}"

    def save(self, *args, **kwargs):
        if not self.ticket_number:
            import random, string
            self.ticket_number = 'TKT-' + ''.join(random.choices(string.digits, k=8))
        super().save(*args, **kwargs)


class TicketMessage(models.Model):
    """Messages within a support ticket thread."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ticket_messages')
    content = models.TextField()
    is_internal_note = models.BooleanField(default=False, help_text="Internal admin/support notes, not visible to user")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"TicketMsg #{self.ticket.ticket_number} by {self.sender.username if self.sender else 'system'}"


class TicketAttachment(models.Model):
    """Files attached to ticket messages."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket_message = models.ForeignKey(TicketMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=ticket_attachment_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

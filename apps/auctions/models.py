"""
ToasterPants — Auctions App Models
Anti-sniping. Auto-extension. Minimum increments. TP⏰
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from apps.accounts.models import User
from apps.listings.models import Listing


class Auction(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', _('Scheduled')
        ACTIVE = 'active', _('Active')
        EXTENDED = 'extended', _('Extended (Anti-Snipe)')
        ENDED = 'ended', _('Ended')
        CANCELLED = 'cancelled', _('Cancelled')
        AWAITING_PAYMENT = 'awaiting_payment', _('Awaiting Payment')
        COMPLETED = 'completed', _('Completed')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name='auction')
    start_price = models.DecimalField(max_digits=18, decimal_places=8,
                                      validators=[MinValueValidator(Decimal('0.00000001'))])
    reserve_price = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    current_bid = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00'))
    min_bid_increment = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.01'))
    buyout_price = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    original_end_time = models.DateTimeField()
    extension_count = models.PositiveIntegerField(default=0)
    total_extension_minutes = models.PositiveIntegerField(default=0)
    anti_sniping = models.BooleanField(default=True)
    auto_extend = models.BooleanField(default=True)
    snipe_window_minutes = models.PositiveIntegerField(default=10)
    extension_minutes = models.PositiveIntegerField(default=10)
    max_extensions = models.PositiveIntegerField(default=5)
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='won_auctions')
    reserve_met = models.BooleanField(default=False)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.SCHEDULED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Auction')
        indexes = [models.Index(fields=['status', 'end_time'])]

    def __str__(self):
        return f"Auction: {self.listing.title} (ends {self.end_time})"

    @property
    def is_active(self):
        now = timezone.now()
        return self.status in [self.Status.ACTIVE, self.Status.EXTENDED] and \
               self.start_time <= now <= self.end_time

    @property
    def seconds_remaining(self):
        if not self.is_active:
            return 0
        return max(0, int((self.end_time - timezone.now()).total_seconds()))

    @property
    def minimum_next_bid(self):
        base = self.current_bid if self.current_bid > 0 else self.start_price
        return base + self.min_bid_increment

    def should_extend(self):
        if not self.anti_sniping or not self.auto_extend:
            return False
        if self.extension_count >= self.max_extensions:
            return False
        time_left = (self.end_time - timezone.now()).total_seconds() / 60
        return time_left <= self.snipe_window_minutes

    def extend(self):
        import datetime
        self.end_time = self.end_time + datetime.timedelta(minutes=self.extension_minutes)
        self.extension_count += 1
        self.total_extension_minutes += self.extension_minutes
        self.status = self.Status.EXTENDED
        self.save(update_fields=['end_time', 'extension_count', 'total_extension_minutes', 'status'])


class Bid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids')
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids')
    bid_amount = models.DecimalField(max_digits=18, decimal_places=8)
    is_winning = models.BooleanField(default=False)
    is_auto_bid = models.BooleanField(default=False)
    max_auto_bid = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    triggered_extension = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-bid_amount', '-timestamp']
        indexes = [
            models.Index(fields=['auction', '-bid_amount']),
            models.Index(fields=['auction', 'bidder']),
        ]

    def __str__(self):
        return f"Bid {self.bid_amount} on {self.auction.listing.title} by {self.bidder.display}"

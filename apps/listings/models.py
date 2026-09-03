"""
ToasterPants — Listings App Models
"""
import uuid
import os
from decimal import Decimal
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from apps.accounts.models import User
from apps.vendors.models import VendorProfile


def listing_file_path(instance, filename):
    return f"listings/{instance.listing.vendor.user.id}/{instance.listing.id}/{filename}"


class ListingCategory(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name        = models.CharField(max_length=100)
    slug        = models.SlugField()
    vendor      = models.ForeignKey(
        'vendors.VendorProfile',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='categories',
    )
    parent      = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='children')
    icon        = models.CharField(max_length=50, blank=True, help_text="Lucide icon name e.g. 'hard-drive'")
    is_active   = models.BooleanField(default=True)
    sort_order  = models.PositiveIntegerField(default=0)
    # Category listing limits
    max_listings_per_vendor = models.PositiveIntegerField(
        default=50, help_text="Max listings a single vendor can have in this category")
    min_price_usd = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.01'),
        help_text="Minimum listing price in USD for this category")

    class Meta:
        verbose_name_plural = 'Listing Categories'
        ordering = ['sort_order', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['slug'],
                condition=Q(vendor__isnull=True),
                name='unique_platform_category_slug',
            ),
            models.UniqueConstraint(
                fields=['vendor', 'slug'],
                name='unique_vendor_category_slug',
            ),
        ]

    def __str__(self):
        return f"{self.parent.name} → {self.name}" if self.parent else self.name

    def vendor_listing_count(self, vendor):
        return Listing.objects.filter(
            vendor=vendor, category=self
        ).exclude(status__in=['deleted', 'suspended']).count()


class Listing(models.Model):

    class Type(models.TextChoices):
        DIGITAL  = 'digital',  _('Digital')
        PHYSICAL = 'physical', _('Physical')
        SERVICE  = 'service',  _('Service')

    class Status(models.TextChoices):
        DRAFT          = 'draft',          _('Draft')
        PENDING_REVIEW = 'pending_review', _('Pending Review')
        ACTIVE         = 'active',         _('Active')
        SOLD_OUT       = 'sold_out',       _('Sold Out')
        EXPIRED        = 'expired',        _('Expired')
        SUSPENDED      = 'suspended',      _('Suspended by Admin')
        DELETED        = 'deleted',        _('Deleted')

    class PriceType(models.TextChoices):
        FIXED   = 'fixed',   _('Fixed Price')
        AUCTION = 'auction', _('Auction')

    class Condition(models.TextChoices):
        NEW       = 'new',       _('New')
        LIKE_NEW  = 'like_new',  _('Like New')
        GOOD      = 'good',      _('Good')
        FAIR      = 'fair',      _('Fair')
        POOR      = 'poor',      _('Poor')
        NA        = 'na',        _('N/A (Digital/Service)')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor      = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name='listings')
    listing_type = models.CharField(max_length=20, choices=Type.choices, default=Type.DIGITAL)
    price_type  = models.CharField(max_length=10, choices=PriceType.choices, default=PriceType.FIXED)

    # Content
    title                = models.CharField(max_length=200)
    description          = models.TextField()
    tags                 = models.CharField(max_length=500, blank=True)
    category             = models.ForeignKey(ListingCategory, on_delete=models.SET_NULL,
                                              null=True, blank=True)
    thumbnail            = models.ImageField(upload_to='listings/thumbnails/', null=True, blank=True)
    condition            = models.CharField(max_length=20, choices=Condition.choices,
                                            default=Condition.NA)

    # Pricing — stored in USD, displayed as TP Coins
    price_usd   = models.DecimalField(max_digits=18, decimal_places=2,
                                      validators=[MinValueValidator(Decimal('0.01'))],
                                      help_text="Price in USD — displayed as TP Coins to buyers")
    currency    = models.CharField(max_length=20, default='TP_COIN')
    quantity    = models.PositiveIntegerField(default=1, help_text="0 = unlimited")
    quantity_sold = models.PositiveIntegerField(default=0)

    # Physical shipping
    requires_shipping   = models.BooleanField(default=False)
    shipping_fee_usd    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    ships_from          = models.CharField(max_length=100, blank=True)
    ships_worldwide     = models.BooleanField(default=True)
    estimated_delivery  = models.CharField(max_length=100, blank=True,
                                           help_text="e.g. '3-7 business days'")

    # Status
    status          = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    expiration      = models.DateTimeField(null=True, blank=True)
    is_featured     = models.BooleanField(default=False)
    admin_verified  = models.BooleanField(default=False)
    admin_note      = models.TextField(blank=True, help_text="Admin rejection/approval note")
    fee_paid        = models.BooleanField(default=False)
    auto_approved   = models.BooleanField(default=False, help_text="Passed auto-approval rules")

    # Reselling
    resell_allowed      = models.BooleanField(default=False)
    max_resell_per_day  = models.PositiveIntegerField(default=1)

    # External links for large files
    external_links      = models.JSONField(default=list, blank=True)

    # Delivery
    delivery_instructions = models.TextField(blank=True)
    auto_delivery       = models.BooleanField(default=True)

    # Stats
    view_count    = models.PositiveIntegerField(default=0)
    avg_rating    = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    review_count  = models.PositiveIntegerField(default=0)

    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'listing_type']),
            models.Index(fields=['vendor', 'status']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        return f"{self.title} by {self.vendor.shop_name}"

    @property
    def price(self):
        """Legacy: returns price_usd for backward compat."""
        return self.price_usd

    @property
    def price_coins(self):
        """Price in TP Coins (1 coin = $10 USD)."""
        from apps.accounts.models import usd_to_coins
        return usd_to_coins(self.price_usd)

    @property
    def is_available(self):
        if self.status != self.Status.ACTIVE:
            return False
        if self.expiration and timezone.now() > self.expiration:
            return False
        if self.quantity > 0 and self.quantity_sold >= self.quantity:
            return False
        return True

    @property
    def stock_remaining(self):
        if self.quantity == 0:
            return '∞'
        return max(0, self.quantity - self.quantity_sold)


class ListingFile(models.Model):
    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    listing           = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name='files')
    file              = models.FileField(upload_to=listing_file_path)
    original_filename = models.CharField(max_length=255)
    file_size         = models.PositiveBigIntegerField()
    mime_type         = models.CharField(max_length=100, blank=True)
    is_public         = models.BooleanField(default=False)
    uploaded_at       = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.original_filename} ({self.listing.title})"

    def delete(self, *args, **kwargs):
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        super().delete(*args, **kwargs)


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = 'percentage', _('Percentage (%)')
        FIXED      = 'fixed',      _('Fixed Amount')

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code            = models.CharField(max_length=50, unique=True)
    discount_type   = models.CharField(max_length=15, choices=DiscountType.choices)
    discount_value  = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_order   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    usage_limit     = models.PositiveIntegerField(default=1)
    times_used      = models.PositiveIntegerField(default=0)
    expiry_date     = models.DateTimeField(null=True, blank=True)
    active          = models.BooleanField(default=True)
    vendor          = models.ForeignKey(VendorProfile, on_delete=models.CASCADE,
                                        null=True, blank=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    @property
    def is_valid(self):
        if not self.active:
            return False
        if self.expiry_date and timezone.now() > self.expiry_date:
            return False
        if self.usage_limit > 0 and self.times_used >= self.usage_limit:
            return False
        return True


class AutoApprovalRule(models.Model):
    """Admin-configurable rules for automatic listing approval/rejection."""

    class RuleType(models.TextChoices):
        KEYWORD_BLACKLIST = 'keyword_blacklist', _('Keyword Blacklist')
        MIN_PRICE         = 'min_price',         _('Minimum Price')
        MAX_PRICE         = 'max_price',         _('Maximum Price')
        CATEGORY_BLOCK    = 'category_block',    _('Category Blocked')
        TYPE_BLOCK        = 'type_block',        _('Type Blocked')

    class Action(models.TextChoices):
        REJECT  = 'reject',  _('Reject listing')
        FLAG    = 'flag',    _('Flag for review')

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule_type   = models.CharField(max_length=30, choices=RuleType.choices)
    value       = models.TextField(help_text="Keyword, price amount, category slug, or type")
    action      = models.CharField(max_length=20, choices=Action.choices, default=Action.REJECT)
    reason      = models.CharField(max_length=200, blank=True,
                                   help_text="Message shown to vendor on rejection")
    is_active   = models.BooleanField(default=True)
    created_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.rule_type}] {self.value} → {self.action}"

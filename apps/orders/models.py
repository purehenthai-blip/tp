"""
ToasterPants — Orders, Escrow & Wallet Models
"""
import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User
from apps.vendors.models import VendorProfile
from apps.listings.models import Listing


class Order(models.Model):

    class Status(models.TextChoices):
        PENDING_PAYMENT  = 'pending_payment',  _('Pending Payment')
        PAYMENT_RECEIVED = 'payment_received', _('Payment Received')
        PROCESSING       = 'processing',       _('Processing')
        ITEM_RELEASED    = 'item_released',    _('Item Released by Vendor')
        SHIPPED          = 'shipped',          _('Shipped')
        DELIVERED        = 'delivered',        _('Delivered')
        VERIFIED         = 'verified',         _('Buyer Verified')
        DISPUTED         = 'disputed',         _('Disputed')
        COMPLETED        = 'completed',        _('Completed')
        REFUNDED         = 'refunded',         _('Refunded')
        CANCELLED        = 'cancelled',        _('Cancelled')

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True, editable=False)

    # Parties
    buyer   = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='orders_placed')
    vendor  = models.ForeignKey(VendorProfile, on_delete=models.SET_NULL, null=True,
                                related_name='orders_received')
    listing = models.ForeignKey(Listing, on_delete=models.SET_NULL, null=True, related_name='orders')

    # Financials — all in TP Coins
    unit_price_coins    = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'))
    quantity            = models.PositiveIntegerField(default=1)
    subtotal_coins      = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'))
    shipping_fee_coins  = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'))
    brokerage_fee_coins = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'),
                                              help_text="2% physical product brokerage fee paid by buyer")
    buyer_tx_fee_coins  = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'),
                                              help_text="2% buyer transaction fee")
    total_coins         = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'),
                                              help_text="Total buyer pays (incl all fees)")
    # Commission — deducted from vendor payout, NOT from buyer
    commission_coins    = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'),
                                              help_text="Platform commission deducted from vendor payout")
    vendor_payout_coins = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'),
                                              help_text="What vendor actually receives")
    coupon_discount     = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0'))
    coupon_used         = models.ForeignKey('listings.Coupon', on_delete=models.SET_NULL,
                                            null=True, blank=True)

    # Legacy compat
    @property
    def total_amount(self):
        return self.total_coins

    @property
    def commission(self):
        return self.commission_coins

    # Shipping address (for physical products)
    shipping_name       = models.CharField(max_length=200, blank=True)
    shipping_address_1  = models.CharField(max_length=300, blank=True)
    shipping_address_2  = models.CharField(max_length=300, blank=True)
    shipping_city       = models.CharField(max_length=100, blank=True)
    shipping_state      = models.CharField(max_length=100, blank=True)
    shipping_zip        = models.CharField(max_length=20, blank=True)
    shipping_country    = models.CharField(max_length=100, blank=True)
    shipping_phone      = models.CharField(max_length=30, blank=True)

    # Status
    status         = models.CharField(max_length=25, choices=Status.choices,
                                       default=Status.PENDING_PAYMENT)
    is_resale      = models.BooleanField(default=False)
    buyer_note     = models.TextField(blank=True)
    admin_note     = models.TextField(blank=True)
    dispute_reason = models.TextField(blank=True)
    ip_address     = models.GenericIPAddressField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['buyer', 'status']),
            models.Index(fields=['vendor', 'status']),
        ]

    def __str__(self):
        return f"Order #{self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            import random, string
            self.order_number = 'TP' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=10))
        super().save(*args, **kwargs)


class Delivery(models.Model):
    class Type(models.TextChoices):
        DIGITAL  = 'digital',  _('Digital')
        PHYSICAL = 'physical', _('Physical Shipping')
        SERVICE  = 'service',  _('Service')

    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order               = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    delivery_type       = models.CharField(max_length=20, choices=Type.choices)
    tracking_number     = models.CharField(max_length=200, blank=True)
    carrier             = models.CharField(max_length=100, blank=True)
    delivery_link       = models.URLField(max_length=2000, blank=True)
    delivery_message    = models.TextField(blank=True)
    vendor_released_at  = models.DateTimeField(null=True, blank=True,
                                               help_text="When vendor clicked release item")
    delivered_at        = models.DateTimeField(null=True, blank=True)
    verified_at         = models.DateTimeField(null=True, blank=True)


class Escrow(models.Model):
    class Status(models.TextChoices):
        LOCKED     = 'locked',     _('Locked')
        RELEASED   = 'released',   _('Released to Vendor')
        REFUNDED   = 'refunded',   _('Refunded to Buyer')
        DISPUTED   = 'disputed',   _('Disputed')
        ADMIN_HOLD = 'admin_hold', _('Admin Hold')

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order           = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='escrow')
    amount_coins    = models.DecimalField(max_digits=18, decimal_places=8,
                                          help_text="Total buyer paid in coins (excl buyer fees)")
    status          = models.CharField(max_length=20, choices=Status.choices,
                                       default=Status.LOCKED)
    locked_at       = models.DateTimeField(auto_now_add=True)
    release_time    = models.DateTimeField()
    released_at     = models.DateTimeField(null=True, blank=True)

    # Payment proof
    tx_hash         = models.CharField(max_length=300, blank=True)
    payment_address = models.CharField(max_length=200, blank=True)
    admin_confirmed = models.BooleanField(default=False)
    confirmed_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='confirmed_escrows')
    dispute_opened_at       = models.DateTimeField(null=True, blank=True)
    dispute_resolved_by     = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                                related_name='resolved_disputes')
    dispute_resolution_note = models.TextField(blank=True)

    # Legacy
    @property
    def amount(self):
        return self.amount_coins

    def __str__(self):
        return f"Escrow #{self.order.order_number}: {self.amount_coins} coins [{self.status}]"

    def release_to_vendor(self, admin_user=None):
        """Release escrow — vendor gets payout minus commission. Commission goes to platform wallet."""
        if self.status != self.Status.LOCKED:
            raise ValueError("Can only release locked escrow.")
        from django.db import transaction as db_tx
        from apps.accounts.models import PlatformWallet

        order = self.order
        commission   = order.commission_coins
        vendor_payout = order.vendor_payout_coins

        with db_tx.atomic():
            # Credit vendor
            vendor_user = order.vendor.user
            vendor_user.coin_balance += vendor_payout
            vendor_user.save(update_fields=['coin_balance'])

            # Credit platform wallet with commission
            pw = PlatformWallet.get_or_create_main()
            pw.credit(commission)

            # Update escrow
            self.status      = self.Status.RELEASED
            self.released_at = timezone.now()
            self.save(update_fields=['status', 'released_at'])

            # Update order
            order.status = Order.Status.COMPLETED
            order.save(update_fields=['status'])

            # Log transactions
            WalletTransaction.objects.create(
                user=vendor_user,
                transaction_type='vendor_payout',
                amount=vendor_payout,
                balance_after=vendor_user.coin_balance,
                description=f"Payout for order #{order.order_number} (after 8% commission)",
                reference_id=str(order.id),
            )

    def refund_to_buyer(self, admin_user=None):
        if self.status not in [self.Status.LOCKED, self.Status.DISPUTED]:
            raise ValueError("Can only refund locked or disputed escrow.")
        buyer = self.order.buyer
        buyer.coin_balance += self.amount_coins
        buyer.save(update_fields=['coin_balance'])
        self.status      = self.Status.REFUNDED
        self.released_at = timezone.now()
        self.save(update_fields=['status', 'released_at'])
        self.order.status = Order.Status.REFUNDED
        self.order.save(update_fields=['status'])


class WalletTransaction(models.Model):
    class Type(models.TextChoices):
        DEPOSIT         = 'deposit',         _('Coin Deposit')
        WITHDRAWAL      = 'withdrawal',      _('Withdrawal')
        PAYMENT         = 'payment',         _('Purchase Payment')
        ESCROW_LOCK     = 'escrow_lock',     _('Escrow Lock')
        ESCROW_RELEASE  = 'escrow_release',  _('Escrow Release')
        ESCROW_REFUND   = 'escrow_refund',   _('Escrow Refund')
        COMMISSION      = 'commission',      _('Platform Commission')
        VENDOR_PAYOUT   = 'vendor_payout',   _('Vendor Payout')
        ADMIN_CREDIT    = 'admin_credit',    _('Admin Credit')
        ADMIN_DEBIT     = 'admin_debit',     _('Admin Debit')
        LISTING_FEE     = 'listing_fee',     _('Listing Fee')
        APPLICATION_FEE = 'application_fee', _('Application Fee')
        REFUND          = 'refund',          _('Refund')
        RESALE          = 'resale',          _('Resale Income')
        BUYER_FEE       = 'buyer_fee',       _('Buyer Transaction Fee')
        BROKERAGE_FEE   = 'brokerage_fee',   _('Physical Brokerage Fee')

    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user             = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=25, choices=Type.choices)
    amount           = models.DecimalField(max_digits=18, decimal_places=8)
    balance_after    = models.DecimalField(max_digits=18, decimal_places=8)
    reference_id     = models.CharField(max_length=100, blank=True)
    description      = models.TextField(blank=True)
    tx_hash          = models.CharField(max_length=300, blank=True)
    admin_note       = models.TextField(blank=True)
    created_by       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='created_transactions')
    timestamp        = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['transaction_type']),
        ]


class ResaleRecord(models.Model):
    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reseller       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resale_records')
    original_order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='resale_origin')
    resale_order   = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='resale_transaction')
    listing        = models.ForeignKey(Listing, on_delete=models.CASCADE)
    resale_price   = models.DecimalField(max_digits=18, decimal_places=8)
    resale_date    = models.DateField(auto_now_add=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['reseller', 'resale_date'])]

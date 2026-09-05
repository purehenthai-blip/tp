"""
ToasterPants — Accounts Models
================================
Users, config, audit logs, coins, ranks.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ─── TP COIN SYSTEM ───────────────────────────────────────────────────────────
TP_COIN_VALUE_USD = Decimal('10.00')   # 1 TP Coin = $10 USD

def usd_to_coins(usd_amount: Decimal) -> Decimal:
    """Convert USD amount to TP Coins. Returns coins with 4 decimal places."""
    if usd_amount is None:
        return Decimal('0.0000')
    return (Decimal(str(usd_amount)) / TP_COIN_VALUE_USD).quantize(Decimal('0.0001'))

def coins_to_usd(coins: Decimal) -> Decimal:
    """Convert TP Coins to USD."""
    if coins is None:
        return Decimal('0.00')
    return (Decimal(str(coins)) * TP_COIN_VALUE_USD).quantize(Decimal('0.00'))


# ─── VENDOR MILITARY RANKS ────────────────────────────────────────────────────
VENDOR_RANKS = [
    ('general',     'General',     50000),
    ('colonel',     'Colonel',     10000),
    ('major',       'Major',        5000),
    ('captain',     'Captain',      1000),
    ('lieutenant',  'Lieutenant',    500),
    ('sergeant',    'Sergeant',      100),
    ('corporal',    'Corporal',       20),
    ('private',     'Private',         0),
]

def get_vendor_rank(total_sales_coins: Decimal) -> tuple:
    """Return (rank_key, rank_label) for a vendor based on total sales in coins."""
    sales = float(total_sales_coins or 0)
    for key, label, threshold in VENDOR_RANKS:
        if sales >= threshold:
            return (key, label)
    return ('private', 'Private')


# ─── BUYER METALLIC RANKS ─────────────────────────────────────────────────────
BUYER_RANKS = [
    ('titanium',  'Titanium',  5000),
    ('diamond',   'Diamond',   1000),
    ('platinum',  'Platinum',   500),
    ('gold',      'Gold',       200),
    ('silver',    'Silver',      50),
    ('bronze',    'Bronze',      10),
    ('iron',      'Iron',         0),
]

def get_buyer_rank(purchase_count: int) -> tuple:
    """Return (rank_key, rank_label) for a buyer based on number of completed purchases."""
    count = int(purchase_count or 0)
    for key, label, threshold in BUYER_RANKS:
        if count >= threshold:
            return (key, label)
    return ('iron', 'Iron')


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('Username is required.')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('role', 'super_admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(username, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    class Role(models.TextChoices):
        SUPER_ADMIN   = 'super_admin',   _('Super Admin')
        ADMIN         = 'admin',         _('Admin')
        SUPPORT       = 'support',       _('Support')
        VENDOR        = 'vendor',        _('Vendor')
        VENDOR_STAFF  = 'vendor_staff',  _('Vendor Staff')
        BUYER         = 'buyer',         _('Buyer')
        RESELLER      = 'reseller',      _('Reseller')

    class Theme(models.TextChoices):
        DARK   = 'dark',   _('Dark')
        LIGHT  = 'light',  _('Light')
        CUSTOM = 'custom', _('Custom')

    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username      = models.CharField(max_length=50, unique=True)
    display_name  = models.CharField(max_length=100, blank=True)
    email         = models.EmailField(unique=True, null=True, blank=True)
    role          = models.CharField(max_length=20, choices=Role.choices, default=Role.BUYER)
    is_active     = models.BooleanField(default=True)
    is_staff      = models.BooleanField(default=False)
    is_banned     = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)
    verified_vendor   = models.BooleanField(default=False)

    # ── TP Coin Wallet ────────────────────────────────────────────────────────
    # All balances stored in TP Coins (1 coin = $10 USD)
    coin_balance    = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    escrow_balance  = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    purchase_count  = models.PositiveIntegerField(default=0, help_text="Number of completed purchases")
    purchase_total  = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))

    # Legacy field — kept for backward compat, maps to coin_balance
    @property
    def wallet_balance(self):
        return self.coin_balance

    @wallet_balance.setter
    def wallet_balance(self, value):
        self.coin_balance = value

    # ── Deposit addresses (platform assigns — where buyers send TO) ───────────
    btc_address         = models.CharField(max_length=100, blank=True)
    usdt_trc20_address  = models.CharField(max_length=100, blank=True)
    ltc_address         = models.CharField(max_length=100, blank=True)
    ada_address         = models.CharField(max_length=100, blank=True)
    eth_address         = models.CharField(max_length=100, blank=True)
    xmr_address         = models.CharField(max_length=100, blank=True)

    # ── Withdrawal address (personal wallet — where earnings go OUT) ──────────
    withdrawal_address  = models.CharField(max_length=200, blank=True)
    withdrawal_currency = models.CharField(max_length=20, blank=True, default='USDT_TRC20')

    # ── Preferences ───────────────────────────────────────────────────────────
    language = models.CharField(max_length=10, default='en')
    theme    = models.CharField(max_length=10, choices=Theme.choices, default=Theme.DARK)
    pgp_key  = models.TextField(blank=True)

    # ── Account lifecycle ─────────────────────────────────────────────────────
    account_delete_time = models.DateTimeField(null=True, blank=True)
    last_active         = models.DateTimeField(default=timezone.now)
    created_at          = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD  = 'username'
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['last_active']),
        ]

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def display(self):
        return self.display_name or f"user_{str(self.id)[:8]}"

    @property
    def is_reseller_eligible(self):
        return self.purchase_total >= Decimal('100.00')

    @property
    def coin_balance_display(self):
        """Coins with 4 decimal places."""
        return self.coin_balance

    @property
    def vendor_rank(self):
        try:
            sales_coins = self.vendor_profile.total_sales
            return get_vendor_rank(sales_coins)
        except Exception:
            return ('private', 'Private')

    @property
    def buyer_rank(self):
        return get_buyer_rank(self.purchase_count)


class SiteConfig(models.Model):
    """Key-value store for all platform configuration."""
    param_name  = models.CharField(max_length=100, unique=True)
    value       = models.TextField()
    description = models.TextField(blank=True)
    updated_at  = models.DateTimeField(auto_now=True)
    updated_by  = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='config_changes')

    class Meta:
        verbose_name = 'Site Configuration'
        verbose_name_plural = 'Site Configurations'

    def __str__(self):
        return f"{self.param_name} = {self.value[:50]}"

    @classmethod
    def get(cls, key: str, default: str = '') -> str:
        try:
            return cls.objects.get(param_name=key).value
        except cls.DoesNotExist:
            return default

    @classmethod
    def set(cls, key: str, value: str, user=None):
        obj, _ = cls.objects.update_or_create(
            param_name=key,
            defaults={'value': value, 'updated_by': user}
        )
        return obj


class PlatformWallet(models.Model):
    """Tracks accumulated platform commission. Admin can withdraw from here."""
    id              = models.BigAutoField(primary_key=True)
    coin_balance    = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00'))
    total_collected = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00'))
    total_withdrawn = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00'))
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Platform Wallet'

    @classmethod
    def get_or_create_main(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def credit(self, amount: Decimal):
        from django.db import transaction as db_transaction
        with db_transaction.atomic():
            wallet = PlatformWallet.objects.select_for_update().get(pk=self.pk)
            wallet.coin_balance    += amount
            wallet.total_collected += amount
            wallet.save(update_fields=['coin_balance', 'total_collected', 'updated_at'])


class WithdrawalRequest(models.Model):
    """Pending withdrawal requests — admin must approve or reject."""

    class Status(models.TextChoices):
        PENDING  = 'pending',  _('Pending')
        APPROVED = 'approved', _('Approved')
        REJECTED = 'rejected', _('Rejected')

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount_coins    = models.DecimalField(max_digits=18, decimal_places=8)
    amount_usd      = models.DecimalField(max_digits=18, decimal_places=2)
    currency        = models.CharField(max_length=20, default='USDT_TRC20')
    address         = models.CharField(max_length=200)
    status          = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_note      = models.TextField(blank=True)
    processed_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='processed_withdrawals')
    created_at      = models.DateTimeField(auto_now_add=True)
    processed_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Withdrawal {self.amount_coins} coins by {self.user.username} [{self.status}]"


class DepositRequest(models.Model):
    """Buyer submits TxHash + screenshot. Admin verifies and credits coins."""

    class Status(models.TextChoices):
        PENDING  = 'pending',  _('Pending Verification')
        APPROVED = 'approved', _('Approved — Coins Credited')
        REJECTED = 'rejected', _('Rejected')

    id              = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user            = models.ForeignKey(User, on_delete=models.CASCADE, related_name='deposit_requests')
    coins_requested = models.DecimalField(max_digits=18, decimal_places=8,
                                          help_text="Number of TP Coins requested")
    usd_amount      = models.DecimalField(max_digits=18, decimal_places=2,
                                          help_text="USD equivalent")
    currency        = models.CharField(max_length=20, default='USDT_TRC20')
    deposit_address = models.CharField(
        max_length=200,
        blank=True,
        help_text="Platform-assigned destination address used for this deposit",
    )
    tx_hash         = models.CharField(max_length=300, help_text="Blockchain transaction hash / ID")
    screenshot      = models.ImageField(upload_to='deposits/screenshots/', null=True, blank=True)
    from_address    = models.CharField(max_length=200, blank=True)
    status          = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    admin_note      = models.TextField(blank=True)
    processed_by    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='processed_deposits')
    created_at      = models.DateTimeField(auto_now_add=True)
    processed_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Deposit {self.coins_requested} coins by {self.user.username} [{self.status}]"


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE          = 'create',          _('Create')
        UPDATE          = 'update',          _('Update')
        DELETE          = 'delete',          _('Delete')
        BAN             = 'ban',             _('Ban User')
        UNBAN           = 'unban',           _('Unban User')
        ESCROW_OVERRIDE = 'escrow_override', _('Escrow Override')
        CONFIG_CHANGE   = 'config_change',   _('Config Change')
        BALANCE_ADJUST  = 'balance_adjust',  _('Balance Adjustment')
        LISTING_REMOVE  = 'listing_remove',  _('Listing Removed')
        OTHER           = 'other',           _('Other')

    admin_user    = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action        = models.CharField(max_length=30, choices=Action.choices)
    target_model  = models.CharField(max_length=100)
    target_id     = models.CharField(max_length=100)
    description   = models.TextField()
    ip_address    = models.GenericIPAddressField(null=True, blank=True)
    timestamp     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.action}] {self.description[:80]}"


class DeletionQueue(models.Model):
    class Reason(models.TextChoices):
        USER_REQUESTED       = 'user_requested',       _('User Requested')
        INACTIVE_LOW_BALANCE = 'inactive_low_balance', _('Inactive + Low Balance')
        ADMIN_ACTION         = 'admin_action',         _('Admin Action')
        BANNED               = 'banned',               _('Account Banned')

    user           = models.OneToOneField(User, on_delete=models.CASCADE, related_name='deletion_queue')
    scheduled_time = models.DateTimeField()
    reason         = models.CharField(max_length=30, choices=Reason.choices)
    admin_note     = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Delete {self.user.username} at {self.scheduled_time}"


class ContentTranslation(models.Model):
    table_name      = models.CharField(max_length=100)
    field_name      = models.CharField(max_length=100)
    record_id       = models.CharField(max_length=50)
    language_code   = models.CharField(max_length=10)
    translated_text = models.TextField()
    auto_translated = models.BooleanField(default=False)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('table_name', 'field_name', 'record_id', 'language_code')

    def __str__(self):
        return f"{self.table_name}.{self.field_name}[{self.record_id}] -> {self.language_code}"


class CryptoWallet(models.Model):
    class Currency(models.TextChoices):
        BTC        = 'BTC',        'Bitcoin'
        USDT_TRC20 = 'USDT_TRC20', 'USDT (TRC20)'
        LTC        = 'LTC',        'Litecoin'
        ADA        = 'ADA',        'Cardano'
        ETH        = 'ETH',        'Ethereum'
        XMR        = 'XMR',        'Monero'

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='crypto_wallets')
    currency   = models.CharField(max_length=20, choices=Currency.choices)
    address    = models.CharField(max_length=200)
    label      = models.CharField(max_length=100, blank=True, default='Deposit Address')
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'currency')

    def __str__(self):
        return f"{self.user.username} {self.currency}: {self.address[:20]}..."

"""
ToasterPants Services — wallet ops, auto-approval, notifications.
"""
import logging
import requests
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('toasterpants')


# ─── TRANSLATION ──────────────────────────────────────────────────────────────

def translate_content(text: str, target_language: str, source_language: str = 'en') -> str:
    from apps.accounts.models import SiteConfig
    api_url = SiteConfig.get('TRANSLATION_API_URL', '')
    api_key = SiteConfig.get('TRANSLATION_API_KEY', '')
    if not api_url or source_language == target_language:
        return text
    try:
        payload = {'q': text, 'source': source_language, 'target': target_language, 'format': 'text'}
        if api_key:
            payload['api_key'] = api_key
        resp = requests.post(f"{api_url.rstrip('/')}/translate", json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get('translatedText', text)
    except Exception as e:
        logger.error(f"Translation error: {e}")
        return text


# ─── WALLET SERVICES ──────────────────────────────────────────────────────────

def credit_wallet(user, amount: Decimal, tx_type: str,
                  description: str = '', tx_hash: str = '',
                  admin_user=None, reference_id: str = '',
                  admin_note: str = ''):
    """Credit a user's coin wallet and log the transaction."""
    from apps.accounts.models import User
    from apps.orders.models import WalletTransaction

    with transaction.atomic():
        u = User.objects.select_for_update().get(pk=user.pk)
        u.coin_balance += amount
        u.save(update_fields=['coin_balance'])
        WalletTransaction.objects.create(
            user=u, transaction_type=tx_type, amount=amount,
            balance_after=u.coin_balance, description=description,
            tx_hash=tx_hash, admin_note=admin_note,
            created_by=admin_user, reference_id=reference_id,
        )
    return u


def debit_wallet(user, amount: Decimal, tx_type: str,
                 description: str = '', reference_id: str = ''):
    """Debit a user's coin wallet. Raises ValueError if insufficient."""
    from apps.accounts.models import User
    from apps.orders.models import WalletTransaction

    with transaction.atomic():
        u = User.objects.select_for_update().get(pk=user.pk)
        if u.coin_balance < amount:
            raise ValueError(f"Insufficient coins. Have: {u.coin_balance}, need: {amount}")
        u.coin_balance -= amount
        u.save(update_fields=['coin_balance'])
        WalletTransaction.objects.create(
            user=u, transaction_type=tx_type, amount=amount,
            balance_after=u.coin_balance, description=description,
            reference_id=reference_id,
        )
    return u


def lock_escrow_for_order(order, tx_hash: str = ''):
    """
    Lock buyer coins in escrow.
    Commission is NOT charged to buyer — it's deducted from vendor payout later.
    Buyer pays: subtotal + buyer_tx_fee (2%) + shipping + brokerage (2% if physical)
    """
    from apps.orders.models import Escrow, WalletTransaction
    from apps.accounts.models import SiteConfig

    auto_release_days = int(SiteConfig.get('ESCROW_AUTO_RELEASE_DAYS', '14'))

    with transaction.atomic():
        # Debit buyer — they pay total_coins (which includes their fees)
        debit_wallet(
            user=order.buyer,
            amount=order.total_coins,
            tx_type='escrow_lock',
            description=f"Payment for order #{order.order_number}",
            reference_id=str(order.id),
        )

        # Lock in escrow — the subtotal (what vendor will get before commission)
        escrow = Escrow.objects.create(
            order=order,
            amount_coins=order.subtotal_coins,
            status=Escrow.Status.LOCKED,
            release_time=timezone.now() + timezone.timedelta(days=auto_release_days),
            tx_hash=tx_hash,
        )

        order.status = 'payment_received'
        order.save(update_fields=['status'])

    return escrow


def process_listing_auto_approval(listing):
    """
    Run auto-approval rules on a listing.
    Returns (action, reason) where action is 'approve', 'reject', or 'review'.
    """
    from apps.listings.models import AutoApprovalRule
    from apps.accounts.models import SiteConfig

    min_price = Decimal(SiteConfig.get('MIN_LISTING_PRICE_USD', '0.01'))
    text_to_check = f"{listing.title} {listing.description}".lower()

    rules = AutoApprovalRule.objects.filter(is_active=True)

    for rule in rules:
        val = rule.value.lower().strip()

        if rule.rule_type == AutoApprovalRule.RuleType.KEYWORD_BLACKLIST:
            keywords = [k.strip() for k in val.split(',') if k.strip()]
            for kw in keywords:
                if kw in text_to_check:
                    return (rule.action, rule.reason or f"Contains prohibited keyword: '{kw}'")

        elif rule.rule_type == AutoApprovalRule.RuleType.MIN_PRICE:
            try:
                rule_min = Decimal(val)
                if listing.price_usd < rule_min:
                    return (rule.action, rule.reason or f"Price below minimum ${rule_min}")
            except Exception:
                pass

        elif rule.rule_type == AutoApprovalRule.RuleType.MAX_PRICE:
            try:
                rule_max = Decimal(val)
                if listing.price_usd > rule_max:
                    return (rule.action, rule.reason or f"Price above maximum ${rule_max}")
            except Exception:
                pass

        elif rule.rule_type == AutoApprovalRule.RuleType.CATEGORY_BLOCK:
            if listing.category and listing.category.slug == val:
                return (rule.action, rule.reason or f"Category '{val}' is restricted")

        elif rule.rule_type == AutoApprovalRule.RuleType.TYPE_BLOCK:
            if listing.listing_type == val:
                return (rule.action, rule.reason or f"Listing type '{val}' is not allowed")

    # Check category limits
    if listing.category:
        cat = listing.category
        current_count = cat.vendor_listing_count(listing.vendor)
        if current_count >= cat.max_listings_per_vendor:
            return ('reject', f"You have reached the maximum of {cat.max_listings_per_vendor} listings in '{cat.name}'")

    # Passed all rules
    return ('approve', '')


# ─── NOTIFICATIONS ────────────────────────────────────────────────────────────

def send_system_message(user, subject: str, content: str):
    from apps.messaging.models import MessageThread, Message
    from apps.accounts.models import User as UserModel
    try:
        system_user = UserModel.objects.filter(role='super_admin').first()
        if not system_user:
            return None
        thread = MessageThread.objects.create(subject=subject, is_admin_thread=True)
        thread.participants.add(user, system_user)
        return Message.objects.create(thread=thread, sender=system_user, content=content)
    except Exception as e:
        logger.error(f"send_system_message error: {e}")
        return None

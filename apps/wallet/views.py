"""
ToasterPants — Wallet Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db import transaction as db_transaction
from django.utils import timezone
from decimal import Decimal
from apps.orders.models import WalletTransaction
from apps.accounts.models import SiteConfig, WithdrawalRequest, DepositRequest, usd_to_coins

SUPPORTED_CRYPTOS = [
    {'code': 'USDT_TRC20', 'name': 'USDT (TRC20)',  'addr_field': 'usdt_trc20_address'},
    {'code': 'BTC',         'name': 'Bitcoin (BTC)',  'addr_field': 'btc_address'},
    {'code': 'LTC',         'name': 'Litecoin (LTC)', 'addr_field': 'ltc_address'},
    {'code': 'ADA',         'name': 'Cardano (ADA)',  'addr_field': 'ada_address'},
    {'code': 'ETH',         'name': 'Ethereum (ETH)', 'addr_field': 'eth_address'},
    {'code': 'XMR',         'name': 'Monero (XMR)',   'addr_field': 'xmr_address'},
]
COIN_VALUE_USD = Decimal('10.00')


@login_required
def wallet_home(request):
    min_deposit_coins    = Decimal(SiteConfig.get('MIN_DEPOSIT_COINS', '1'))
    min_withdrawal_coins = Decimal(SiteConfig.get('MIN_WITHDRAWAL_COINS', '1'))

    supported_cryptos = [
        {'code': c['code'], 'name': c['name'],
         'address': getattr(request.user, c['addr_field'], '')}
        for c in SUPPORTED_CRYPTOS
    ]

    transactions = WalletTransaction.objects.filter(
        user=request.user).order_by('-timestamp')
    paginator = Paginator(transactions, 25)
    page = paginator.get_page(request.GET.get('page'))

    pending_deposits    = DepositRequest.objects.filter(user=request.user, status='pending').count()
    pending_withdrawals = WithdrawalRequest.objects.filter(user=request.user, status='pending').count()

    vendor_stats = None
    if request.user.role in ['vendor', 'vendor_staff']:
        try:
            earned = WalletTransaction.objects.filter(
                user=request.user, transaction_type='vendor_payout'
            ).values_list('amount', flat=True)
            vendor_stats = {
                'total_earned':   sum(earned),
                'pending_escrow': request.user.escrow_balance,
            }
        except Exception:
            vendor_stats = {'total_earned': 0, 'pending_escrow': 0}

    return render(request, 'wallet/wallet.html', {
        'supported_cryptos':    supported_cryptos,
        'transactions':          page,
        'vendor_stats':          vendor_stats,
        'withdrawal_address':    request.user.withdrawal_address,
        'withdrawal_currency':   request.user.withdrawal_currency,
        'min_deposit_coins':     min_deposit_coins,
        'min_withdrawal_coins':  min_withdrawal_coins,
        'coin_value_usd':        COIN_VALUE_USD,
        'pending_deposits':      pending_deposits,
        'pending_withdrawals':   pending_withdrawals,
        'page_title':            'My Wallet',
    })


@login_required
@require_POST
def submit_deposit(request):
    """Submit a crypto deposit for Super Admin verification.

    The destination address is NEVER supplied by the user. It is taken
    exclusively from the platform-assigned address on the user's account.
    """
    coins_str = request.POST.get('coins', '').strip()
    currency = request.POST.get('currency', '').strip()
    tx_hash = request.POST.get('tx_hash', '').strip()
    screenshot = request.FILES.get('screenshot')

    crypto = next(
        (c for c in SUPPORTED_CRYPTOS if c['code'] == currency),
        None,
    )

    if not crypto:
        messages.error(request, "Please select a supported deposit currency.")
        return redirect('wallet:home')

    # The destination address comes exclusively from the address assigned
    # by Super Admin. The browser can never override it.
    deposit_address = getattr(request.user, crypto['addr_field'], '').strip()

    if not deposit_address:
        messages.error(
            request,
            f"No {crypto['name']} deposit address has been assigned to your account yet. "
            "Please contact support."
        )
        return redirect('wallet:home')

    if not tx_hash:
        messages.error(request, "Transaction hash is required.")
        return redirect('wallet:home')

    if len(tx_hash) > 300:
        messages.error(request, "Transaction hash is too long.")
        return redirect('wallet:home')

    try:
        coins = Decimal(coins_str)
    except Exception:
        messages.error(request, "Please enter a valid deposit amount.")
        return redirect('wallet:home')

    min_deposit = Decimal(SiteConfig.get('MIN_DEPOSIT_COINS', '1'))

    if coins <= 0:
        messages.error(request, "Deposit amount must be greater than zero.")
        return redirect('wallet:home')

    if coins < min_deposit:
        messages.error(
            request,
            f"Minimum deposit is {min_deposit} TP Coins."
        )
        return redirect('wallet:home')

    # A transaction hash can only be submitted once.
    if DepositRequest.objects.filter(tx_hash=tx_hash).exists():
        messages.error(
            request,
            "This transaction hash has already been submitted."
        )
        return redirect('wallet:home')

    DepositRequest.objects.create(
        user=request.user,
        coins_requested=coins,
        usd_amount=coins * COIN_VALUE_USD,
        currency=currency,
        deposit_address=deposit_address,
        tx_hash=tx_hash,
        screenshot=screenshot,
        status=DepositRequest.Status.PENDING,
    )

    messages.success(
        request,
        f"Deposit request for {coins} TP Coins submitted. "
        "Super Admin will verify the transaction before crediting your balance."
    )
    return redirect('wallet:home')


@login_required
@require_POST
def request_withdrawal(request):
    """Request a withdrawal — goes to pending, admin approves/rejects."""
    coins_str = request.POST.get('amount', '').strip()
    address   = request.POST.get('withdrawal_address', '').strip()
    currency  = request.POST.get('currency', 'USDT_TRC20').strip()
    save_addr = request.POST.get('save_address')

    min_withdrawal = Decimal(SiteConfig.get('MIN_WITHDRAWAL_COINS', '1'))

    if not address:
        messages.error(request, "Please enter a withdrawal address.")
        return redirect('wallet:home')

    try:
        coins = Decimal(coins_str)
        if coins < min_withdrawal:
            messages.error(request, f"Minimum withdrawal is {min_withdrawal} TP Coins.")
            return redirect('wallet:home')
    except Exception:
        messages.error(request, "Please enter a valid amount.")
        return redirect('wallet:home')

    if request.user.coin_balance < coins:
        messages.error(request,
            f"Insufficient balance. You have {request.user.coin_balance:.4f} coins, "
            f"requested {coins} coins.")
        return redirect('wallet:home')

    if save_addr:
        request.user.withdrawal_address  = address
        request.user.withdrawal_currency = currency
        request.user.save(update_fields=['withdrawal_address', 'withdrawal_currency'])

    with db_transaction.atomic():
        # Reserve coins — deduct from balance immediately (held pending admin approval)
        request.user.coin_balance -= coins
        request.user.save(update_fields=['coin_balance'])

        WithdrawalRequest.objects.create(
            user=request.user,
            amount_coins=coins,
            amount_usd=coins * COIN_VALUE_USD,
            currency=currency,
            address=address,
            status=WithdrawalRequest.Status.PENDING,
        )

        WalletTransaction.objects.create(
            user=request.user,
            transaction_type='withdrawal',
            amount=coins,
            balance_after=request.user.coin_balance,
            description=f"Withdrawal request: {coins} coins to {address[:20]}...",
        )

    messages.success(request,
        f"Withdrawal of {coins} TP Coins submitted. Admin will process within 24 hours.")
    return redirect('wallet:home')


@login_required
def transaction_history(request):
    return redirect('wallet:home')

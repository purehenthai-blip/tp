from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Sum
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from decimal import Decimal
import logging
from .models import User, SiteConfig, AuditLog, DeletionQueue
from .decorators import admin_required, superadmin_required
from .forms import RegisterForm, LoginForm, ProfileUpdateForm, AdminUserEditForm

logger = logging.getLogger('toasterpants')


def homepage(request):
    from apps.listings.models import Listing, ListingCategory
    try:
        featured = Listing.objects.filter(status='active', is_featured=True).select_related('vendor').order_by('-created_at')[:8]
        recent = Listing.objects.filter(status='active').select_related('vendor').order_by('-created_at')[:12]
        categories = ListingCategory.objects.filter(is_active=True, parent=None).prefetch_related('children')[:8]
    except Exception:
        featured, recent, categories = [], [], []
    return render(request, 'home.html', {
        'featured_listings': featured, 'recent_listings': recent,
        'categories': categories, 'page_title': 'ToasterPants — Anonymous Crypto Marketplace',
    })


def terms_of_service(request):
    return render(request, 'legal/terms.html', {'page_title': 'Terms of Service'})


def privacy_policy(request):
    return render(request, 'legal/privacy.html', {'page_title': 'Privacy Policy'})


@csrf_protect
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                try:
                    from apps.filemanager.models import UserStorageQuota
                    UserStorageQuota.objects.get_or_create(user=user)
                except Exception:
                    pass
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                messages.success(request, f"Welcome to ToasterPants, {user.display}!")
                return redirect('dashboard')
            except Exception as e:
                logger.error(f"Registration error: {e}")
                messages.error(request, f"Registration failed: {e}")
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form, 'page_title': 'Register'})


@csrf_protect
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_banned:
                messages.error(request, "Account suspended. Contact support.")
                return render(request, 'accounts/login.html', {'form': form})
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            user.last_active = timezone.now()
            user.save(update_fields=['last_active'])
            nxt = request.GET.get('next', '')
            return redirect(nxt if nxt.startswith('/') else 'dashboard')
        messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm(request)
    return render(request, 'accounts/login.html', {'form': form, 'page_title': 'Login'})


@login_required
def logout_view(request):
    logout(request)
    return redirect('/')


@login_required
def dashboard(request):
    user = request.user
    if user.role in [User.Role.SUPER_ADMIN, User.Role.ADMIN]:
        return redirect('admin_panel:dashboard')
    elif user.role in [User.Role.VENDOR, User.Role.VENDOR_STAFF]:
        return redirect('vendors:dashboard')
    elif user.role == User.Role.SUPPORT:
        return redirect('support:dashboard')
    return buyer_dashboard(request)


@login_required
def buyer_dashboard(request):
    from apps.orders.models import Order
    try:
        recent_orders = Order.objects.filter(buyer=request.user).select_related('listing', 'vendor').order_by('-created_at')[:5]
    except Exception:
        recent_orders = []
    try:
        from apps.messaging.models import MessageThread
        unread = MessageThread.objects.filter(participants=request.user, messages__is_read=False).exclude(messages__sender=request.user).distinct().count()
    except Exception:
        unread = 0
    return render(request, 'accounts/buyer_dashboard.html', {
        'recent_orders': recent_orders, 'wallet_balance': request.user.wallet_balance,
        'purchase_total': request.user.purchase_total,
        'is_reseller_eligible': request.user.is_reseller_eligible,
        'unread_messages': unread, 'page_title': 'My Dashboard',
    })


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated!")
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    deletion_scheduled = None
    try:
        deletion_scheduled = request.user.deletion_queue.scheduled_time
    except Exception:
        pass
    crypto_fields = [
        ('btc_address', 'Bitcoin (BTC)'), ('usdt_trc20_address', 'USDT TRC20'),
        ('ltc_address', 'Litecoin (LTC)'), ('ada_address', 'Cardano (ADA)'),
        ('eth_address', 'Ethereum (ETH)'), ('xmr_address', 'Monero (XMR)'),
    ]
    return render(request, 'accounts/profile.html', {
        'form': form, 'deletion_scheduled': deletion_scheduled,
        'crypto_fields': crypto_fields, 'page_title': 'Profile Settings',
    })


@login_required
@require_POST
def save_crypto_addresses(request):
    fields = ['btc_address', 'usdt_trc20_address', 'ltc_address', 'ada_address', 'eth_address', 'xmr_address']
    for f in fields:
        setattr(request.user, f, request.POST.get(f, '').strip())
    request.user.save(update_fields=fields)
    messages.success(request, "Addresses saved!")
    return redirect('accounts:profile')


@login_required
def set_theme(request):
    if request.method == 'POST':
        theme = request.POST.get('theme', 'dark')
        if theme in ['dark', 'light', 'custom']:
            request.user.theme = theme
            request.user.save(update_fields=['theme'])
            request.session['theme'] = theme
            return JsonResponse({'status': 'ok', 'theme': theme})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def set_language(request):
    if request.method == 'POST':
        lang = request.POST.get('language', 'en')
        request.user.language = lang
        request.user.save(update_fields=['language'])
        request.session['_language'] = lang
        return JsonResponse({'status': 'ok'})
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def schedule_account_deletion(request):
    if request.method == 'POST':
        days = int(request.POST.get('days', 7))
        DeletionQueue.objects.update_or_create(
            user=request.user,
            defaults={'scheduled_time': timezone.now() + timezone.timedelta(days=days),
                      'reason': DeletionQueue.Reason.USER_REQUESTED}
        )
        messages.success(request, f"Account scheduled for deletion in {days} days.")
    return redirect('accounts:profile')


@login_required
def cancel_account_deletion(request):
    DeletionQueue.objects.filter(user=request.user).delete()
    messages.success(request, "Account deletion cancelled!")
    return redirect('accounts:profile')


@admin_required
def admin_dashboard(request):
    from apps.orders.models import Order, Escrow
    from apps.listings.models import Listing
    from apps.messaging.models import Ticket
    try:
        stats = {
            'total_users': User.objects.count(),
            'total_vendors': User.objects.filter(role='vendor').count(),
            'total_buyers': User.objects.filter(role='buyer').count(),
            'active_listings': Listing.objects.filter(status='active').count(),
            'pending_orders': Order.objects.filter(status='pending_payment').count(),
            'locked_escrow': Escrow.objects.filter(status='locked').aggregate(total_coins=Sum('amount_coins'))['total_coins'] or 0,
            'open_tickets': Ticket.objects.filter(status='open').count(),
            'total_revenue': Order.objects.filter(status='completed').aggregate(total_coins=Sum('commission_coins'))['total_coins'] or 0,
        }
        recent_activity = AuditLog.objects.select_related('admin_user').order_by('-timestamp')[:10]
        recent_orders = Order.objects.select_related('buyer', 'vendor', 'listing').order_by('-created_at')[:10]
        pending_vendors = User.objects.filter(role='vendor', vendor_profile__verified_status='pending').select_related('vendor_profile')[:10]
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        stats = {k: 0 for k in ['total_users','total_vendors','total_buyers','active_listings','pending_orders','locked_escrow','open_tickets','total_revenue']}
        recent_activity, recent_orders, pending_vendors = [], [], []
    return render(request, 'admin_panel/dashboard.html', {
        'stats': stats, 'recent_activity': recent_activity,
        'recent_orders': recent_orders, 'pending_vendors': pending_vendors,
        'page_title': 'Admin Control Panel',
    })


@admin_required
def admin_user_list(request):
    qs = User.objects.all().order_by('-created_at')
    if request.GET.get('role'):
        qs = qs.filter(role=request.GET['role'])
    if request.GET.get('q'):
        qs = qs.filter(Q(username__icontains=request.GET['q']) | Q(email__icontains=request.GET['q']))
    return render(request, 'admin_panel/users.html', {
        'users': Paginator(qs, 25).get_page(request.GET.get('page')),
        'roles': User.Role.choices, 'page_title': 'User Management',
    })


@admin_required
def admin_user_edit(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = AdminUserEditForm(request.POST, instance=target_user)
        if form.is_valid():
            form.save()
            messages.success(request, f"User {target_user.username} updated!")
            return redirect('admin_panel:user_list')
    else:
        form = AdminUserEditForm(instance=target_user)
    return render(request, 'admin_panel/user_edit.html', {
        'form': form, 'target_user': target_user, 'page_title': f'Edit: {target_user.username}',
    })


@superadmin_required
def admin_site_config(request):
    configs = SiteConfig.objects.all().order_by('param_name')
    if request.method == 'POST':
        key, value = request.POST.get('param_name'), request.POST.get('value')
        if key and value is not None:
            SiteConfig.set(key, value, user=request.user)
            messages.success(request, f"Config '{key}' updated!")
            return redirect('admin_panel:site_config')
    return render(request, 'admin_panel/site_config.html', {'configs': configs, 'page_title': 'Site Configuration'})


@admin_required
def admin_audit_log(request):
    logs = AuditLog.objects.select_related('admin_user').order_by('-timestamp')
    return render(request, 'admin_panel/audit_log.html', {
        'logs': Paginator(logs, 50).get_page(request.GET.get('page')), 'page_title': 'Audit Log',
    })


@admin_required
def admin_translation_manager(request):
    from .models import ContentTranslation
    if request.method == 'POST':
        from .services import translate_content
        return JsonResponse({'translated': translate_content(request.POST.get('text', ''), request.POST.get('language', 'es'))})
    translations = ContentTranslation.objects.all().order_by('-updated_at')
    return render(request, 'admin_panel/translations.html', {
        'translations': Paginator(translations, 50).get_page(request.GET.get('page')),
        'page_title': 'Translation Manager',
    })


@admin_required
def admin_listings_list(request):
    from apps.listings.models import Listing
    qs = Listing.objects.exclude(status='deleted').select_related('vendor').order_by('-created_at')
    return render(request, 'admin_panel/listings.html', {
        'listings': Paginator(qs, 25).get_page(request.GET.get('page')), 'page_title': 'All Listings',
    })


@admin_required
def admin_orders_list(request):
    from apps.orders.models import Order
    qs = Order.objects.select_related('buyer', 'vendor', 'listing').order_by('-created_at')
    return render(request, 'admin_panel/orders.html', {
        'orders': Paginator(qs, 25).get_page(request.GET.get('page')), 'page_title': 'All Orders',
    })


@admin_required
def admin_escrow_list(request):
    from apps.orders.models import Escrow
    qs = Escrow.objects.select_related('order').order_by('-locked_at')
    return render(request, 'admin_panel/escrow.html', {'escrows': qs[:100], 'page_title': 'Escrow Management'})


@admin_required
def admin_tickets_list(request):
    from apps.messaging.models import Ticket
    qs = Ticket.objects.select_related('user').order_by('-created_at')
    return render(request, 'admin_panel/tickets.html', {
        'tickets': Paginator(qs, 25).get_page(request.GET.get('page')), 'page_title': 'All Tickets',
    })


@admin_required
def admin_vendors_list(request):
    from apps.vendors.models import VendorProfile
    status_filter = request.GET.get('status', '')
    qs = VendorProfile.objects.select_related('user').order_by('-created_at')
    if status_filter:
        qs = qs.filter(verified_status=status_filter)
    return render(request, 'admin_panel/vendors.html', {
        'vendors': qs[:100], 'status_filter': status_filter, 'page_title': 'Vendor Management',
    })


@admin_required
def admin_vendor_approve(request, user_id):
    from apps.vendors.models import VendorProfile
    vendor = get_object_or_404(VendorProfile, user__id=user_id)
    vendor.verified_status = 'approved'
    vendor.save(update_fields=['verified_status'])
    vendor.user.verified_vendor = True
    vendor.user.save(update_fields=['verified_vendor'])
    messages.success(request, f"Vendor {vendor.shop_name} approved!")
    return redirect('admin_panel:vendors')


@admin_required
def admin_vendor_reject(request, user_id):
    from apps.vendors.models import VendorProfile
    vendor = get_object_or_404(VendorProfile, user__id=user_id)
    vendor.verified_status = 'rejected'
    vendor.save(update_fields=['verified_status'])
    messages.success(request, f"Vendor {vendor.shop_name} rejected.")
    return redirect('admin_panel:vendors')


@admin_required
def admin_auctions_list(request):
    from apps.auctions.models import Auction
    qs = Auction.objects.select_related('listing').order_by('-created_at')
    return render(request, 'admin_panel/auctions.html', {'auctions': qs[:100], 'page_title': 'All Auctions'})


# ─── ADMIN WITHDRAWAL MANAGEMENT ─────────────────────────────────────────────

@admin_required
def admin_withdrawals(request):
    from apps.accounts.models import WithdrawalRequest
    qs = WithdrawalRequest.objects.select_related('user').order_by('-created_at')
    status_filter = request.GET.get('status', 'pending')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'admin_panel/withdrawals.html', {
        'withdrawals': qs[:100],
        'status_filter': status_filter,
        'page_title': 'Withdrawal Requests',
    })


@admin_required
def admin_withdrawal_approve(request, withdrawal_id):
    from apps.accounts.models import WithdrawalRequest
    from django.utils import timezone as tz
    wr = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    if request.method == 'POST' and wr.status == WithdrawalRequest.Status.PENDING:
        note = request.POST.get('admin_note', '')
        wr.status = WithdrawalRequest.Status.APPROVED
        wr.admin_note = note
        wr.processed_by = request.user
        wr.processed_at = tz.now()
        wr.save()
        AuditLog.objects.create(
            admin_user=request.user, action=AuditLog.Action.UPDATE,
            target_model='WithdrawalRequest', target_id=str(withdrawal_id),
            description=f"Approved withdrawal of {wr.amount_coins} coins for {wr.user.username}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f"Withdrawal approved for {wr.user.username}.")
    return redirect('admin_panel:withdrawals')


@admin_required
def admin_withdrawal_reject(request, withdrawal_id):
    from apps.accounts.models import WithdrawalRequest
    from apps.orders.models import WalletTransaction
    from django.utils import timezone as tz
    wr = get_object_or_404(WithdrawalRequest, id=withdrawal_id)
    if request.method == 'POST' and wr.status == WithdrawalRequest.Status.PENDING:
        note = request.POST.get('admin_note', 'Rejected by admin.')
        # Refund coins back to user
        wr.user.coin_balance += wr.amount_coins
        wr.user.save(update_fields=['coin_balance'])
        WalletTransaction.objects.create(
            user=wr.user, transaction_type='refund',
            amount_coins=wr.amount_coins,
            balance_after=wr.user.coin_balance,
            description=f"Withdrawal rejection refund — {note}",
            created_by=request.user,
        )
        wr.status = WithdrawalRequest.Status.REJECTED
        wr.admin_note = note
        wr.processed_by = request.user
        wr.processed_at = tz.now()
        wr.save()
        AuditLog.objects.create(
            admin_user=request.user, action=AuditLog.Action.UPDATE,
            target_model='WithdrawalRequest', target_id=str(withdrawal_id),
            description=f"Rejected withdrawal of {wr.amount_coins} coins for {wr.user.username}",
        )
        messages.success(request, f"Withdrawal rejected. Coins refunded to {wr.user.username}.")
    return redirect('admin_panel:withdrawals')


# ─── ADMIN DEPOSIT MANAGEMENT ─────────────────────────────────────────────────

@admin_required
def admin_deposits(request):
    from apps.accounts.models import DepositRequest
    qs = DepositRequest.objects.select_related('user').order_by('-created_at')
    status_filter = request.GET.get('status', 'pending')
    if status_filter:
        qs = qs.filter(status=status_filter)
    return render(request, 'admin_panel/deposits.html', {
        'deposits': qs[:100],
        'status_filter': status_filter,
        'page_title': 'Deposit Requests',
    })


@admin_required
def admin_deposit_approve(request, deposit_id):
    from apps.accounts.models import DepositRequest
    from apps.accounts.services import credit_wallet
    from django.utils import timezone as tz
    dr = get_object_or_404(DepositRequest, id=deposit_id)
    if request.method == 'POST' and dr.status == DepositRequest.Status.PENDING:
        note = request.POST.get('admin_note', '')
        credit_wallet(
            user=dr.user,
            amount_coins=dr.coins_requested,
            tx_type='deposit',
            description=f"Deposit approved: {dr.coins_requested} TP Coins ({dr.currency})",
            tx_hash=dr.tx_hash,
            admin_user=request.user,
            reference_id=str(dr.id),
        )
        dr.status = DepositRequest.Status.APPROVED
        dr.admin_note = note
        dr.processed_by = request.user
        dr.processed_at = tz.now()
        dr.save()
        AuditLog.objects.create(
            admin_user=request.user, action=AuditLog.Action.BALANCE_ADJUST,
            target_model='DepositRequest', target_id=str(deposit_id),
            description=f"Approved deposit of {dr.coins_requested} coins for {dr.user.username}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f"{dr.coins_requested} coins credited to {dr.user.username}.")
    return redirect('admin_panel:deposits')


@admin_required
def admin_deposit_reject(request, deposit_id):
    from apps.accounts.models import DepositRequest
    from django.utils import timezone as tz
    dr = get_object_or_404(DepositRequest, id=deposit_id)
    if request.method == 'POST' and dr.status == DepositRequest.Status.PENDING:
        note = request.POST.get('admin_note', 'Rejected by admin.')
        dr.status = DepositRequest.Status.REJECTED
        dr.admin_note = note
        dr.processed_by = request.user
        dr.processed_at = tz.now()
        dr.save()
        messages.success(request, f"Deposit request rejected for {dr.user.username}.")
    return redirect('admin_panel:deposits')


# ─── ADMIN PLATFORM WALLET ────────────────────────────────────────────────────

@admin_required
def admin_platform_wallet(request):
    from apps.accounts.models import PlatformWallet
    pw = PlatformWallet.get_or_create_main()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'withdraw':
            from decimal import Decimal as D
            amount_coins = D(request.POST.get('amount_coins', '0'))
            note   = request.POST.get('note', 'Admin withdrawal')
            if amount_coins > 0 and amount_coins <= pw.coin_balance:
                pw.coin_balance    -= amount_coins
                pw.total_withdrawn += amount_coins
                pw.save()
                AuditLog.objects.create(
                    admin_user=request.user, action=AuditLog.Action.BALANCE_ADJUST,
                    target_model='PlatformWallet', target_id='1',
                    description=f"Platform wallet withdrawal: {amount_coins} coins — {note}",
                )
                messages.success(request, f"Withdrew {amount_coins} coins from platform wallet.")
            else:
                messages.error(request, "Invalid amount_coins.")
        elif action == 'transfer':
            from decimal import Decimal as D
            amount_coins      = D(request.POST.get('amount_coins', '0'))
            to_username = request.POST.get('to_username', '').strip()
            note        = request.POST.get('note', 'Platform giveaway')
            try:
                recipient = User.objects.get(username=to_username)
                if amount_coins > 0 and amount_coins <= pw.coin_balance:
                    pw.coin_balance    -= amount_coins
                    pw.total_withdrawn += amount_coins
                    pw.save()
                    recipient.coin_balance += amount_coins
                    recipient.save(update_fields=['coin_balance'])
                    from apps.orders.models import WalletTransaction
                    WalletTransaction.objects.create(
                        user=recipient, transaction_type='admin_credit',
                        amount_coins=amount_coins, balance_after=recipient.coin_balance,
                        description=f"Transfer from platform wallet: {note}",
                        created_by=request.user,
                    )
                    messages.success(request, f"Transferred {amount_coins} coins to {recipient.username}.")
                else:
                    messages.error(request, "Invalid amount_coins.")
            except User.DoesNotExist:
                messages.error(request, f"User '{to_username}' not found.")
        return redirect('admin_panel:platform_wallet')

    from apps.orders.models import WalletTransaction
    recent_commissions = WalletTransaction.objects.filter(
        transaction_type='commission_coins'
    ).order_by('-timestamp')[:20]
    return render(request, 'admin_panel/platform_wallet.html', {
        'pw': pw,
        'recent_commissions': recent_commissions,
        'page_title': 'Platform Wallet',
    })


# ─── ADMIN LISTING APPROVAL ───────────────────────────────────────────────────

@admin_required
def admin_listing_approve(request, listing_id):
    from apps.listings.models import Listing
    listing = get_object_or_404(Listing, id=listing_id)
    if request.method == 'POST':
        listing.status = Listing.Status.ACTIVE
        listing.admin_verified = True
        listing.admin_note = request.POST.get('note', '')
        listing.save(update_fields=['status', 'admin_verified', 'admin_note'])
        AuditLog.objects.create(
            admin_user=request.user, action=AuditLog.Action.UPDATE,
            target_model='Listing', target_id=str(listing_id),
            description=f"Approved listing: {listing.title}",
        )
        messages.success(request, f"Listing '{listing.title}' approved and live!")
    return redirect('admin_panel:listings')


@admin_required
def admin_listing_reject(request, listing_id):
    from apps.listings.models import Listing
    listing = get_object_or_404(Listing, id=listing_id)
    if request.method == 'POST':
        note = request.POST.get('note', 'Does not meet platform requirements.')
        listing.status = Listing.Status.SUSPENDED
        listing.admin_verified = False
        listing.admin_note = note
        listing.save(update_fields=['status', 'admin_verified', 'admin_note'])
        from apps.accounts.services import send_system_message
        send_system_message(listing.vendor.user,
            f"Listing '{listing.title}' was rejected",
            f"Your listing '{listing.title}' was rejected.\nReason: {note}")
        messages.success(request, f"Listing rejected. Vendor notified.")
    return redirect('admin_panel:listings')


# ─── ADMIN AUTO-APPROVAL RULES ────────────────────────────────────────────────

@admin_required
def admin_approval_rules(request):
    from apps.listings.models import AutoApprovalRule
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            AutoApprovalRule.objects.create(
                rule_type   = request.POST.get('rule_type'),
                value       = request.POST.get('value', ''),
                action      = request.POST.get('rule_action', 'reject'),
                reason      = request.POST.get('reason', ''),
                is_active   = True,
                created_by  = request.user,
            )
            messages.success(request, "Rule added.")
        elif action == 'delete':
            rule_id = request.POST.get('rule_id')
            AutoApprovalRule.objects.filter(id=rule_id).delete()
            messages.success(request, "Rule deleted.")
        elif action == 'toggle':
            rule_id = request.POST.get('rule_id')
            rule = AutoApprovalRule.objects.get(id=rule_id)
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active'])
        return redirect('admin_panel:approval_rules')

    rules = AutoApprovalRule.objects.all().order_by('-created_at')
    return render(request, 'admin_panel/approval_rules.html', {
        'rules': rules,
        'rule_types': AutoApprovalRule.RuleType.choices,
        'page_title': 'Auto-Approval Rules',
    })


# ─── LEADERBOARD ─────────────────────────────────────────────────────────────

def leaderboard(request):
    from apps.vendors.models import VendorProfile
    from apps.accounts.models import VENDOR_RANKS, BUYER_RANKS, get_vendor_rank, get_buyer_rank

    top_vendors = VendorProfile.objects.filter(
        verified_status='approved'
    ).select_related('user').order_by('-total_sales')[:50]

    top_buyers = User.objects.filter(
        role__in=['buyer', 'reseller']
    ).order_by('-purchase_total')[:50]

    vendor_data = []
    for i, v in enumerate(top_vendors, 1):
        rk, rl = get_vendor_rank(v.total_sales)
        vendor_data.append({'rank_num': i, 'vendor': v, 'rank_key': rk, 'rank_label': rl})

    buyer_data = []
    for i, b in enumerate(top_buyers, 1):
        rk, rl = get_buyer_rank(b.purchase_count)
        buyer_data.append({'rank_num': i, 'buyer': b, 'rank_key': rk, 'rank_label': rl})

    return render(request, 'leaderboard.html', {
        'vendor_data': vendor_data,
        'buyer_data': buyer_data,
        'page_title': 'Leaderboard',
    })

"""
ToasterPants REST API
=======================
JWT-authenticated. Role-based. Full CRUD.
Vendors manage listings. Buyers place orders. Admin rules everything.
TP
"""

from rest_framework import viewsets, generics, status, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
import logging

from apps.accounts.models import User
from apps.listings.models import Listing, ListingCategory
from apps.auctions.models import Auction, Bid
from apps.orders.models import Order, Escrow
from apps.messaging.models import MessageThread, Message
from apps.reviews.models import Review
from apps.support.models import Ticket
from apps.wallet.models import WalletTransaction
from .serializers import (
    ListingSerializer, OrderSerializer, BidSerializer,
    MessageSerializer, ReviewSerializer, TicketSerializer,
    WalletTransactionSerializer, UserProfileSerializer,
    AuctionStatusSerializer,
)
from .permissions import IsVendor, IsAdminUser, IsOwnerOrAdmin

logger = logging.getLogger('toasterpants')


# ─── JWT TOKEN CUSTOMIZATION ──────────────────────────────────────────────────

class ToasterPantsTokenSerializer(TokenObtainPairSerializer):
    """Add user role and display to JWT claims."""
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['display'] = user.display
        token['username'] = user.username
        return token


class ToasterPantsTokenView(TokenObtainPairView):
    serializer_class = ToasterPantsTokenSerializer


# ─── LISTING API ──────────────────────────────────────────────────────────────

class ListingViewSet(viewsets.ModelViewSet):
    """
    Full CRUD for listings.
    - GET (list/retrieve): Public
    - POST/PATCH/DELETE: Vendor only (their own listings)
    - Admin can do everything
    """
    serializer_class = ListingSerializer
    queryset = Listing.objects.filter(status=Listing.Status.ACTIVE).select_related('vendor')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Listing.objects.select_related('vendor', 'category')

        # Public: only active listings
        if not self.request.user.is_authenticated or self.request.user.role not in ['admin', 'super_admin']:
            qs = qs.filter(status=Listing.Status.ACTIVE)

        # Vendor: only their own
        if self.request.user.is_authenticated and self.request.user.role == 'vendor':
            if self.action not in ['list', 'retrieve']:
                qs = qs.filter(vendor__user=self.request.user)

        # Filters
        params = self.request.query_params
        if params.get('type'):
            qs = qs.filter(listing_type=params['type'])
        if params.get('category'):
            qs = qs.filter(category__slug=params['category'])
        if params.get('q'):
            from django.db.models import Q
            qs = qs.filter(Q(title__icontains=params['q']) | Q(description__icontains=params['q']))
        if params.get('vendor'):
            qs = qs.filter(vendor__shop_name__icontains=params['vendor'])
        if params.get('min_price'):
            qs = qs.filter(price__gte=params['min_price'])
        if params.get('max_price'):
            qs = qs.filter(price__lte=params['max_price'])

        return qs.order_by('-created_at')

    def perform_create(self, serializer):
        """Vendor creates a listing — auto-attach vendor profile."""
        if self.request.user.role != 'vendor':
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only vendors can create listings.")
        vendor_profile = self.request.user.vendor_profile
        if not vendor_profile.is_active:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Vendor account not approved yet.")
        serializer.save(vendor=vendor_profile)

    def perform_destroy(self, instance):
        """Soft-delete: mark as deleted, don't remove from DB."""
        instance.status = Listing.Status.DELETED
        instance.save(update_fields=['status'])


# ─── AUCTION API ──────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def auction_status(request, auction_id):
    """Polling endpoint for live auction status (timer, bids, anti-snipe)."""
    try:
        auction = Auction.objects.get(id=auction_id)
    except Auction.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    return Response({
        'id': str(auction.id),
        'status': auction.status,
        'current_bid': str(auction.current_bid),
        'minimum_next_bid': str(auction.minimum_next_bid),
        'end_time': auction.end_time.isoformat(),
        'new_end_time': auction.end_time.isoformat(),
        'seconds_remaining': auction.seconds_remaining,
        'extension_count': auction.extension_count,
        'total_bids': auction.bids.count(),
        'winner': auction.winner.display if auction.winner else None,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_bid(request, auction_id):
    """Place a bid on an auction. Handles anti-snipe extension automatically."""
    try:
        auction = Auction.objects.select_for_update().get(id=auction_id)
    except Auction.DoesNotExist:
        return Response({'error': 'Auction not found'}, status=404)

    if not auction.is_active:
        return Response({'error': 'Auction is not active'}, status=400)

    bid_amount = Decimal(str(request.data.get('bid_amount', 0)))
    is_buyout = request.data.get('buyout', False)
    use_auto_bid = request.data.get('use_auto_bid', False)
    max_auto_bid = request.data.get('max_auto_bid')

    # Buyout handling
    if is_buyout and auction.buyout_price:
        bid_amount = auction.buyout_price

    # Validate bid amount
    if bid_amount < auction.minimum_next_bid:
        return Response({
            'error': f'Bid must be at least {auction.minimum_next_bid}'
        }, status=400)

    # Check wallet balance
    if request.user.coin_balance < bid_amount:
        return Response({'error': 'Insufficient wallet balance'}, status=400)

    with transaction.atomic():
        # Mark previous winning bid as not winning
        Bid.objects.filter(auction=auction, is_winning=True).update(is_winning=False)

        # Create new bid
        triggered_extension = auction.should_extend()
        bid = Bid.objects.create(
            auction=auction,
            bidder=request.user,
            bid_amount=bid_amount,
            is_winning=True,
            is_auto_bid=use_auto_bid,
            max_auto_bid=Decimal(str(max_auto_bid)) if max_auto_bid else None,
            triggered_extension=triggered_extension,
            ip_address=request.META.get('REMOTE_ADDR'),
        )

        # Update auction current bid
        auction.current_bid = bid_amount
        if is_buyout and auction.buyout_price and bid_amount >= auction.buyout_price:
            auction.status = Auction.Status.ENDED
            auction.winner = request.user

        # Anti-snipe extension
        if triggered_extension:
            auction.extend()
        else:
            auction.save(update_fields=['current_bid', 'status', 'winner'])

    return Response({
        'success': True,
        'bid_amount': str(bid_amount),
        'is_winning': True,
        'extended': triggered_extension,
        'new_end_time': auction.end_time.isoformat(),
        'extension_count': auction.extension_count,
    })


# ─── ORDER API ────────────────────────────────────────────────────────────────

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    """Buyers view their own orders. Vendors view orders for their listings."""
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ['admin', 'super_admin']:
            return Order.objects.all().select_related('buyer', 'vendor', 'listing')
        elif user.role == 'vendor':
            return Order.objects.filter(vendor__user=user).select_related('listing')
        else:
            return Order.objects.filter(buyer=user).select_related('listing', 'vendor')

    @action(detail=True, methods=['post'])
    def verify_delivery(self, request, pk=None):
        """Buyer verifies delivery — triggers escrow release."""
        order = self.get_object()
        if order.buyer != request.user:
            return Response({'error': 'Not your order'}, status=403)
        if order.status not in [Order.Status.DELIVERED, Order.Status.PROCESSING]:
            return Response({'error': 'Order not in deliverable state'}, status=400)

        with transaction.atomic():
            order.status = Order.Status.VERIFIED
            order.save(update_fields=['status'])
            if hasattr(order, 'escrow') and order.escrow.status == Escrow.Status.LOCKED:
                order.escrow.release_to_vendor()

        return Response({'success': True, 'status': 'verified'})

    @action(detail=True, methods=['post'])
    def open_dispute(self, request, pk=None):
        """Buyer opens a dispute on an order."""
        order = self.get_object()
        if order.buyer != request.user:
            return Response({'error': 'Not your order'}, status=403)
        reason = request.data.get('reason', '')
        with transaction.atomic():
            order.status = Order.Status.DISPUTED
            order.dispute_reason = reason
            order.save(update_fields=['status', 'dispute_reason'])
            if hasattr(order, 'escrow'):
                order.escrow.status = Escrow.Status.DISPUTED
                order.escrow.dispute_opened_at = timezone.now()
                order.escrow.save(update_fields=['status', 'dispute_opened_at'])
        return Response({'success': True, 'status': 'disputed'})


# ─── MESSAGING API ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_threads(request):
    """Get all message threads for current user."""
    threads = MessageThread.objects.filter(
        participants=request.user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')[:20]

    data = []
    for thread in threads:
        last_msg = thread.messages.order_by('-timestamp').first()
        data.append({
            'id': str(thread.id),
            'subject': thread.subject,
            'last_message': last_msg.content[:100] if last_msg else None,
            'last_message_time': last_msg.timestamp.isoformat() if last_msg else None,
            'unread': thread.messages.filter(is_read=False).exclude(sender=request.user).count(),
        })
    return Response(data)


# ─── RESELLER API ─────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def request_reseller_upgrade(request):
    """Request upgrade to reseller status (if eligible)."""
    user = request.user
    if user.role == User.Role.RESELLER:
        return Response({'error': 'Already a reseller'}, status=400)
    if not user.is_reseller_eligible:
        remaining = Decimal('100.00') - user.purchase_total
        return Response({
            'error': f'Not eligible yet. Need ${remaining:.2f} more in purchases.',
            'purchase_total': str(user.purchase_total),
            'threshold': '100.00',
        }, status=400)

    user.role = User.Role.RESELLER
    user.save(update_fields=['role'])
    return Response({'success': True, 'message': 'Welcome to the reseller club! TP'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def reseller_daily_status(request):
    """Check how many resales today and if limit reached."""
    from apps.orders.models import ResaleRecord
    import datetime

    today_count = ResaleRecord.objects.filter(
        reseller=request.user,
        resale_date=datetime.date.today()
    ).count()

    from apps.accounts.models import SiteConfig
    daily_limit = int(SiteConfig.get('RESELLER_DAILY_LIMIT', 1))

    return Response({
        'today_resales': today_count,
        'daily_limit': daily_limit,
        'can_resell': request.user.role == 'reseller' and today_count < daily_limit,
    })


# ─── ADMIN API ENDPOINTS ──────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_release_escrow(request, escrow_id):
    """Admin manually releases escrow funds to vendor."""
    if request.user.role not in ['admin', 'super_admin']:
        return Response({'error': 'Admin only'}, status=403)
    try:
        escrow = Escrow.objects.get(id=escrow_id)
    except Escrow.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    from apps.accounts.models import AuditLog
    with transaction.atomic():
        escrow.release_to_vendor(admin_user=request.user)
        AuditLog.objects.create(
            admin_user=request.user,
            action=AuditLog.Action.ESCROW_OVERRIDE,
            target_model='Escrow',
            target_id=str(escrow_id),
            description=f"Admin manually released escrow #{escrow_id}",
            ip_address=request.META.get('REMOTE_ADDR')
        )

    return Response({'success': True, 'status': 'released'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_confirm_deposit(request):
    """Admin confirms crypto deposit and credits user wallet."""
    if request.user.role not in ['admin', 'super_admin']:
        return Response({'error': 'Admin only'}, status=403)

    user_id = request.data.get('user_id')
    tx_hash = str(request.data.get('tx_hash', '')).strip()
    note = str(request.data.get('note', '')).strip()
    currency = str(request.data.get('currency', 'USDT_TRC20')).strip() or 'USDT_TRC20'

    try:
        amount = Decimal(str(request.data.get('amount', '0')))
    except Exception:
        return Response({'error': 'Invalid amount'}, status=400)

    if amount <= 0:
        return Response({'error': 'Amount must be greater than zero'}, status=400)

    if not tx_hash:
        return Response({'error': 'Transaction hash is required'}, status=400)

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=404)

    from apps.accounts.services import credit_wallet
    from apps.accounts.models import AuditLog

    updated_user = credit_wallet(
        target_user,
        amount,
        WalletTransaction.Type.DEPOSIT,
        description="Crypto deposit confirmed by admin",
        tx_hash=tx_hash,
        admin_user=request.user,
        admin_note=note,
    )

    AuditLog.objects.create(
        admin_user=request.user,
        action=AuditLog.Action.BALANCE_ADJUST,
        target_model='User',
        target_id=str(user_id),
        description=(
            f"Admin credited {amount} {currency} to "
            f"{updated_user.username}. TxHash: {tx_hash}"
        ),
        ip_address=request.META.get('REMOTE_ADDR')
    )

    return Response({
        'success': True,
        'credited': str(amount),
        'new_balance': str(target_user.coin_balance)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_run_cron(request):
    """Admin manually triggers a cron task."""
    if request.user.role not in ['admin', 'super_admin']:
        return Response({'error': 'Admin only'}, status=403)

    task_name = request.data.get('task')
    from apps.cron.tasks import manual_task_runner
    try:
        result = manual_task_runner.delay(task_name)
        return Response({'success': True, 'task_id': str(result.id)})
    except ValueError as e:
        return Response({'error': str(e)}, status=400)


# ─── TRANSLATION API ──────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def auto_translate(request):
    """Trigger external translation API for content."""
    if request.user.role not in ['admin', 'super_admin']:
        return Response({'error': 'Admin only'}, status=403)

    from apps.accounts.services import translate_content
    text = request.data.get('text', '')
    target_lang = request.data.get('language', 'es')

    if not text:
        return Response({'error': 'No text provided'}, status=400)

    translated = translate_content(text, target_lang)
    return Response({'original': text, 'translated': translated, 'language': target_lang})


# ─── API DOCS VIEW ────────────────────────────────────────────────────────────

from django.shortcuts import render as django_render
from rest_framework.decorators import api_view, permission_classes as perm_classes
from rest_framework.permissions import AllowAny as AllowAnyPerm

def api_docs(request):
    """Human-readable API documentation page."""
    auth_endpoints = [
        {'method':'POST','path':'/api/v1/auth/token/','auth':False,'description':'Get JWT access + refresh tokens','body':'{"username": "user", "password": "pass"}'},
        {'method':'POST','path':'/api/v1/auth/token/refresh/','auth':False,'description':'Refresh your access token','body':'{"refresh": "<refresh_token>"}'},
        {'method':'POST','path':'/api/v1/auth/token/blacklist/','auth':True,'description':'Logout — blacklist your refresh token','body':None},
    ]
    listing_endpoints = [
        {'method':'GET','path':'/api/v1/listings/','auth':False,'role':'','description':'Browse all active listings. Supports ?q=, ?type=, ?category=, ?min_price=, ?max_price=, ?sort='},
        {'method':'GET','path':'/api/v1/listings/{id}/','auth':False,'role':'','description':'Get a single listing detail'},
        {'method':'POST','path':'/api/v1/listings/','auth':True,'role':'Vendor','description':'Create a new listing'},
        {'method':'PATCH','path':'/api/v1/listings/{id}/','auth':True,'role':'Vendor','description':'Update your listing'},
        {'method':'DELETE','path':'/api/v1/listings/{id}/','auth':True,'role':'Vendor','description':'Delete (soft-delete) your listing'},
    ]
    auction_endpoints = [
        {'method':'GET','path':'/api/v1/auctions/{id}/status/','auth':False,'role':'','description':'Live auction status — current bid, time remaining, extension count. Poll every 10s.'},
        {'method':'POST','path':'/api/v1/auctions/{id}/bid/','auth':True,'role':'Buyer','description':'Place a bid. Include buyout=1 for instant purchase if buyout price is set.'},
    ]
    order_endpoints = [
        {'method':'GET','path':'/api/v1/orders/','auth':True,'role':'Buyer/Vendor','description':'List your orders (buyers see their purchases, vendors see received orders)'},
        {'method':'GET','path':'/api/v1/orders/{id}/','auth':True,'role':'Buyer/Vendor','description':'Get a single order detail'},
        {'method':'POST','path':'/api/v1/orders/{id}/verify_delivery/','auth':True,'role':'Buyer','description':'Verify delivery received — triggers escrow release to vendor'},
        {'method':'POST','path':'/api/v1/orders/{id}/open_dispute/','auth':True,'role':'Buyer','description':'Open a dispute on an order — escrow stays locked'},
        {'method':'GET','path':'/api/v1/messages/','auth':True,'role':'Any','description':'Get your message threads'},
        {'method':'POST','path':'/api/v1/reseller/upgrade/','auth':True,'role':'Buyer','description':'Request reseller upgrade (requires $100+ in purchases)'},
        {'method':'GET','path':'/api/v1/reseller/daily-status/','auth':True,'role':'Reseller','description':'Check how many resales you have done today'},
    ]
    admin_endpoints = [
        {'method':'POST','path':'/api/v1/admin/escrow/{id}/release/','description':'Manually release escrow funds to vendor'},
        {'method':'POST','path':'/api/v1/admin/deposit/confirm/','description':'Confirm crypto deposit and credit user wallet'},
        {'method':'POST','path':'/api/v1/admin/cron/run/','description':'Manually trigger a background cron task'},
        {'method':'POST','path':'/api/v1/admin/translate/','description':'Auto-translate content via external API'},
    ]
    return django_render(request, 'api/docs.html', {
        'auth_endpoints': auth_endpoints,
        'listing_endpoints': listing_endpoints,
        'auction_endpoints': auction_endpoints,
        'order_endpoints': order_endpoints,
        'admin_endpoints': admin_endpoints,
        'page_title': 'API Documentation',
    })

"""
ToasterPants — Orders Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction as db_transaction
from django.core.paginator import Paginator
from decimal import Decimal
from .models import Order, Escrow, WalletTransaction
from apps.listings.models import Listing
from apps.accounts.models import SiteConfig


def _calculate_order_totals(listing, quantity=1):
    """
    Calculate all order amounts in TP Coins.
    Commission is NOT charged to buyer — deducted from vendor payout.
    Buyer pays: item price + 2% buyer fee + shipping + 2% brokerage (physical only)
    """
    from apps.accounts.models import usd_to_coins
    from apps.accounts.models import TP_COIN_VALUE_USD

    commission_rate   = Decimal(SiteConfig.get('COMMISSION_RATE', '0.08'))
    buyer_fee_rate    = Decimal('0.02')
    brokerage_rate    = Decimal('0.02')
    min_coins_deposit = Decimal(SiteConfig.get('MIN_DEPOSIT_COINS', '1'))

    # Base in coins
    unit_price_coins  = usd_to_coins(listing.price_usd) * quantity
    shipping_usd      = listing.shipping_fee_usd if listing.requires_shipping else Decimal('0')
    shipping_coins    = usd_to_coins(shipping_usd)

    subtotal_coins    = unit_price_coins
    buyer_fee_coins   = (subtotal_coins * buyer_fee_rate).quantize(Decimal('0.0001'))
    brokerage_coins   = Decimal('0')
    if listing.listing_type == 'physical':
        brokerage_coins = (subtotal_coins * brokerage_rate).quantize(Decimal('0.0001'))

    total_coins = subtotal_coins + buyer_fee_coins + brokerage_coins + shipping_coins

    # Commission deducted from vendor payout (not from buyer)
    commission_coins  = (subtotal_coins * commission_rate).quantize(Decimal('0.0001'))
    vendor_payout     = subtotal_coins - commission_coins

    return {
        'unit_price_coins':    usd_to_coins(listing.price_usd),
        'subtotal_coins':      subtotal_coins,
        'shipping_fee_coins':  shipping_coins,
        'brokerage_fee_coins': brokerage_coins,
        'buyer_tx_fee_coins':  buyer_fee_coins,
        'total_coins':         total_coins,
        'commission_coins':    commission_coins,
        'vendor_payout_coins': vendor_payout,
        'commission_rate_pct': commission_rate * 100,
        'buyer_fee_pct':       buyer_fee_rate * 100,
        'brokerage_fee_pct':   brokerage_rate * 100,
    }


@login_required
def order_list(request):
    if request.user.role in ['vendor', 'vendor_staff']:
        try:
            orders = Order.objects.filter(
                vendor=request.user.vendor_profile
            ).select_related('listing', 'buyer').order_by('-created_at')
        except Exception:
            orders = Order.objects.none()
    else:
        orders = Order.objects.filter(
            buyer=request.user
        ).select_related('listing', 'vendor').order_by('-created_at')

    paginator = Paginator(orders, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'orders/order_list.html', {'orders': page, 'page_title': 'Orders'})


@login_required
def order_detail(request, order_id):
    # Buyer sees their own orders, vendor sees orders for their shop
    if request.user.role in ['vendor', 'vendor_staff', 'admin', 'super_admin']:
        try:
            if request.user.role in ['admin', 'super_admin']:
                order = get_object_or_404(Order, id=order_id)
            else:
                order = get_object_or_404(Order, id=order_id,
                                          vendor=request.user.vendor_profile)
        except Exception:
            order = get_object_or_404(Order, id=order_id, buyer=request.user)
    else:
        order = get_object_or_404(Order, id=order_id, buyer=request.user)

    is_vendor_view = (
        request.user.role in ['vendor', 'vendor_staff'] and
        hasattr(request.user, 'vendor_profile') and
        order.vendor == request.user.vendor_profile
    )

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'is_vendor_view': is_vendor_view,
        'page_title': f'Order #{order.order_number}',
    })


@login_required
def checkout(request, listing_id):
    listing = get_object_or_404(
        Listing,
        id=listing_id,
        status=Listing.Status.ACTIVE,
    )

    totals = _calculate_order_totals(listing)
    requires_shipping = (
        listing.listing_type == 'physical'
        and listing.requires_shipping
    )

    if request.method == 'POST':
        with db_transaction.atomic():
            # Lock the buyer row so the balance check and debit are
            # performed against the same current balance.
            from apps.accounts.models import User

            buyer = User.objects.select_for_update().get(
                pk=request.user.pk
            )

            if buyer.coin_balance < totals['total_coins']:
                messages.error(
                    request,
                    f"Insufficient coins. Need "
                    f"{totals['total_coins']:.4f} TP Coins, "
                    f"you have {buyer.coin_balance:.4f}."
                )
                return redirect('wallet:home')

            order_data = {
                'buyer': buyer,
                'vendor': listing.vendor,
                'listing': listing,
                'unit_price_coins': totals['unit_price_coins'],
                'quantity': 1,
                'subtotal_coins': totals['subtotal_coins'],
                'shipping_fee_coins': totals['shipping_fee_coins'],
                'brokerage_fee_coins': totals['brokerage_fee_coins'],
                'buyer_tx_fee_coins': totals['buyer_tx_fee_coins'],
                'total_coins': totals['total_coins'],
                'commission_coins': totals['commission_coins'],
                'vendor_payout_coins': totals['vendor_payout_coins'],
                'status': Order.Status.PENDING_PAYMENT,
            }

            if requires_shipping:
                order_data.update({
                    'shipping_name': request.POST.get(
                        'shipping_name', ''
                    ).strip(),
                    'shipping_address_1': request.POST.get(
                        'shipping_address_1', ''
                    ).strip(),
                    'shipping_address_2': request.POST.get(
                        'shipping_address_2', ''
                    ).strip(),
                    'shipping_city': request.POST.get(
                        'shipping_city', ''
                    ).strip(),
                    'shipping_state': request.POST.get(
                        'shipping_state', ''
                    ).strip(),
                    'shipping_zip': request.POST.get(
                        'shipping_zip', ''
                    ).strip(),
                    'shipping_country': request.POST.get(
                        'shipping_country', ''
                    ).strip(),
                    'shipping_phone': request.POST.get(
                        'shipping_phone', ''
                    ).strip(),
                })

            order_data['buyer_note'] = request.POST.get(
                'buyer_note', ''
            ).strip()

            order = Order.objects.create(**order_data)

            from apps.accounts.services import lock_escrow_for_order
            lock_escrow_for_order(order)

            buyer.purchase_total += listing.price_usd
            buyer.save(update_fields=['purchase_total'])

            if listing.quantity > 0:
                Listing.objects.filter(pk=listing.pk).update(
                    quantity_sold=listing.quantity_sold + 1
                )

        messages.success(
            request,
            f"Order placed! #{order.order_number} — "
            f"awaiting vendor to release item."
        )
        return redirect('orders:detail', order_id=order.id)

    return render(request, 'orders/checkout.html', {
        'listing': listing,
        'totals': totals,
        'requires_shipping': requires_shipping,
        'page_title': f'Checkout: {listing.title}',
    })


@login_required
def vendor_release_item(request, order_id):
    """Vendor confirms they have sent / released the item."""
    order = get_object_or_404(Order, id=order_id, vendor=request.user.vendor_profile)
    if request.method == 'POST':
        if order.status not in [Order.Status.PAYMENT_RECEIVED, Order.Status.PROCESSING]:
            messages.error(request, "Cannot release this order in its current state.")
            return redirect('orders:detail', order_id=order_id)

        delivery_link    = request.POST.get('delivery_link', '').strip()
        delivery_message = request.POST.get('delivery_message', '').strip()
        tracking_number  = request.POST.get('tracking_number', '').strip()
        carrier          = request.POST.get('carrier', '').strip()

        with db_transaction.atomic():
            from django.utils import timezone as tz
            order.status = Order.Status.ITEM_RELEASED
            order.save(update_fields=['status'])

            delivery, _ = Delivery.objects.get_or_create(
                order=order,
                defaults={'delivery_type': order.listing.listing_type if order.listing else 'digital'}
            )
            delivery.delivery_link    = delivery_link
            delivery.delivery_message = delivery_message
            delivery.tracking_number  = tracking_number
            delivery.carrier          = carrier
            delivery.vendor_released_at = tz.now()
            delivery.save()

        messages.success(request, "Item released! Buyer has been notified.")
        from apps.accounts.services import send_system_message
        if order.buyer:
            send_system_message(order.buyer,
                f"Your order #{order.order_number} has been released",
                f"The vendor has released your item for order #{order.order_number}. "
                f"Please verify delivery to release their payment."
            )
    return redirect('orders:detail', order_id=order_id)


@login_required
def verify_delivery(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    if order.status not in [Order.Status.ITEM_RELEASED, Order.Status.DELIVERED,
                             Order.Status.PROCESSING]:
        messages.error(request, "Cannot verify this order in its current state.")
        return redirect('orders:detail', order_id=order_id)
    with db_transaction.atomic():
        order.status = Order.Status.VERIFIED
        order.save(update_fields=['status'])
        if hasattr(order, 'escrow') and order.escrow.status == Escrow.Status.LOCKED:
            order.escrow.release_to_vendor()
    messages.success(request, "Delivery verified! Funds released to vendor.")
    return redirect('orders:detail', order_id=order_id)


@login_required
def open_dispute(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        with db_transaction.atomic():
            order.status         = Order.Status.DISPUTED
            order.dispute_reason = reason
            order.save(update_fields=['status', 'dispute_reason'])
            if hasattr(order, 'escrow'):
                order.escrow.status = Escrow.Status.DISPUTED
                order.escrow.save(update_fields=['status'])
        messages.success(request, "Dispute opened. Admin will review within 24 hours.")
        return redirect('orders:detail', order_id=order_id)
    return render(request, 'orders/dispute_form.html',
                  {'order': order, 'page_title': 'Open Dispute'})


# Import Delivery here to avoid circular
from .models import Delivery

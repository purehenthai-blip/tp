from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
from .models import Auction, Bid

def auction_list(request):
    auctions = Auction.objects.filter(
        status__in=[Auction.Status.ACTIVE, Auction.Status.EXTENDED]
    ).select_related('listing', 'listing__vendor').order_by('end_time')
    paginator = Paginator(auctions, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'auctions/auction_list.html', {'auctions': page, 'page_title': 'Live Auctions'})

def auction_detail(request, auction_id):
    auction = get_object_or_404(Auction.objects.select_related('listing', 'listing__vendor', 'winner'), id=auction_id)
    bids = auction.bids.select_related('bidder').order_by('-bid_amount')[:20]
    return render(request, 'auctions/auction_detail.html', {
        'auction': auction, 'bids': bids, 'min_next_bid': auction.minimum_next_bid,
        'seconds_remaining': auction.seconds_remaining, 'total_bids': auction.bids.count(),
        'page_title': f'Auction: {auction.listing.title}',
    })

@login_required
def place_bid_view(request, auction_id):
    if request.method != 'POST':
        return redirect('auctions:detail', auction_id=auction_id)
    auction = get_object_or_404(Auction.objects.select_for_update(), id=auction_id)
    if not auction.is_active:
        messages.error(request, "This auction is no longer active.")
        return redirect('auctions:detail', auction_id=auction_id)
    try:
        bid_amount = Decimal(str(request.POST.get('bid_amount', 0)))
    except InvalidOperation:
        messages.error(request, "Invalid bid amount.")
        return redirect('auctions:detail', auction_id=auction_id)
    is_buyout = request.POST.get('buyout') == '1'
    if is_buyout and auction.buyout_price:
        bid_amount = auction.buyout_price
    if bid_amount < auction.minimum_next_bid:
        messages.error(request, f"Bid must be at least {auction.minimum_next_bid}.")
        return redirect('auctions:detail', auction_id=auction_id)
    if request.user.wallet_balance < bid_amount:
        messages.error(request, "Insufficient wallet balance.")
        return redirect('wallet:home')
    with transaction.atomic():
        Bid.objects.filter(auction=auction, is_winning=True).update(is_winning=False)
        triggered_extension = auction.should_extend()
        Bid.objects.create(auction=auction, bidder=request.user, bid_amount=bid_amount,
                           is_winning=True, triggered_extension=triggered_extension,
                           ip_address=request.META.get('REMOTE_ADDR'))
        auction.current_bid = bid_amount
        if is_buyout and auction.buyout_price and bid_amount >= auction.buyout_price:
            auction.status = Auction.Status.ENDED
            auction.winner = request.user
        if triggered_extension:
            auction.extend()
            messages.success(request, f"Bid placed! Auction extended {auction.extension_minutes} mins (anti-snipe).")
        else:
            auction.save(update_fields=['current_bid', 'status', 'winner'])
            messages.success(request, f"Bid of {bid_amount} placed! You're currently winning.")
    return redirect('auctions:detail', auction_id=auction_id)

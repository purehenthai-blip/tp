from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.messaging.models import Review
from apps.listings.models import Listing
from apps.orders.models import Order

@login_required
def add_review(request, listing_id):
    listing = get_object_or_404(Listing, id=listing_id)
    if request.method == 'POST':
        has_purchase = Order.objects.filter(buyer=request.user, listing=listing, status__in=['verified','completed']).exists()
        if not has_purchase:
            messages.error(request, "You need a verified purchase to leave a review.")
            return redirect('listings:detail', listing_id=listing_id)
        if Review.objects.filter(listing=listing, buyer=request.user).exists():
            messages.error(request, "You already reviewed this listing.")
            return redirect('listings:detail', listing_id=listing_id)
        rating = int(request.POST.get('rating', 5))
        comment = request.POST.get('comment', '').strip()
        title = request.POST.get('title', '').strip()
        Review.objects.create(listing=listing, buyer=request.user, rating=rating,
                              title=title, comment=comment, verified_purchase=has_purchase)
        from apps.reviews.services import recalculate_vendor_rating
        recalculate_vendor_rating(listing.vendor)
        messages.success(request, "Review posted!")
    return redirect('listings:detail', listing_id=listing_id)

@login_required
def delete_review(request, review_id):
    if request.user.role in ['admin', 'super_admin']:
        review = get_object_or_404(Review, id=review_id)
        review.admin_removed = True
        review.save(update_fields=['admin_removed'])
    return redirect('/')

"""
ToasterPants — Listings Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST
from .models import Listing, ListingFile, ListingCategory
from apps.accounts.decorators import vendor_required

SORT_OPTIONS = [
    ('-created_at', 'Newest'),
    ('price_asc', 'Price ↑'),
    ('price_desc', 'Price ↓'),
    ('rating', 'Top Rated'),
    ('popular', 'Popular'),
]


@login_required
def listing_list(request):
    qs = Listing.objects.filter(status=Listing.Status.ACTIVE).select_related('vendor', 'category')
    q = request.GET.get('q', '')
    listing_type = request.GET.get('type', '')
    category_slug = request.GET.get('category', '')
    sort = request.GET.get('sort', '-created_at')
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if listing_type:
        qs = qs.filter(listing_type=listing_type)
    if category_slug:
        qs = qs.filter(category__slug=category_slug)
    sort_map = {
        '-created_at': '-created_at', 'price_asc': 'price',
        'price_desc': '-price', 'rating': '-avg_rating', 'popular': '-view_count'
    }
    qs = qs.order_by(sort_map.get(sort, '-created_at'))
    categories = ListingCategory.objects.filter(is_active=True, parent=None).prefetch_related('children')
    paginator = Paginator(qs, 24)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'listings/listing_list.html', {
        'listings': page, 'categories': categories,
        'current_type': listing_type, 'current_category': category_slug,
        'search_q': q, 'sort': sort, 'sort_options': SORT_OPTIONS,
        'listing_types': Listing.Type.choices, 'page_title': 'Browse Listings',
    })


@login_required
def listing_detail(request, listing_id):
    # Allow vendors to preview their own draft listings
    if request.user.is_authenticated and request.user.role in ['vendor', 'vendor_staff', 'admin', 'super_admin']:
        listing = get_object_or_404(
            Listing.objects.select_related('vendor', 'category').prefetch_related('files'),
            id=listing_id
        )
        # Non-admin vendor can only see their own drafts
        if listing.status not in [Listing.Status.ACTIVE, Listing.Status.SOLD_OUT]:
            if request.user.role not in ['admin', 'super_admin']:
                try:
                    if listing.vendor.user != request.user:
                        raise Http404("Not found.")
                except Exception:
                    raise Http404("Not found.")
    else:
        listing = get_object_or_404(
            Listing.objects.select_related('vendor', 'category').prefetch_related('files'),
            id=listing_id, status__in=[Listing.Status.ACTIVE, Listing.Status.SOLD_OUT]
        )

    Listing.objects.filter(pk=listing.pk).update(view_count=listing.view_count + 1)

    auction = None
    bids = []
    min_next_bid = None
    if listing.price_type == Listing.PriceType.AUCTION:
        try:
            auction = listing.auction
            bids = auction.bids.select_related('bidder').order_by('-bid_amount')[:10]
            min_next_bid = auction.minimum_next_bid
        except Exception:
            pass

    reviews = listing.reviews.filter(is_published=True, admin_removed=False).order_by('-created_at')[:10]
    can_review = False
    user_review = None
    if request.user.is_authenticated:
        from apps.messaging.models import Review
        from apps.orders.models import Order
        user_review = Review.objects.filter(listing=listing, buyer=request.user).first()
        can_review = not user_review and Order.objects.filter(
            buyer=request.user, listing=listing,
            status__in=['verified', 'completed']
        ).exists()

    is_own_listing = (
        request.user.is_authenticated and
        hasattr(request.user, 'vendor_profile') and
        listing.vendor == request.user.vendor_profile
    )

    return render(request, 'listings/listing_detail.html', {
        'listing': listing, 'auction': auction, 'bids': bids,
        'min_next_bid': min_next_bid, 'reviews': reviews,
        'can_review': can_review, 'user_review': user_review,
        'seconds_remaining': auction.seconds_remaining if auction else 0,
        'total_bids': len(bids), 'page_title': listing.title,
        'is_own_listing': is_own_listing,
        'tags_list': [t.strip() for t in listing.tags.split(',') if t.strip()] if listing.tags else [],
    })


@login_required
@vendor_required
def vendor_listing_create(request):
    """Create a new listing."""
    from .forms import ListingForm
    try:
        vendor = request.user.vendor_profile
    except Exception:
        messages.error(request, "You need a vendor profile first.")
        return redirect('vendors:apply')

    if not vendor.is_active:
        messages.warning(request, "Your vendor account is pending approval. You can create listings but they won't be visible until your account is approved.")

    if request.method == 'POST':
        form = ListingForm(request.POST, request.FILES, vendor=vendor)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.vendor = vendor
            # Auto-set status based on button clicked
            if request.POST.get('publish'):
                # Run auto-approval rules
                from apps.accounts.services import process_listing_auto_approval
                action, reason = process_listing_auto_approval(listing)
                if action == 'reject':
                    listing.status = Listing.Status.SUSPENDED
                    listing.admin_note = reason
                    listing.save()
                    messages.error(request, f"Listing rejected: {reason}")
                    return redirect('listings:edit', listing_id=listing.id)
                else:
                    # Goes to pending_review — admin still approves
                    listing.status = Listing.Status.PENDING_REVIEW
                    listing.auto_approved = (action == 'approve')
                    listing.save()
                    messages.success(request, f"Listing submitted for admin review. It will go live once approved.")
            else:
                listing.status = Listing.Status.DRAFT
                listing.save()
                messages.success(request, f"Listing '{listing.title}' saved as draft.")
            return redirect('listings:edit', listing_id=listing.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ListingForm(vendor=vendor)

    return render(request, 'listings/listing_form.html', {
        'form': form, 'action': 'Create', 'listing': None,
        'page_title': 'Create New Listing',
    })


@login_required
@vendor_required
def vendor_listing_edit(request, listing_id):
    """Edit an existing listing."""
    from .forms import ListingForm

    try:
        vendor = request.user.vendor_profile
    except Exception:
        messages.error(request, "Vendor profile not found.")
        return redirect('vendors:apply')

    # Admin can edit any listing, vendor only their own
    if request.user.role in ['admin', 'super_admin']:
        listing = get_object_or_404(Listing, id=listing_id)
    else:
        listing = get_object_or_404(Listing, id=listing_id, vendor=vendor)

    if request.method == 'POST':
        # Deletion must happen before form validation. A listing with
        # incomplete/legacy fields must still be deletable.
        if request.POST.get('delete_listing'):
            listing.status = Listing.Status.DELETED
            listing.save(update_fields=['status'])
            messages.success(request, f"'{listing.title}' deleted.")
            return redirect('vendors:dashboard')

        form = ListingForm(
            request.POST, request.FILES, instance=listing,
            vendor=None if request.user.role in ['admin', 'super_admin'] else vendor,
        )
        if form.is_valid():
            updated = form.save(commit=False)

            # Handle publish/unpublish/save actions
            if request.POST.get('publish'):
                updated.status = Listing.Status.ACTIVE
                messages.success(request, f"'{listing.title}' is now live!")
            elif request.POST.get('unpublish'):
                updated.status = Listing.Status.DRAFT
                messages.success(request, f"'{listing.title}' moved to draft.")
            else:
                messages.success(request, "Listing saved!")

            updated.save()
            return redirect('listings:edit', listing_id=listing.id)
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = ListingForm(
        instance=listing,
        vendor=None if request.user.role in ['admin', 'super_admin'] else vendor,
    )

    # Get listing files for display
    listing_files = listing.files.all()

    return render(request, 'listings/listing_form.html', {
        'form': form, 'action': 'Edit', 'listing': listing,
        'listing_files': listing_files,
        'page_title': f'Edit: {listing.title}',
    })


@login_required
@vendor_required
def upload_listing_file(request, listing_id):
    """Upload a file to a listing."""
    from django.conf import settings
    import os, mimetypes

    try:
        vendor = request.user.vendor_profile
    except Exception:
        return JsonResponse({'error': 'Vendor profile not found'}, status=403)

    if request.user.role in ['admin', 'super_admin']:
        listing = get_object_or_404(Listing, id=listing_id)
    else:
        listing = get_object_or_404(Listing, id=listing_id, vendor=vendor)

    if request.method != 'POST':
        return redirect('listings:edit', listing_id=listing_id)

    uploaded = request.FILES.get('file')
    if not uploaded:
        messages.error(request, "No file selected.")
        return redirect('listings:edit', listing_id=listing_id)

    # 20MB limit
    max_size = 20 * 1024 * 1024
    if uploaded.size > max_size:
        messages.error(request, "File too large. Maximum 20MB per file.")
        return redirect('listings:edit', listing_id=listing_id)

    # Check user total quota (100MB)
    from apps.filemanager.models import UserStorageQuota
    quota, _ = UserStorageQuota.objects.get_or_create(user=request.user)
    if quota.used_bytes + uploaded.size > quota.max_bytes:
        messages.error(request, "Storage quota exceeded (100MB max).")
        return redirect('listings:edit', listing_id=listing_id)

    is_public = request.POST.get('is_public') == 'on'
    mime_type, _ = mimetypes.guess_type(uploaded.name)

    lf = ListingFile.objects.create(
        listing=listing,
        file=uploaded,
        original_filename=uploaded.name,
        file_size=uploaded.size,
        mime_type=mime_type or '',
        is_public=is_public,
    )

    quota.used_bytes += uploaded.size
    quota.save(update_fields=['used_bytes'])

    messages.success(request, f"File '{uploaded.name}' uploaded!")
    return redirect('listings:edit', listing_id=listing_id)


@login_required
@require_POST
def delete_listing_file(request, file_id):
    """Delete a file from a listing."""
    listing_file = get_object_or_404(ListingFile, id=file_id)

    # Check ownership
    if request.user.role not in ['admin', 'super_admin']:
        if listing_file.listing.vendor.user != request.user:
            raise Http404("Access denied.")

    listing_id = listing_file.listing.id

    # Update quota
    try:
        from apps.filemanager.models import UserStorageQuota
        quota = UserStorageQuota.objects.get(user=request.user)
        quota.used_bytes = max(0, quota.used_bytes - listing_file.file_size)
        quota.save(update_fields=['used_bytes'])
    except Exception:
        pass

    listing_file.delete()
    messages.success(request, "File deleted.")
    return redirect('listings:edit', listing_id=listing_id)


@login_required
def download_listing_file(request, file_id):
    """Secure file download — buyers who purchased can access."""
    listing_file = get_object_or_404(ListingFile, id=file_id)

    if listing_file.is_public:
        return FileResponse(listing_file.file.open(), as_attachment=True,
                            filename=listing_file.original_filename)

    from apps.orders.models import Order
    has_purchase = Order.objects.filter(
        buyer=request.user, listing=listing_file.listing,
        status__in=['verified', 'completed', 'delivered']
    ).exists()

    if not has_purchase and request.user.role not in ['admin', 'super_admin']:
        try:
            if listing_file.listing.vendor.user != request.user:
                raise Http404("Access denied.")
        except Exception:
            raise Http404("Access denied.")

    return FileResponse(listing_file.file.open(), as_attachment=True,
                        filename=listing_file.original_filename)

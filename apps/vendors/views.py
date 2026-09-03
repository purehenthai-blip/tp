from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from decimal import Decimal
from .models import VendorProfile
from apps.accounts.models import SiteConfig, User


def vendor_directory(request):
    vendors = VendorProfile.objects.filter(
        verified_status='approved'
    ).select_related('user').order_by('-rating')
    paginator = Paginator(vendors, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'vendors/vendor_directory.html', {
        'vendors': page, 'page_title': 'Vendor Directory'
    })


@login_required
def vendor_profile_public(request, shop_slug):
    vendor = get_object_or_404(VendorProfile,
        shop_name__iexact=shop_slug.replace('-', ' '),
        verified_status='approved')
    listings = vendor.listings.filter(status='active').order_by('-created_at')[:12]
    return render(request, 'vendors/vendor_profile.html', {
        'vendor': vendor, 'listings': listings, 'page_title': vendor.shop_name
    })


@login_required
def vendor_apply(request):
    if hasattr(request.user, 'vendor_profile'):
        messages.info(request, "You already have a vendor profile.")
        return redirect('vendors:dashboard')

    app_fee_usd = Decimal(SiteConfig.get('VENDOR_APPLICATION_FEE', '10.00'))
    from apps.accounts.models import usd_to_coins
    app_fee_coins = usd_to_coins(app_fee_usd)

    if request.method == 'POST':
        shop_name         = request.POST.get('shop_name', '').strip()
        shop_description  = request.POST.get('shop_description', '').strip()

        if not shop_name:
            messages.error(request, "Shop name is required.")
        elif VendorProfile.objects.filter(shop_name__iexact=shop_name).exists():
            messages.error(request, "Shop name already taken. Choose another.")
        elif request.user.coin_balance < app_fee_coins:
            messages.error(request,
                f"Insufficient coins. Application fee is {app_fee_coins} TP Coins "
                f"(${app_fee_usd} USD). You have {request.user.coin_balance:.4f} coins. "
                f"Please deposit more coins first.")
        else:
            from apps.accounts.services import debit_wallet
            from apps.orders.models import WalletTransaction
            try:
                debit_wallet(
                    user=request.user,
                    amount=app_fee_coins,
                    tx_type='application_fee',
                    description=f"Vendor application fee for shop: {shop_name}",
                )
                vendor = VendorProfile.objects.create(
                    user=request.user,
                    shop_name=shop_name,
                    shop_description=shop_description,
                    application_fee_paid=True,
                )
                request.user.role = User.Role.VENDOR
                request.user.save(update_fields=['role'])
                messages.success(request,
                    f"Application submitted! Fee of {app_fee_coins} TP Coins deducted. "
                    f"Admin will review your application.")
                return redirect('vendors:dashboard')
            except ValueError as e:
                messages.error(request, str(e))

    return render(request, 'vendors/vendor_apply.html', {
        'app_fee_coins': app_fee_coins,
        'app_fee_usd': app_fee_usd,
        'user_coins': request.user.coin_balance,
        'can_afford': request.user.coin_balance >= app_fee_coins,
        'page_title': 'Become a Vendor',
    })


@login_required
def vendor_dashboard(request):
    if request.user.role not in ['vendor', 'vendor_staff']:
        return redirect('dashboard')
    try:
        vendor = request.user.vendor_profile
    except Exception:
        return redirect('vendors:apply')
    from apps.listings.models import Listing
    from apps.orders.models import Order
    listings     = vendor.listings.exclude(status='deleted').order_by('-created_at')[:10]
    recent_orders = Order.objects.filter(vendor=vendor).order_by('-created_at')[:5]
    rank_key, rank_label = request.user.vendor_rank
    return render(request, 'vendors/vendor_dashboard.html', {
        'vendor': vendor,
        'listings': listings,
        'recent_orders': recent_orders,
        'rank_key': rank_key,
        'rank_label': rank_label,
        'page_title': f'{vendor.shop_name} Dashboard',
    })


@login_required
def vendor_categories(request):
    if request.user.role not in ['vendor', 'vendor_staff']:
        return redirect('dashboard')

    try:
        vendor = request.user.vendor_profile
    except Exception:
        return redirect('vendors:apply')

    from apps.listings.models import ListingCategory

    categories = ListingCategory.objects.filter(
        vendor=vendor
    ).select_related('parent').order_by('sort_order', 'name')

    return render(request, 'vendors/vendor_categories.html', {
        'vendor': vendor,
        'categories': categories,
        'page_title': 'My Categories',
    })


@login_required
def vendor_category_create(request):
    if request.user.role not in ['vendor', 'vendor_staff']:
        return redirect('dashboard')

    try:
        vendor = request.user.vendor_profile
    except Exception:
        return redirect('vendors:apply')

    from .forms import VendorCategoryForm

    if request.method == 'POST':
        form = VendorCategoryForm(request.POST, vendor=vendor)
        if form.is_valid():
            category = form.save(commit=False)
            category.vendor = vendor
            category.save()
            messages.success(request, 'Category created successfully.')
            return redirect('vendors:categories')
    else:
        form = VendorCategoryForm(vendor=vendor)

    return render(request, 'vendors/vendor_category_form.html', {
        'form': form,
        'vendor': vendor,
        'page_title': 'Create Category',
    })


@login_required
def vendor_category_edit(request, category_id):
    if request.user.role not in ['vendor', 'vendor_staff']:
        return redirect('dashboard')

    try:
        vendor = request.user.vendor_profile
    except Exception:
        return redirect('vendors:apply')

    from apps.listings.models import ListingCategory
    from .forms import VendorCategoryForm

    category = get_object_or_404(ListingCategory, id=category_id, vendor=vendor)

    if request.method == 'POST':
        form = VendorCategoryForm(request.POST, instance=category, vendor=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('vendors:categories')
    else:
        form = VendorCategoryForm(instance=category, vendor=vendor)

    return render(request, 'vendors/vendor_category_form.html', {
        'form': form,
        'vendor': vendor,
        'category': category,
        'page_title': 'Edit Category',
    })


@login_required
def vendor_category_delete(request, category_id):
    if request.user.role not in ['vendor', 'vendor_staff']:
        return redirect('dashboard')

    try:
        vendor = request.user.vendor_profile
    except Exception:
        return redirect('vendors:apply')

    from apps.listings.models import ListingCategory

    category = get_object_or_404(ListingCategory, id=category_id, vendor=vendor)

    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted successfully.')

    return redirect('vendors:categories')

"""
ToasterPants — Permission Decorators
=========================================
Who can do what. Enforced at the view level.
No exceptions. No sneaking. Not even with a toaster. TP
"""

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponseForbidden
from .models import User


def role_required(*roles):
    """Decorator requiring one of the listed roles."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect(f'/accounts/login/?next={request.path}')
            if request.user.role not in roles:
                messages.error(request, "You don't have permission to access this page. ")
                return HttpResponseForbidden("Access Denied")
            if request.user.is_banned:
                messages.error(request, "Your account is suspended.")
                return redirect('/')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_required(view_func):
    """Admin or Super Admin only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if request.user.role not in [User.Role.SUPER_ADMIN, User.Role.ADMIN]:
            messages.error(request, "Admin access required. ")
            return HttpResponseForbidden("Access Denied")
        return view_func(request, *args, **kwargs)
    return wrapper


def superadmin_required(view_func):
    """Super Admin only — the top dog."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if request.user.role != User.Role.SUPER_ADMIN:
            messages.error(request, "Super Admin access required. You are NOT the chosen one. TP")
            return HttpResponseForbidden("Access Denied — Super Admin Only")
        return view_func(request, *args, **kwargs)
    return wrapper


def vendor_required(view_func):
    """Vendor or Vendor Staff only."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if request.user.role not in [User.Role.VENDOR, User.Role.VENDOR_STAFF, User.Role.SUPER_ADMIN, User.Role.ADMIN]:
            messages.error(request, "Vendor access required.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def support_required(view_func):
    """Support staff, admin, or super admin."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if request.user.role not in [User.Role.SUPPORT, User.Role.ADMIN, User.Role.SUPER_ADMIN]:
            return HttpResponseForbidden("Support Access Only")
        return view_func(request, *args, **kwargs)
    return wrapper


def buyer_required(view_func):
    """Buyers and resellers — purchasing power."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f'/accounts/login/?next={request.path}')
        if request.user.role not in [User.Role.BUYER, User.Role.RESELLER, User.Role.SUPER_ADMIN, User.Role.ADMIN]:
            return HttpResponseForbidden("Buyer Access Only")
        return view_func(request, *args, **kwargs)
    return wrapper

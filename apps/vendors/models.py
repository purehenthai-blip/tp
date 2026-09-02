"""
ToasterPants — Vendors App Models
===================================
Where vendor dreams go to be listed, sold, and slightly toasted. TP
"""

import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User


class VendorProfile(models.Model):
    """Extended profile for vendor users."""

    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending Review')
        APPROVED = 'approved', _('Approved')
        SUSPENDED = 'suspended', _('Suspended')
        REJECTED = 'rejected', _('Rejected')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='vendor_profile')
    shop_name = models.CharField(max_length=100, unique=True)
    shop_description = models.TextField(blank=True)
    shop_banner = models.ImageField(upload_to='vendors/banners/', null=True, blank=True)
    shop_logo = models.ImageField(upload_to='vendors/logos/', null=True, blank=True)
    listing_fee_paid = models.BooleanField(default=False)
    application_fee_paid = models.BooleanField(default=False)
    total_sales = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    staff_count = models.PositiveIntegerField(default=0)
    verified_status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    pgp_key = models.TextField(blank=True)
    admin_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Vendor Profile')

    def __str__(self):
        return f"Vendor: {self.shop_name} ({self.user.username})"

    @property
    def is_active(self):
        return self.verified_status == self.Status.APPROVED


class VendorStaff(models.Model):
    """
    Sub-accounts under a vendor.
    Requires admin approval. Cannot impersonate the vendor.
    """

    class Role(models.TextChoices):
        MANAGER = 'manager', _('Manager')
        FULFILLMENT = 'fulfillment', _('Fulfillment')
        SUPPORT = 'support', _('Support')
        READ_ONLY = 'read_only', _('Read Only')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    vendor = models.ForeignKey(VendorProfile, on_delete=models.CASCADE, related_name='staff_members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='staff_roles')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.READ_ONLY)
    permissions = models.JSONField(default=dict, help_text="Fine-grained permission flags")
    admin_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_staff'
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('vendor', 'user')

    def __str__(self):
        return f"{self.user.username} → {self.vendor.shop_name} ({self.role})"

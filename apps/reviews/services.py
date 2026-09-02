"""
ToasterPants — Reviews App
============================
Review models live in messaging.models for import simplicity.
This file exposes them cleanly.
"""

from apps.messaging.models import Review, VendorReview

__all__ = ['Review', 'VendorReview']


def recalculate_vendor_rating(vendor_profile):
    """Recalculate and save the average rating for a vendor."""
    from django.db.models import Avg
    result = Review.objects.filter(
        listing__vendor=vendor_profile,
        is_published=True,
        admin_removed=False
    ).aggregate(avg=Avg('rating'))

    avg = result['avg'] or 0
    count = Review.objects.filter(
        listing__vendor=vendor_profile,
        is_published=True,
        admin_removed=False
    ).count()

    vendor_profile.rating = round(avg, 2)
    vendor_profile.rating_count = count
    vendor_profile.save(update_fields=['rating', 'rating_count'])
    return avg

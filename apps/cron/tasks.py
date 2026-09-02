"""
ToasterPants — Cron / Celery Background Tasks
===============================================
The silent workers. Running 24/7. Keeping the marketplace tidy.
Auto-deleting, auto-releasing, auto-expiring. Like a very responsible toaster. TP⏰
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.db import transaction
from decimal import Decimal

logger = logging.getLogger('toasterpants')


@shared_task(name='apps.cron.tasks.delete_inactive_accounts')
def delete_inactive_accounts():
    """
    Auto-delete accounts that are:
    - Inactive for 14+ days AND
    - Have wallet balance < $15 AND
    - Are scheduled for deletion OR have no activity
    """
    from apps.accounts.models import User, DeletionQueue, AuditLog

    cutoff_date = timezone.now() - timezone.timedelta(days=14)
    min_balance = Decimal('15.00')
    deleted_count = 0

    # 1. Process DeletionQueue (user-requested + admin-scheduled)
    due_deletions = DeletionQueue.objects.filter(
        scheduled_time__lte=timezone.now()
    ).select_related('user')

    for deletion in due_deletions:
        user = deletion.user
        try:
            with transaction.atomic():
                logger.info(f"Auto-deleting user {user.username} (reason: {deletion.reason})")
                AuditLog.objects.create(
                    admin_user=None,
                    action=AuditLog.Action.DELETE,
                    target_model='User',
                    target_id=str(user.id),
                    description=f"Auto-deleted user {user.username} — reason: {deletion.reason}",
                )
                user.delete()
                deleted_count += 1
        except Exception as e:
            logger.error(f"Error deleting user {user.username}: {e}")

    # 2. Auto-delete inactive low-balance accounts (no user request needed)
    inactive_low_balance = User.objects.filter(
        last_active__lt=cutoff_date,
        wallet_balance__lt=min_balance,
        role__in=['buyer', 'reseller'],
        is_banned=False,
        deletion_queue__isnull=True,  # Not already in queue
    )

    for user in inactive_low_balance:
        try:
            with transaction.atomic():
                logger.info(f"Queueing auto-delete for inactive user {user.username}")
                DeletionQueue.objects.get_or_create(
                    user=user,
                    defaults={
                        'scheduled_time': timezone.now() + timezone.timedelta(days=3),
                        'reason': DeletionQueue.Reason.INACTIVE_LOW_BALANCE
                    }
                )
        except Exception as e:
            logger.error(f"Error queueing user {user.username}: {e}")

    logger.info(f"Account deletion task: {deleted_count} accounts deleted")
    return {'deleted': deleted_count}


@shared_task(name='apps.cron.tasks.expire_listings')
def expire_listings():
    """Mark expired listings as expired status."""
    from apps.listings.models import Listing

    now = timezone.now()
    expired = Listing.objects.filter(
        status=Listing.Status.ACTIVE,
        expiration__lte=now,
    )
    count = expired.count()
    expired.update(status=Listing.Status.EXPIRED)
    logger.info(f"Listing expiry task: {count} listings expired")
    return {'expired': count}


@shared_task(name='apps.cron.tasks.complete_ended_auctions')
def complete_ended_auctions():
    """
    Check for auctions that have ended and process winners.
    Anti-sniping extension is handled at bid time, but this task
    finalizes auctions that are genuinely over.
    """
    from apps.auctions.models import Auction, Bid
    from apps.orders.models import Order, Escrow
    from apps.wallet.services import lock_escrow_for_order
    from apps.accounts.models import AuditLog

    now = timezone.now()
    ended_auctions = Auction.objects.filter(
        status__in=[Auction.Status.ACTIVE, Auction.Status.EXTENDED],
        end_time__lte=now,
    ).select_related('listing', 'listing__vendor')

    processed = 0
    for auction in ended_auctions:
        try:
            with transaction.atomic():
                winning_bid = Bid.objects.filter(
                    auction=auction
                ).order_by('-bid_amount').first()

                if winning_bid:
                    # Check reserve price
                    if auction.reserve_price and winning_bid.bid_amount < auction.reserve_price:
                        auction.status = Auction.Status.CANCELLED
                        auction.save(update_fields=['status'])
                        logger.info(f"Auction {auction.id} cancelled — reserve not met")
                        continue

                    auction.winner = winning_bid.bidder
                    auction.status = Auction.Status.AWAITING_PAYMENT
                    auction.current_bid = winning_bid.bid_amount
                    auction.reserve_met = True
                    winning_bid.is_winning = True
                    winning_bid.save(update_fields=['is_winning'])
                    auction.save(update_fields=['winner', 'status', 'current_bid', 'reserve_met'])

                    # Mark all other bids as not winning
                    Bid.objects.filter(auction=auction).exclude(id=winning_bid.id).update(is_winning=False)

                    logger.info(f"Auction {auction.id} completed. Winner: {winning_bid.bidder.username}")
                else:
                    auction.status = Auction.Status.ENDED
                    auction.save(update_fields=['status'])
                    logger.info(f"Auction {auction.id} ended — no bids")

                processed += 1
        except Exception as e:
            logger.error(f"Error completing auction {auction.id}: {e}")

    return {'processed': processed}


@shared_task(name='apps.cron.tasks.auto_release_escrow')
def auto_release_escrow():
    """
    Auto-release escrow funds to vendors when release_time has passed
    and buyer hasn't verified or disputed.
    """
    from apps.orders.models import Escrow, Order
    from apps.accounts.models import AuditLog

    now = timezone.now()
    releasable = Escrow.objects.filter(
        status=Escrow.Status.LOCKED,
        release_time__lte=now,
        admin_confirmed=True,  # Only release if admin confirmed payment
    ).select_related('order', 'order__vendor', 'order__buyer')

    released_count = 0
    for escrow in releasable:
        try:
            with transaction.atomic():
                escrow.release_to_vendor()
                AuditLog.objects.create(
                    admin_user=None,
                    action=AuditLog.Action.ESCROW_OVERRIDE,
                    target_model='Escrow',
                    target_id=str(escrow.id),
                    description=f"Auto-released escrow for order #{escrow.order.order_number} — release time reached",
                )
                logger.info(f"Auto-released escrow {escrow.id} for order {escrow.order.order_number}")
                released_count += 1
        except Exception as e:
            logger.error(f"Error auto-releasing escrow {escrow.id}: {e}")

    return {'released': released_count}


@shared_task(name='apps.cron.tasks.daily_maintenance')
def daily_maintenance():
    """
    Daily cleanup and maintenance tasks:
    - Update vendor ratings
    - Recalculate reseller eligibility
    - Update listing view counts cache
    - Check for expired coupons
    """
    from apps.accounts.models import User
    from apps.vendors.models import VendorProfile
    from apps.listings.models import Coupon
    from apps.reviews.services import recalculate_vendor_rating

    # 1. Mark expired coupons as inactive
    Coupon.objects.filter(
        active=True,
        expiry_date__lt=timezone.now()
    ).update(active=False)

    # 2. Upgrade buyers to resellers if eligible
    eligible_buyers = User.objects.filter(
        role=User.Role.BUYER,
        purchase_total__gte=Decimal('100.00')
    )
    upgraded = eligible_buyers.update(role=User.Role.RESELLER)

    # 3. Recalculate vendor ratings
    for vendor in VendorProfile.objects.filter(verified_status='approved'):
        try:
            recalculate_vendor_rating(vendor)
        except Exception as e:
            logger.error(f"Error recalculating rating for vendor {vendor.id}: {e}")

    logger.info(f"Daily maintenance: {upgraded} buyers upgraded to resellers")
    return {'resellers_upgraded': upgraded}


@shared_task(name='apps.cron.tasks.send_delivery_notifications')
def send_delivery_notifications():
    """
    Notify buyers of pending deliveries that haven't been verified.
    Notify vendors of orders that are overdue.
    """
    from apps.orders.models import Order
    from apps.messaging.services import send_system_message

    # Orders delivered but not verified after 3 days
    cutoff = timezone.now() - timezone.timedelta(days=3)
    pending_verifications = Order.objects.filter(
        status=Order.Status.DELIVERED,
        delivery__delivered_at__lt=cutoff,
    ).select_related('buyer', 'listing')

    notified = 0
    for order in pending_verifications:
        try:
            send_system_message(
                user=order.buyer,
                subject=f"Reminder: Verify delivery for Order #{order.order_number}",
                content=f"Your order '{order.listing.title if order.listing else 'Unknown'}' "
                        f"was delivered 3+ days ago. Please verify delivery or "
                        f"open a dispute before escrow auto-releases."
            )
            notified += 1
        except Exception as e:
            logger.error(f"Error sending delivery notification for order {order.id}: {e}")

    return {'notified': notified}


@shared_task(name='apps.cron.tasks.cleanup_old_attachments')
def cleanup_old_attachments():
    """Remove orphaned message/ticket attachment files."""
    import os
    from apps.messaging.models import MessageAttachment
    from apps.support.models import TicketAttachment

    cleaned = 0
    # Find attachments for deleted messages
    for model in [MessageAttachment, TicketAttachment]:
        for att in model.objects.all():
            try:
                if att.file and not os.path.isfile(att.file.path):
                    att.delete()
                    cleaned += 1
            except Exception:
                pass

    return {'cleaned': cleaned}


@shared_task(name='apps.cron.tasks.manual_task_runner')
def manual_task_runner(task_name):
    """
    Admin-triggered manual task execution.
    Because sometimes you don't want to wait for the scheduler.
    """
    task_map = {
        'delete_inactive_accounts': delete_inactive_accounts,
        'expire_listings': expire_listings,
        'complete_ended_auctions': complete_ended_auctions,
        'auto_release_escrow': auto_release_escrow,
        'daily_maintenance': daily_maintenance,
        'send_delivery_notifications': send_delivery_notifications,
        'cleanup_old_attachments': cleanup_old_attachments,
    }
    if task_name in task_map:
        return task_map[task_name].apply_async()
    raise ValueError(f"Unknown task: {task_name}")

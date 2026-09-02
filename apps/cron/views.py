from django.shortcuts import render, redirect
from django.contrib import messages
from apps.accounts.decorators import admin_required

CRON_TASKS = [
    {'name': 'Delete Inactive Accounts', 'icon': '️', 'task_name': 'delete_inactive_accounts',
     'description': 'Removes inactive accounts with balance < $15 after 14 days', 'schedule': 'Daily @ 2:00 AM'},
    {'name': 'Expire Listings', 'icon': '', 'task_name': 'expire_listings',
     'description': 'Marks expired listings as expired', 'schedule': 'Every hour'},
    {'name': 'Complete Auctions', 'icon': '', 'task_name': 'complete_ended_auctions',
     'description': 'Finalises ended auctions and sets winners', 'schedule': 'Every minute'},
    {'name': 'Auto-Release Escrow', 'icon': '', 'task_name': 'auto_release_escrow',
     'description': 'Releases escrow funds when release time has passed', 'schedule': 'Every 30 mins'},
    {'name': 'Daily Maintenance', 'icon': '️', 'task_name': 'daily_maintenance',
     'description': 'Upgrades resellers, recalculates ratings, expires coupons', 'schedule': 'Daily @ 3:00 AM'},
    {'name': 'Delivery Notifications', 'icon': '', 'task_name': 'send_delivery_notifications',
     'description': 'Reminds buyers to verify deliveries', 'schedule': 'Every 6 hours'},
    {'name': 'Cleanup Attachments', 'icon': '', 'task_name': 'cleanup_old_attachments',
     'description': 'Removes orphaned file attachments', 'schedule': 'Weekly (Sunday 4 AM)'},
]

@admin_required
def cron_dashboard(request):
    if request.method == 'POST':
        task_name = request.POST.get('task')
        try:
            from apps.cron.tasks import manual_task_runner
            manual_task_runner.delay(task_name)
            messages.success(request, f"Task '{task_name}' queued.")
        except Exception as e:
            messages.error(request, f"Failed: {e}")
        return redirect('admin_panel:cron')
    return render(request, 'admin_panel/cron_jobs.html', {'tasks': CRON_TASKS, 'page_title': 'Cron Jobs'})

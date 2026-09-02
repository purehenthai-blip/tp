from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.orders.models import Escrow, Order
from apps.accounts.decorators import admin_required

@login_required
def escrow_list(request):
    if request.user.role in ['admin', 'super_admin']:
        escrows = Escrow.objects.all().select_related('order').order_by('-locked_at')
    else:
        escrows = Escrow.objects.filter(order__buyer=request.user).select_related('order')
    return render(request, 'escrow/escrow_list.html', {'escrows': escrows, 'page_title': 'Escrow'})

@login_required
def escrow_detail(request, escrow_id):
    if request.user.role in ['admin', 'super_admin']:
        escrow = get_object_or_404(Escrow, id=escrow_id)
    else:
        escrow = get_object_or_404(Escrow, id=escrow_id, order__buyer=request.user)
    return render(request, 'escrow/escrow_detail.html', {'escrow': escrow})

@admin_required
def release_escrow(request, escrow_id):
    escrow = get_object_or_404(Escrow, id=escrow_id)
    if request.method == 'POST':
        from apps.accounts.models import AuditLog
        escrow.release_to_vendor(admin_user=request.user)
        AuditLog.objects.create(admin_user=request.user, action=AuditLog.Action.ESCROW_OVERRIDE,
            target_model='Escrow', target_id=str(escrow_id),
            description=f"Admin released escrow #{escrow_id}")
        messages.success(request, "Escrow released to vendor.")
    return redirect('admin_panel:dashboard')

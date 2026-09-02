from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import MessageThread, Message, MessageAttachment, Ticket, TicketMessage

@login_required
def inbox(request):
    threads = MessageThread.objects.filter(participants=request.user).prefetch_related('messages').order_by('-updated_at')
    active_thread = None
    thread_id = request.GET.get('thread')
    if thread_id:
        try:
            active_thread = threads.get(id=thread_id)
            active_thread.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        except MessageThread.DoesNotExist:
            pass
    return render(request, 'messaging/inbox.html', {'threads': threads, 'active_thread': active_thread, 'page_title': 'Messages'})

@login_required
def thread_detail(request, thread_id):
    thread = get_object_or_404(MessageThread, id=thread_id, participants=request.user)
    thread.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    return redirect(f'/messages/?thread={thread_id}')

@login_required
def send_message(request, thread_id):
    if request.method != 'POST':
        return redirect('messaging:inbox')
    thread = get_object_or_404(MessageThread, id=thread_id, participants=request.user)
    content = request.POST.get('content', '').strip()
    if not content:
        messages.error(request, "Message cannot be empty.")
        return redirect(f'/messages/?thread={thread_id}')
    msg = Message.objects.create(thread=thread, sender=request.user, content=content)
    attachment = request.FILES.get('attachment')
    if attachment:
        if attachment.size <= 20 * 1024 * 1024:
            MessageAttachment.objects.create(
                message=msg, file=attachment,
                original_filename=attachment.name, file_size=attachment.size
            )
    from django.utils import timezone
    MessageThread.objects.filter(pk=thread.pk).update(updated_at=timezone.now())
    return redirect(f'/messages/?thread={thread_id}')

@login_required
def new_thread(request):
    if request.method == 'POST':
        from apps.accounts.models import User
        recipient_username = request.POST.get('recipient', '').strip()
        subject = request.POST.get('subject', '').strip()
        content = request.POST.get('content', '').strip()
        try:
            recipient = User.objects.get(username=recipient_username)
        except User.DoesNotExist:
            messages.error(request, f"User '{recipient_username}' not found.")
            return redirect('messaging:inbox')
        thread = MessageThread.objects.create(subject=subject)
        thread.participants.add(request.user, recipient)
        if content:
            Message.objects.create(thread=thread, sender=request.user, content=content)
        return redirect(f'/messages/?thread={thread.id}')
    return redirect('messaging:inbox')

@login_required
def ticket_list(request):
    user_tickets = Ticket.objects.filter(user=request.user).order_by('-created_at')
    paginator = Paginator(user_tickets, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'support/ticket_list.html', {'tickets': page, 'page_title': 'My Support Tickets'})

@login_required
def new_ticket(request):
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        category = request.POST.get('category', 'other')
        priority = request.POST.get('priority', 'medium')
        content = request.POST.get('content', '').strip()
        if not subject or not content:
            messages.error(request, "Subject and message are required.")
            return redirect('support:new')
        ticket = Ticket.objects.create(user=request.user, subject=subject, category=category, priority=priority)
        TicketMessage.objects.create(ticket=ticket, sender=request.user, content=content)
        messages.success(request, f"Ticket #{ticket.ticket_number} created!")
        return redirect('support:detail', ticket_id=ticket.id)
    return render(request, 'support/new_ticket.html', {'categories': Ticket.Category.choices, 'priorities': Ticket.Priority.choices, 'page_title': 'New Support Ticket'})

@login_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id, user=request.user)
    ticket_messages = ticket.messages.all()
    return render(request, 'support/ticket_detail.html', {'ticket': ticket, 'ticket_messages': ticket_messages, 'page_title': f'Ticket #{ticket.ticket_number}'})

@login_required
def reply_ticket(request, ticket_id):
    ticket = get_object_or_404(Ticket, id=ticket_id)
    if ticket.user != request.user and request.user.role not in ['admin', 'super_admin', 'support']:
        messages.error(request, "Access denied.")
        return redirect('support:list')
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            TicketMessage.objects.create(ticket=ticket, sender=request.user, content=content)
            from django.utils import timezone
            ticket.updated_at = timezone.now()
            if ticket.status == 'open':
                ticket.status = 'in_progress'
            ticket.save(update_fields=['updated_at', 'status'])
    return redirect('support:detail', ticket_id=ticket_id)

@login_required
def support_dashboard(request):
    from apps.accounts.decorators import support_required
    if request.user.role not in ['admin', 'super_admin', 'support']:
        return redirect('/')
    open_tickets = Ticket.objects.filter(status__in=['open', 'in_progress']).order_by('-priority', '-created_at')
    return render(request, 'support/support_dashboard.html', {'tickets': open_tickets[:50], 'page_title': 'Support Dashboard'})

def faq(request):
    return render(request, 'support/faq.html', {'page_title': 'FAQ'})

def escrow_guide(request):
    return render(request, 'support/escrow_guide.html', {'page_title': 'Escrow Guide'})

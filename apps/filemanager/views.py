from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import ManagedFile, FileFolder, UserStorageQuota

@login_required
def file_manager(request):
    folder_id = request.GET.get('folder')
    current_folder = None
    if folder_id:
        current_folder = get_object_or_404(FileFolder, id=folder_id, owner=request.user)
    files = ManagedFile.objects.filter(owner=request.user, folder=current_folder).order_by('-uploaded_at')
    folders = FileFolder.objects.filter(owner=request.user, parent=current_folder)
    quota, _ = UserStorageQuota.objects.get_or_create(user=request.user)
    all_folders = FileFolder.objects.filter(owner=request.user)
    breadcrumb = []
    if current_folder:
        f = current_folder
        while f:
            breadcrumb.insert(0, f)
            f = f.parent
    return render(request, 'filemanager/file_manager.html', {
        'files': files, 'folders': folders, 'current_folder': current_folder,
        'quota': quota, 'all_folders': all_folders, 'breadcrumb': breadcrumb,
        'page_title': 'File Manager',
    })

@login_required
def upload_file(request):
    if request.method != 'POST':
        return redirect('filemanager:home')
    uploaded = request.FILES.get('file')
    if not uploaded:
        messages.error(request, "No file selected.")
        return redirect('filemanager:home')
    if uploaded.size > settings.FILE_UPLOAD_MAX_MEMORY_SIZE:
        messages.error(request, f"File too large. Max {settings.FILE_UPLOAD_MAX_MEMORY_SIZE // 1024 // 1024}MB.")
        return redirect('filemanager:home')
    quota, _ = UserStorageQuota.objects.get_or_create(user=request.user)
    if quota.used_bytes + uploaded.size > quota.max_bytes:
        messages.error(request, f"Storage quota exceeded ({quota.max_bytes // 1024 // 1024}MB max).")
        return redirect('filemanager:home')
    folder_id = request.POST.get('folder')
    folder = None
    if folder_id:
        try:
            folder = FileFolder.objects.get(id=folder_id, owner=request.user)
        except FileFolder.DoesNotExist:
            pass
    import mimetypes
    mime_type, _ = mimetypes.guess_type(uploaded.name)
    file_type = 'other'
    if mime_type:
        if mime_type.startswith('image/'): file_type = 'image'
        elif mime_type.startswith('video/'): file_type = 'video'
        elif mime_type.startswith('audio/'): file_type = 'audio'
        elif mime_type in ['application/zip', 'application/x-rar-compressed', 'application/x-tar']: file_type = 'archive'
        elif 'document' in mime_type or mime_type == 'application/pdf': file_type = 'document'
    ManagedFile.objects.create(
        owner=request.user, file=uploaded, filename=uploaded.name,
        original_filename=uploaded.name, file_type=file_type,
        file_size=uploaded.size, mime_type=mime_type or '', folder=folder
    )
    quota.used_bytes += uploaded.size
    quota.save(update_fields=['used_bytes'])
    messages.success(request, f"'{uploaded.name}' uploaded!")
    return redirect('filemanager:home')

@login_required
def download_file(request, file_id):
    f = get_object_or_404(ManagedFile, id=file_id, owner=request.user)
    return FileResponse(f.file.open(), as_attachment=True, filename=f.filename)

@login_required
@require_POST
def delete_file(request, file_id):
    f = get_object_or_404(ManagedFile, id=file_id, owner=request.user)
    quota, _ = UserStorageQuota.objects.get_or_create(user=request.user)
    quota.used_bytes = max(0, quota.used_bytes - f.file_size)
    quota.save(update_fields=['used_bytes'])
    f.delete()
    return JsonResponse({'status': 'ok'})

@login_required
@require_POST
def rename_file(request, file_id):
    f = get_object_or_404(ManagedFile, id=file_id, owner=request.user)
    new_name = request.POST.get('name', '').strip()
    if new_name:
        f.filename = new_name
        f.save(update_fields=['filename'])
    return JsonResponse({'status': 'ok'})

@login_required
def create_folder(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if name:
            FileFolder.objects.create(owner=request.user, name=name)
    return redirect('filemanager:home')

@login_required
@require_POST
def delete_folder(request, folder_id):
    folder = get_object_or_404(FileFolder, id=folder_id, owner=request.user)
    folder.delete()
    return JsonResponse({'status': 'ok'})

@login_required
@require_POST
def rename_folder(request, folder_id):
    folder = get_object_or_404(FileFolder, id=folder_id, owner=request.user)
    new_name = request.POST.get('name', '').strip()
    if new_name:
        folder.name = new_name
        folder.save(update_fields=['name'])
    return JsonResponse({'status': 'ok'})

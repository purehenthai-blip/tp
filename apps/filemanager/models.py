"""
ToasterPants — File Manager Models
=====================================
Upload it. Rename it. Delete it.
Windows-style file browser energy. In a browser. Because why not. TP
"""

import uuid
import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from apps.accounts.models import User


def managed_file_path(instance, filename):
    return f"filemanager/{instance.owner.id}/{filename}"


class ManagedFile(models.Model):
    """
    User-uploaded files via the file manager.
    Max 20MB per file. Max 100MB per user total.
    Admin can view / delete any file.
    """

    class FileType(models.TextChoices):
        DOCUMENT = 'document', _('Document')
        IMAGE = 'image', _('Image')
        ARCHIVE = 'archive', _('Archive')
        VIDEO = 'video', _('Video')
        AUDIO = 'audio', _('Audio')
        OTHER = 'other', _('Other')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_files')
    file = models.FileField(upload_to=managed_file_path)
    filename = models.CharField(max_length=255)          # Display name (renameable)
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FileType.choices, default=FileType.OTHER)
    file_size = models.PositiveBigIntegerField(help_text="Bytes")
    mime_type = models.CharField(max_length=100, blank=True)
    folder = models.ForeignKey('FileFolder', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='files')
    is_linked_to_listing = models.BooleanField(default=False)
    description = models.CharField(max_length=500, blank=True)
    is_flagged = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['owner', '-uploaded_at']),
        ]

    def __str__(self):
        return f"{self.filename} ({self.owner.username})"

    def delete(self, *args, **kwargs):
        if self.file and os.path.isfile(self.file.path):
            os.remove(self.file.path)
        super().delete(*args, **kwargs)


class FileFolder(models.Model):
    """Virtual folders for organizing files — Windows Explorer vibes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='file_folders')
    name = models.CharField(max_length=200)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                               related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('owner', 'name', 'parent')

    def __str__(self):
        return f" {self.name} ({self.owner.username})"


class UserStorageQuota(models.Model):
    """Tracks total storage usage per user."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='storage_quota')
    used_bytes = models.PositiveBigIntegerField(default=0)
    max_bytes = models.PositiveBigIntegerField(default=100 * 1024 * 1024)  # 100MB default

    def __str__(self):
        return f"{self.user.username}: {self.used_bytes / 1024 / 1024:.1f}MB / {self.max_bytes / 1024 / 1024:.0f}MB"

    @property
    def remaining_bytes(self):
        return max(0, self.max_bytes - self.used_bytes)

    @property
    def is_full(self):
        return self.used_bytes >= self.max_bytes

    @property
    def usage_percent(self):
        return min(100, (self.used_bytes / self.max_bytes) * 100)

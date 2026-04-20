from uuid import uuid4

from django.db import models

from .uploads import (
    avatar_upload_to,
    document_upload_to,
    validate_avatar_upload,
    validate_document_upload,
)


def _delete_file(storage, file_name):
    if file_name:
        storage.delete(file_name)


class Submission(models.Model):
    public_id = models.UUIDField(default=uuid4, editable=False, unique=True)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField(max_length=2000)
    avatar = models.FileField(
        upload_to=avatar_upload_to,
        blank=True,
        validators=[validate_avatar_upload],
        help_text="PNG, JPEG, GIF, or WEBP only. Maximum size: 2 MB.",
    )
    document = models.FileField(
        upload_to=document_upload_to,
        blank=True,
        validators=[validate_document_upload],
        help_text="PDF only. Maximum size: 5 MB.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "Submission"
        verbose_name_plural = "Submissions"

    def __str__(self):
        return f"{self.name} <{self.email}>"

    def save(self, *args, **kwargs):
        previous_avatar = None
        previous_document = None

        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("avatar", "document").first()
            if previous:
                previous_avatar = previous["avatar"]
                previous_document = previous["document"]

        super().save(*args, **kwargs)

        current_avatar = self.avatar.name if self.avatar else None
        current_document = self.document.name if self.document else None

        if previous_avatar and previous_avatar != current_avatar:
            _delete_file(self.avatar.storage, previous_avatar)

        if previous_document and previous_document != current_document:
            _delete_file(self.document.storage, previous_document)

    def delete(self, *args, **kwargs):
        avatar_name = self.avatar.name if self.avatar else None
        document_name = self.document.name if self.document else None
        avatar_storage = self.avatar.storage
        document_storage = self.document.storage

        super().delete(*args, **kwargs)

        _delete_file(avatar_storage, avatar_name)
        _delete_file(document_storage, document_name)

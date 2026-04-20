"""
charles/signals.py

Signal handlers for automatic profile creation.
When a new User is created, automatically create an associated Profile.

Docs: https://docs.djangoproject.com/en/5.2/topics/signals/
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Profile


def _delete_profile_file(storage, file_name):
    if file_name:
        storage.delete(file_name)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Create a Profile whenever a new User is created.
    """
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Save the Profile whenever the User is saved.
    """
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(pre_save, sender=Profile)
def capture_previous_profile_files(sender, instance, **kwargs):
    """Remember the old file names so we can remove replaced uploads."""
    if not instance.pk:
        instance._previous_avatar_name = None
        instance._previous_document_name = None
        return

    previous = sender.objects.filter(pk=instance.pk).values("avatar", "document").first()
    if previous:
        instance._previous_avatar_name = previous["avatar"]
        instance._previous_document_name = previous["document"]
    else:
        instance._previous_avatar_name = None
        instance._previous_document_name = None


@receiver(post_save, sender=Profile)
def delete_replaced_profile_files(sender, instance, created, **kwargs):
    """Delete old avatar/document files once a replacement has been saved."""
    if created:
        return

    previous_avatar = getattr(instance, "_previous_avatar_name", None)
    previous_document = getattr(instance, "_previous_document_name", None)

    current_avatar = instance.avatar.name if instance.avatar else None
    current_document = instance.document.name if instance.document else None

    if previous_avatar and previous_avatar != current_avatar:
        _delete_profile_file(instance.avatar.storage, previous_avatar)

    if previous_document and previous_document != current_document:
        _delete_profile_file(instance.document.storage, previous_document)


@receiver(post_delete, sender=Profile)
def delete_profile_files_on_delete(sender, instance, **kwargs):
    """Remove uploaded files when a profile is deleted."""
    if instance.avatar:
        _delete_profile_file(instance.avatar.storage, instance.avatar.name)
    if instance.document:
        _delete_profile_file(instance.document.storage, instance.document.name)

"""
charles/signals.py

Signal handlers for automatic profile creation.
When a new User is created, automatically create an associated Profile.

Docs: https://docs.djangoproject.com/en/5.2/topics/signals/
"""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


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

"""
charles/admin.py

Register Profile model with Django admin for staff to manage user profiles.
"""

from django.contrib import admin

from .models import LoginAttempt, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for user profiles.
    """
    list_display = ('user', 'bio')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user',)


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin interface for reviewing account lockouts."""

    list_display = ("username", "failed_count", "last_failed_at", "locked_until")
    search_fields = ("username",)
    readonly_fields = ("username", "failed_count", "last_failed_at", "locked_until")

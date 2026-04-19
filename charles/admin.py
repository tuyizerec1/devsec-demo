"""
charles/admin.py

Register Profile model with Django admin for staff to manage user profiles.
"""

from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for user profiles.
    """
    list_display = ('user', 'bio')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user',)

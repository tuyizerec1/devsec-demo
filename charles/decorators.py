"""
charles/decorators.py

View decorators for role-based access control.

These sit one level above authentication — they assume the user is logged in
and additionally verify that the logged-in user belongs to a privileged role.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def instructor_required(view_func):
    """Allow access only to instructor, staff, or superuser accounts."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not (
            request.user.groups.filter(name="instructor").exists()
            or request.user.is_staff
            or request.user.is_superuser
        ):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return login_required(_wrapped)

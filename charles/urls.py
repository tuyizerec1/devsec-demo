"""
charles/urls.py

URL patterns for the charles authentication app.

app_name sets the application namespace. This means every reverse lookup
must be prefixed:  reverse('charles:login')  or  {% url 'charles:login' %}.
Namespacing prevents collisions if other apps define views with the same names.

Docs: https://docs.djangoproject.com/en/5.2/topics/http/urls/#url-namespaces
"""

from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "charles"

urlpatterns = [
    # --- Public ---
    path("register/", views.register, name="register"),
    path("login/", views.user_login, name="login"),

    # --- Password reset (public — user is locked out and cannot authenticate) ---
    # Django's built-in views handle token generation, validation, and expiry.
    # We only supply templates and the success redirect URLs.
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="charles/password_reset_request.html",
            email_template_name="charles/email/password_reset_email.txt",
            subject_template_name="charles/email/password_reset_subject.txt",
            success_url=reverse_lazy("charles:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="charles/password_reset_done.html",
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="charles/password_reset_confirm.html",
            success_url=reverse_lazy("charles:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="charles/password_reset_complete.html",
        ),
        name="password_reset_complete",
    ),

    # --- Protected ---
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("password-change/", views.password_change, name="password_change"),
    path("logout/", views.user_logout, name="logout"),
]

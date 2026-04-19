"""
charles/views.py — authentication lifecycle views.
Docs: https://docs.djangoproject.com/en/5.2/topics/auth/default/
"""

import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, ProfileUpdateForm, RegistrationForm
from .models import LoginAttempt, Profile


LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def register(request):
    if request.user.is_authenticated:
        return redirect("charles:dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account is ready.")
            return redirect("charles:dashboard")
    else:
        form = RegistrationForm()

    return render(request, "charles/register.html", {"form": form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect("charles:dashboard")

    if request.method == "POST":
        raw_username = request.POST.get("username", "").strip()
        attempt_key = raw_username.lower()
        attempt, _ = LoginAttempt.objects.get_or_create(username=attempt_key)
        now = timezone.now()

        if attempt.locked_until and attempt.locked_until > now:
            remaining = max(1, round((attempt.locked_until - now).total_seconds() / 60))
            messages.error(
                request,
                f"Too many failed login attempts. Please wait {remaining} minute(s) before trying again.",
            )
            return render(request, "charles/login.html", {
                "form": LoginForm(),
                "next": request.POST.get("next", ""),
            })

        if attempt.locked_until and attempt.locked_until <= now:
            attempt.failed_count = 0
            attempt.last_failed_at = None
            attempt.locked_until = None
            attempt.save(update_fields=["failed_count", "last_failed_at", "locked_until"])

        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            attempt.delete()

            # Open-redirect guard: validate ?next= before following it.
            # Without this check an attacker could craft a link that sends
            # the victim to an external site after a successful login.
            # Docs: https://docs.djangoproject.com/en/5.2/ref/utils/#django.utils.http.url_has_allowed_host_and_scheme
            next_url = request.POST.get("next") or request.GET.get("next", "")
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return HttpResponseRedirect(next_url)

            return redirect("charles:dashboard")
        else:
            attempt.failed_count += 1
            attempt.last_failed_at = now
            if attempt.failed_count >= LOCKOUT_THRESHOLD:
                attempt.locked_until = now + LOCKOUT_DURATION
            attempt.save()

    else:
        form = LoginForm()

    return render(request, "charles/login.html", {
        "form": form,
        "next": request.GET.get("next", ""),
    })


@login_required
def dashboard(request):
    return render(request, "charles/dashboard.html")


@login_required
def profile(request):
    # get_or_create is a safety net for users created outside the registration
    # form (e.g. via django admin or fixtures) who may not have a Profile yet.
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("charles:profile")
    else:
        form = ProfileUpdateForm(instance=profile_obj)

    return render(request, "charles/profile.html", {"form": form})


@login_required
@require_POST
def update_profile_bio(request):
    """
    Secure AJAX endpoint for profile bio updates.

    This view intentionally relies on Django's normal CSRF middleware rather
    than exemption shortcuts. The browser must send the CSRF token in the
    X-CSRFToken header for the update to succeed.
    """

    profile_obj, _ = Profile.objects.get_or_create(user=request.user)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"ok": False, "errors": {"__all__": ["Invalid JSON payload."]}},
            status=400,
        )

    form = ProfileUpdateForm(payload, instance=profile_obj)
    if form.is_valid():
        profile = form.save()
        return JsonResponse(
            {
                "ok": True,
                "bio": profile.bio,
                "message": "Your profile has been updated.",
            }
        )

    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


@login_required
def password_change(request):
    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            # update_session_auth_hash keeps the current session alive after
            # the password hash rotates, so the user is not signed out here.
            # Docs: https://docs.djangoproject.com/en/5.2/topics/auth/default/#django.contrib.auth.update_session_auth_hash
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been changed successfully.")
            return redirect("charles:dashboard")
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, "charles/password_change.html", {"form": form})


@login_required
def user_logout(request):
    # POST-only logout prevents a CSRF-style attack where an attacker embeds
    # the logout URL in an <img> tag and silently signs the victim out.
    if request.method == "POST":
        logout(request)
        messages.info(request, "You have been signed out. See you next time!")
        return redirect("charles:login")

    return render(request, "charles/logout_confirm.html")

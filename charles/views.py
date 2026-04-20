"""
charles/views.py — authentication lifecycle views.
Docs: https://docs.djangoproject.com/en/5.2/topics/auth/default/
"""

import json
import mimetypes
from datetime import timedelta
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import LoginForm, ProfileAssetForm, ProfileUpdateForm, RegistrationForm
from .models import LoginAttempt, Profile


LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def _guess_upload_content_type(file_name):
    content_type, _ = mimetypes.guess_type(file_name)
    if content_type:
        return content_type

    extension = Path(file_name).suffix.lower()
    if extension == ".webp":
        return "image/webp"
    if extension == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _serve_profile_file(uploaded_file, attachment=False):
    if not uploaded_file or not uploaded_file.name or not uploaded_file.storage.exists(uploaded_file.name):
        raise Http404

    file_handle = uploaded_file.open("rb")
    response = FileResponse(file_handle, content_type=_guess_upload_content_type(uploaded_file.name))
    disposition = "attachment" if attachment else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{Path(uploaded_file.name).name}"'
    response["X-Content-Type-Options"] = "nosniff"
    return response


def get_safe_next_url(request):
    """Return a same-origin next= destination or an empty string."""

    next_url = request.POST.get("next") or request.GET.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return ""


def register(request):
    next_url = get_safe_next_url(request)

    if request.user.is_authenticated:
        if next_url:
            return HttpResponseRedirect(next_url)
        return redirect("charles:dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account is ready.")
            if next_url:
                return HttpResponseRedirect(next_url)
            return redirect("charles:dashboard")
    else:
        form = RegistrationForm()

    return render(request, "charles/register.html", {"form": form, "next": next_url})


def user_login(request):
    next_url = get_safe_next_url(request)

    if request.user.is_authenticated:
        if next_url:
            return HttpResponseRedirect(next_url)
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
                "next": next_url,
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

            # Only same-origin redirect targets are ever followed.
            if next_url:
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
        "next": next_url,
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
        if request.FILES or request.POST.get("upload_assets"):
            asset_form = ProfileAssetForm(request.POST, request.FILES, instance=profile_obj)
            form = ProfileUpdateForm(instance=profile_obj)
            if asset_form.is_valid():
                asset_form.save()
                messages.success(request, "Your profile files have been updated.")
                return redirect("charles:profile")
        else:
            form = ProfileUpdateForm(request.POST, instance=profile_obj)
            asset_form = ProfileAssetForm(instance=profile_obj)
            if form.is_valid():
                form.save()
                messages.success(request, "Your profile has been updated.")
                return redirect("charles:profile")
    else:
        form = ProfileUpdateForm(instance=profile_obj)
        asset_form = ProfileAssetForm(instance=profile_obj)

    return render(request, "charles/profile.html", {"form": form, "asset_form": asset_form, "profile": profile_obj})


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
                "message": "Your profile has been updated.",
            }
        )

    return JsonResponse({"ok": False, "errors": form.errors}, status=400)


@login_required
def profile_avatar(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    return _serve_profile_file(profile_obj.avatar, attachment=False)


@login_required
def profile_document(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    return _serve_profile_file(profile_obj.document, attachment=True)


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

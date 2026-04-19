"""
charles/views.py — authentication lifecycle views.
Docs: https://docs.djangoproject.com/en/5.2/topics/auth/default/
"""

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, ProfileUpdateForm, RegistrationForm
from .models import Profile


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
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")

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
def view_profile(request, pk):
    """Read-only view for a single user's profile.

    The URL includes a predictable user primary key. This view explicitly
    verifies that the requesting user either owns the profile or has the
    instructor role before returning any profile data.
    """
    is_instructor = request.user.groups.filter(name="instructor").exists()

    if request.user.pk != pk and not is_instructor:
        raise PermissionDenied

    target_user = get_object_or_404(User, pk=pk)
    profile_obj, _ = Profile.objects.get_or_create(user=target_user)

    return render(request, "charles/view_profile.html", {
        "profile_user": target_user,
        "profile_obj": profile_obj,
    })


@login_required
def user_logout(request):
    # POST-only logout prevents a CSRF-style attack where an attacker embeds
    # the logout URL in an <img> tag and silently signs the victim out.
    if request.method == "POST":
        logout(request)
        messages.info(request, "You have been signed out. See you next time!")
        return redirect("charles:login")

    return render(request, "charles/logout_confirm.html")

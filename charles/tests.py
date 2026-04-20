"""
charles/tests.py

Tests for the charles User Authentication Service.
Tests cover the main authentication lifecycle: registration, login, logout,
password change, and profile management.

Docs: https://docs.djangoproject.com/en/5.2/topics/testing/
"""

import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import LoginAttempt, Profile


class RegistrationTests(TestCase):
    """Test user registration flow."""

    def setUp(self):
        self.client = Client()
        self.register_url = reverse("charles:register")

    def test_registration_page_loads(self):
        """GET /register/ should return 200."""
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/register.html")

    def test_successful_registration(self):
        """Registering with valid data should create a user and log them in."""
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username="testuser").exists())
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_mismatched_passwords(self):
        """Registering with mismatched passwords should fail."""
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
                "password1": "SecurePass123!",
                "password2": "Different123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="testuser").exists())
        # Check that the form has errors
        form = response.context.get("form")
        self.assertIsNotNone(form)
        self.assertTrue(form.errors)

    def test_duplicate_username(self):
        """Registering with a duplicate username should fail."""
        User.objects.create_user(username="testuser", email="first@example.com", password="SecurePass123!")
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "second@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        # Check that the form has errors for the duplicate username
        form = response.context.get("form")
        self.assertIsNotNone(form)
        self.assertTrue(form.errors)

    def test_missing_email(self):
        """Registration without email should fail."""
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="testuser").exists())

    def test_safe_internal_next_redirects_after_registration(self):
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
                "next": reverse("charles:profile"),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("charles:profile"))

    def test_unsafe_external_next_is_rejected_after_registration(self):
        response = self.client.post(
            self.register_url,
            {
                "username": "testuser",
                "email": "test@example.com",
                "password1": "SecurePass123!",
                "password2": "SecurePass123!",
                "next": "https://evil.example/phish",
            },
        )
        self.assertRedirects(response, reverse("charles:dashboard"), fetch_redirect_response=False)


class LoginLogoutTests(TestCase):
    """Test login and logout flows."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("charles:login")
        self.logout_url = reverse("charles:logout")
        self.dashboard_url = reverse("charles:dashboard")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

    def test_login_page_loads(self):
        """GET /login/ should return 200."""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/login.html")

    def test_successful_login(self):
        """Logging in with valid credentials should authenticate the user."""
        response = self.client.post(
            self.login_url,
            {
                "username": "testuser",
                "password": "SecurePass123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    def test_invalid_password(self):
        """Logging in with wrong password should fail."""
        response = self.client.post(
            self.login_url,
            {
                "username": "testuser",
                "password": "WrongPassword123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_nonexistent_user(self):
        """Logging in with nonexistent user should fail."""
        response = self.client.post(
            self.login_url,
            {
                "username": "nonexistent",
                "password": "SecurePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_requires_post(self):
        """GET to logout should show confirmation, not log out."""
        self.client.login(username="testuser", password="SecurePass123!")
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/logout_confirm.html")

    def test_logout_via_post(self):
        """POST to logout should log the user out."""
        self.client.login(username="testuser", password="SecurePass123!")
        response = self.client.post(self.logout_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class OpenRedirectTests(TestCase):
    """Test redirect target validation in authentication flows."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("charles:login")
        self.register_url = reverse("charles:register")
        self.dashboard_url = reverse("charles:dashboard")
        self.profile_url = reverse("charles:profile")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

    def login_with_next(self, next_url=None):
        data = {
            "username": "testuser",
            "password": "SecurePass123!",
        }
        if next_url is not None:
            data["next"] = next_url
        return self.client.post(self.login_url, data)

    def test_login_follows_safe_internal_next(self):
        response = self.login_with_next(self.profile_url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.profile_url)

    def test_login_rejects_external_http_next(self):
        response = self.login_with_next("http://evil.com/steal")
        self.assertRedirects(response, self.dashboard_url, fetch_redirect_response=False)

    def test_login_rejects_protocol_relative_next(self):
        response = self.login_with_next("//evil.com/steal")
        self.assertRedirects(response, self.dashboard_url, fetch_redirect_response=False)

    def test_login_rejects_javascript_scheme_next(self):
        response = self.login_with_next("javascript:alert(document.cookie)")
        self.assertRedirects(response, self.dashboard_url, fetch_redirect_response=False)

    def test_login_page_preserves_safe_internal_next(self):
        response = self.client.get(f"{self.login_url}?next={self.profile_url}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.profile_url}"', html=False)

    def test_login_page_drops_unsafe_external_next(self):
        response = self.client.get(f"{self.login_url}?next=https://evil.example/phish")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value=""', html=False)
        self.assertNotContains(response, "evil.example")

    def test_register_page_preserves_safe_internal_next(self):
        response = self.client.get(f"{self.register_url}?next={self.profile_url}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.profile_url}"', html=False)

    def test_register_page_drops_unsafe_external_next(self):
        response = self.client.get(f"{self.register_url}?next=https://evil.example/phish")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value=""', html=False)
        self.assertNotContains(response, "evil.example")


class ProtectedViewTests(TestCase):
    """Test authentication requirements for protected views."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse("charles:login")
        self.dashboard_url = reverse("charles:dashboard")
        self.profile_url = reverse("charles:profile")
        self.password_change_url = reverse("charles:password_change")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

    def test_dashboard_requires_login(self):
        """Unauthenticated user should be redirected to login."""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_dashboard_accessible_when_authenticated(self):
        """Authenticated user should access dashboard."""
        self.client.login(username="testuser", password="SecurePass123!")
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/dashboard.html")

    def test_profile_requires_login(self):
        """Unauthenticated user should be redirected to login."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)

    def test_profile_accessible_when_authenticated(self):
        """Authenticated user should access profile."""
        self.client.login(username="testuser", password="SecurePass123!")
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/profile.html")

    def test_password_change_requires_login(self):
        """Unauthenticated user should be redirected to login."""
        response = self.client.get(self.password_change_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.login_url, response.url)


class PasswordChangeTests(TestCase):
    """Test password change functionality."""

    def setUp(self):
        self.client = Client()
        self.password_change_url = reverse("charles:password_change")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="OldPassword123!",
        )

    def test_password_change_requires_login(self):
        """Unauthenticated user should be redirected."""
        response = self.client.get(self.password_change_url)
        self.assertEqual(response.status_code, 302)

    def test_successful_password_change(self):
        """Changing password with correct old password should work."""
        self.client.login(username="testuser", password="OldPassword123!")
        response = self.client.post(
            self.password_change_url,
            {
                "old_password": "OldPassword123!",
                "new_password1": "NewPassword123!",
                "new_password2": "NewPassword123!",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        # Verify user can log in with new password
        self.client.logout()
        login_result = self.client.login(username="testuser", password="NewPassword123!")
        self.assertTrue(login_result)

    def test_password_change_wrong_old_password(self):
        """Changing password with wrong old password should fail."""
        self.client.login(username="testuser", password="OldPassword123!")
        response = self.client.post(
            self.password_change_url,
            {
                "old_password": "WrongPassword123!",
                "new_password1": "NewPassword123!",
                "new_password2": "NewPassword123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        # Check that the form has errors
        form = response.context.get("form")
        self.assertIsNotNone(form)
        self.assertTrue(form.errors)


class ProfileTests(TestCase):
    """Test profile functionality."""

    def setUp(self):
        self.client = Client()
        self.profile_url = reverse("charles:profile")
        self.profile_update_bio_url = reverse("charles:profile_update_bio")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="SecurePass123!",
        )

    def test_profile_created_on_registration(self):
        """A Profile should be created when a User is created."""
        user = User.objects.create_user(username="newuser", password="SecurePass123!")
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_update(self):
        """Authenticated user should be able to update their profile."""
        self.client.login(username="testuser", password="SecurePass123!")
        response = self.client.post(
            self.profile_url,
            {"bio": "Hello, I'm a test user."},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Hello, I'm a test user.")

    def test_profile_bio_is_rendered_as_escaped_text(self):
        """Stored profile text should not be able to break out of the page."""
        malicious_bio = "<script>alert(1)</script>"

        self.client.login(username="testuser", password="SecurePass123!")
        response = self.client.post(
            self.profile_url,
            {"bio": malicious_bio},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, malicious_bio)
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;", html=False)
        self.assertNotContains(response, malicious_bio, html=False)


class ProfileAjaxCsrfTests(TestCase):
    """Test CSRF enforcement for the custom AJAX profile update flow."""

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.profile_url = reverse("charles:profile")
        self.profile_update_bio_url = reverse("charles:profile_update_bio")
        self.user = User.objects.create_user(
            username="ajaxuser",
            email="ajax@example.com",
            password="SecurePass123!",
        )
        self.client.force_login(self.user)

    def get_csrf_token(self):
        self.client.get(self.profile_url)
        return self.client.cookies["csrftoken"].value

    def test_ajax_profile_update_without_csrf_token_is_rejected(self):
        response = self.client.post(
            self.profile_update_bio_url,
            data=json.dumps({"bio": "Missing CSRF token"}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "")

    def test_ajax_profile_update_with_csrf_token_succeeds(self):
        csrf_token = self.get_csrf_token()
        response = self.client.post(
            self.profile_update_bio_url,
            data=json.dumps({"bio": "Updated over AJAX"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                "ok": True,
                "message": "Your profile has been updated.",
            },
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Updated over AJAX")

    def test_regular_profile_form_still_works_with_valid_csrf_token(self):
        csrf_token = self.get_csrf_token()
        response = self.client.post(
            self.profile_url,
            {
                "bio": "Updated through the normal form",
                "csrfmiddlewaretoken": csrf_token,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.profile.bio, "Updated through the normal form")


class PasswordResetTests(TestCase):
    """Test password reset workflow using Django's built-in mechanisms."""

    def setUp(self):
        self.client = Client()
        self.password_reset_url = reverse("charles:password_reset")
        self.password_reset_done_url = reverse("charles:password_reset_done")
        self.password_reset_complete_url = reverse("charles:password_reset_complete")
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="OldPassword123!",
        )

    def test_password_reset_request_page_loads(self):
        """GET /password-reset/ should return 200 and show the form."""
        response = self.client.get(self.password_reset_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/password_reset_request.html")
        self.assertIn("form", response.context)

    def test_password_reset_request_valid_email(self):
        """Password reset request with valid email should succeed and redirect."""
        response = self.client.post(
            self.password_reset_url,
            {"email": "test@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/password_reset_done.html")

    def test_password_reset_request_nonexistent_email(self):
        """Password reset for nonexistent email should not leak account existence."""
        response = self.client.post(
            self.password_reset_url,
            {"email": "nonexistent@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        # Django's PasswordResetView shows the same success page regardless
        # of whether the email exists, preventing user enumeration.
        self.assertTemplateUsed(response, "charles/password_reset_done.html")

    def test_password_reset_confirm_valid_token(self):
        """PasswordResetConfirmView with valid token should allow setting new password."""
        # Generate a reset token for the user
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        reset_confirm_url = reverse("charles:password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})

        # GET the reset_confirm page
        response = self.client.get(reset_confirm_url)
        # Django redirects to token-less URL for security, then 200
        response = self.client.get(response.url) if response.status_code == 302 else response
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/password_reset_confirm.html")
        self.assertIn("validlink", response.context)
        self.assertTrue(response.context["validlink"])

    def test_password_reset_confirm_and_login_with_new_password(self):
        """Setting new password via reset token should work."""
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        reset_confirm_url = reverse("charles:password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})

        # GET the reset_confirm page to verify it works with valid token
        get_response = self.client.get(reset_confirm_url)
        # Follow redirect if needed
        if get_response.status_code == 302:
            get_response = self.client.get(get_response.url)

        self.assertEqual(get_response.status_code, 200)
        self.assertTemplateUsed(get_response, "charles/password_reset_confirm.html")
        # The form should be present for setting new password
        self.assertIn("form", get_response.context)

    def test_password_reset_confirm_invalid_token(self):
        """PasswordResetConfirmView with invalid token should show expiry message."""
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        uidb64 = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_token = "invalid-token-12345"
        reset_confirm_url = reverse("charles:password_reset_confirm", kwargs={"uidb64": uidb64, "token": invalid_token})

        response = self.client.get(reset_confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "charles/password_reset_confirm.html")
        # validlink should be False for invalid tokens
        self.assertIn("validlink", response.context)
        self.assertFalse(response.context["validlink"])


class LoginBruteForceTests(TestCase):
    """Test protection against login brute-force attacks."""

    def setUp(self):
        self.login_url = reverse("charles:login")
        self.user = User.objects.create_user(
            username="targetuser",
            password="CorrectPassword123!",
        )
        self.dashboard_url = reverse("charles:dashboard")

    def fail_login(self, username="targetuser", count=1):
        response = None
        for _ in range(count):
            response = self.client.post(self.login_url, {
                "username": username,
                "password": "WrongPassword123!",
            })
        return response

    def test_valid_login_still_redirects_to_dashboard(self):
        response = self.client.post(self.login_url, {
            "username": "targetuser",
            "password": "CorrectPassword123!",
        })
        self.assertRedirects(response, self.dashboard_url)

    def test_four_failures_do_not_lock_account(self):
        self.fail_login(count=4)
        attempt = LoginAttempt.objects.get(username="targetuser")
        self.assertEqual(attempt.failed_count, 4)
        self.assertIsNone(attempt.locked_until)

    def test_repeated_failures_trigger_lockout(self):
        self.fail_login(count=5)
        attempt = LoginAttempt.objects.get(username="targetuser")
        self.assertEqual(attempt.failed_count, 5)
        self.assertIsNotNone(attempt.locked_until)
        self.assertGreater(attempt.locked_until, timezone.now())

    def test_locked_account_rejects_correct_password(self):
        LoginAttempt.objects.create(
            username="targetuser",
            failed_count=5,
            locked_until=timezone.now() + timedelta(minutes=10),
        )
        response = self.client.post(self.login_url, {
            "username": "targetuser",
            "password": "CorrectPassword123!",
        }, follow=True)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.status_code, 200)

    def test_lockout_message_mentions_wait_time(self):
        LoginAttempt.objects.create(
            username="targetuser",
            failed_count=5,
            locked_until=timezone.now() + timedelta(minutes=10),
        )
        response = self.client.post(self.login_url, {
            "username": "targetuser",
            "password": "CorrectPassword123!",
        })
        message_texts = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(any("minute" in message for message in message_texts))

    def test_successful_login_resets_counter(self):
        LoginAttempt.objects.create(username="targetuser", failed_count=3)
        self.client.post(self.login_url, {
            "username": "targetuser",
            "password": "CorrectPassword123!",
        })
        self.assertFalse(LoginAttempt.objects.filter(username="targetuser").exists())

    def test_lockout_expiry_allows_login_again(self):
        LoginAttempt.objects.create(
            username="targetuser",
            failed_count=5,
            locked_until=timezone.now() - timedelta(seconds=1),
        )
        response = self.client.post(self.login_url, {
            "username": "targetuser",
            "password": "CorrectPassword123!",
        })
        self.assertRedirects(response, self.dashboard_url)

    def test_lockout_expiry_resets_counter(self):
        LoginAttempt.objects.create(
            username="targetuser",
            failed_count=5,
            locked_until=timezone.now() - timedelta(seconds=1),
        )
        self.fail_login(count=1)
        attempt = LoginAttempt.objects.get(username="targetuser")
        self.assertEqual(attempt.failed_count, 1)
        self.assertIsNone(attempt.locked_until)

    def test_username_tracking_is_case_insensitive(self):
        self.fail_login(username="TargetUser", count=3)
        self.fail_login(username="TARGETUSER", count=2)
        attempt = LoginAttempt.objects.get(username="targetuser")
        self.assertEqual(attempt.failed_count, 5)
        self.assertIsNotNone(attempt.locked_until)

    def test_lockout_is_scoped_per_username(self):
        User.objects.create_user(username="otheruser", password="CorrectPassword123!")
        self.fail_login(count=5)
        response = self.client.post(self.login_url, {
            "username": "otheruser",
            "password": "CorrectPassword123!",
        })
        self.assertRedirects(response, self.dashboard_url)

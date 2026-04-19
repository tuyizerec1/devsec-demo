"""
charles/tests.py

Tests for the charles User Authentication Service.
Tests cover the main authentication lifecycle: registration, login, logout,
password change, and profile management.

Docs: https://docs.djangoproject.com/en/5.2/topics/testing/
"""

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse

from .models import Profile


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

import shutil
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Submission
from .uploads import MAX_AVATAR_UPLOAD_SIZE, MAX_DOCUMENT_UPLOAD_SIZE


class PortfolioSubmissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.contact_url = reverse("portfolio:contact")
        self.review_url = reverse("portfolio:submissions_review")
        self.staff_user = User.objects.create_user(
            username="curator",
            email="curator@example.com",
            password="SecurePass123!",
            is_staff=True,
            is_superuser=True,
        )
        self.viewer_user = User.objects.create_user(
            username="viewer",
            email="viewer@example.com",
            password="SecurePass123!",
        )
        self.staff_client = Client()
        self.staff_client.force_login(self.staff_user)
        self.viewer_client = Client()
        self.viewer_client.force_login(self.viewer_user)

        self.upload_root = Path(__file__).resolve().parent.parent / "private_media" / "test-submission-uploads"
        self.upload_root.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.upload_root, ignore_errors=True)
        self.media_override = override_settings(MEDIA_ROOT=str(self.upload_root))
        self.media_override.enable()
        self.addCleanup(self.media_override.disable)
        self.addCleanup(lambda: shutil.rmtree(self.upload_root, ignore_errors=True))

    def _avatar_file(self, name="avatar.png", content_type="image/png", body=None):
        if body is None:
            body = b"\x89PNG\r\n\x1a\nPNGDATA"
        return SimpleUploadedFile(name, body, content_type=content_type)

    def _document_file(self, name="document.pdf", content_type="application/pdf", body=None):
        if body is None:
            body = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF"
        return SimpleUploadedFile(name, body, content_type=content_type)

    def test_contact_page_loads(self):
        response = self.client.get(self.contact_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "portfolio/contact.html")

    def test_contact_submission_without_files_still_succeeds(self):
        response = self.client.post(
            self.contact_url,
            {
                "name": "Studio Visitor",
                "email": "visitor@example.com",
                "message": "I would like to discuss a private viewing.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your inquiry has been received securely.")
        submission = Submission.objects.get(email="visitor@example.com")
        self.assertEqual(submission.name, "Studio Visitor")
        self.assertFalse(submission.avatar)
        self.assertFalse(submission.document)

    def test_avatar_upload_accepts_png_and_is_downloadable_by_staff(self):
        response = self.client.post(
            self.contact_url,
            {
                "name": "Artist One",
                "email": "artist@example.com",
                "message": "Please review my materials.",
                "avatar": self._avatar_file(),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your inquiry has been received securely.")
        submission = Submission.objects.get(email="artist@example.com")
        self.assertTrue(submission.avatar)
        self.assertTrue(submission.avatar.name.startswith(f"submissions/{submission.public_id}/avatars/"))
        self.assertNotEqual(Path(submission.avatar.name).name, "avatar.png")

        download = self.staff_client.get(reverse("portfolio:submission_avatar", args=[submission.public_id]))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "image/png")
        self.assertIn("inline", download["Content-Disposition"])
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.assertEqual(download["Cache-Control"], "private, no-store")

        review = self.staff_client.get(self.review_url)
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, "Artist One")
        self.assertContains(review, reverse("portfolio:submission_avatar", args=[submission.public_id]))

    def test_document_upload_accepts_pdf_and_serves_as_attachment(self):
        response = self.client.post(
            self.contact_url,
            {
                "name": "Document Sender",
                "email": "document@example.com",
                "message": "Here is the requested PDF.",
                "document": self._document_file(),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        submission = Submission.objects.get(email="document@example.com")
        self.assertTrue(submission.document)
        self.assertTrue(submission.document.name.startswith(f"submissions/{submission.public_id}/documents/"))
        self.assertNotEqual(Path(submission.document.name).name, "document.pdf")

        download = self.staff_client.get(reverse("portfolio:submission_document", args=[submission.public_id]))
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/pdf")
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertEqual(download["X-Content-Type-Options"], "nosniff")
        self.assertEqual(download["Cache-Control"], "private, no-store")

    def test_avatar_upload_rejects_svg(self):
        bad_avatar = SimpleUploadedFile(
            "avatar.svg",
            b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
            content_type="image/svg+xml",
        )
        response = self.client.post(
            self.contact_url,
            {
                "name": "Artist Two",
                "email": "svg@example.com",
                "message": "This should not be accepted.",
                "avatar": bad_avatar,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.objects.count(), 0)
        self.assertIsNotNone(response.context)
        self.assertFormError(
            response.context["form"],
            "avatar",
            "Avatar uploads must be PNG, JPEG, GIF, or WEBP images.",
        )

    def test_avatar_upload_rejects_oversized_file(self):
        too_large_body = b"\x89PNG\r\n\x1a\n" + (b"a" * (MAX_AVATAR_UPLOAD_SIZE + 1))
        too_large_avatar = SimpleUploadedFile(
            "avatar.png",
            too_large_body,
            content_type="image/png",
        )
        response = self.client.post(
            self.contact_url,
            {
                "name": "Artist Three",
                "email": "large-avatar@example.com",
                "message": "This should be rejected.",
                "avatar": too_large_avatar,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.objects.count(), 0)
        self.assertIsNotNone(response.context)
        self.assertFormError(
            response.context["form"],
            "avatar",
            "Avatar files must be 2 MB or smaller.",
        )

    def test_document_upload_rejects_oversized_file(self):
        too_large_body = b"%PDF-" + (b"a" * (MAX_DOCUMENT_UPLOAD_SIZE + 1))
        response = self.client.post(
            self.contact_url,
            {
                "name": "Artist Four",
                "email": "large-document@example.com",
                "message": "This should be rejected.",
                "document": self._document_file(body=too_large_body),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Submission.objects.count(), 0)
        self.assertIsNotNone(response.context)
        self.assertFormError(
            response.context["form"],
            "document",
            "Document files must be 5 MB or smaller.",
        )

    def test_private_submission_views_require_staff_access(self):
        submission = Submission.objects.create(
            name="Access Test",
            email="access@example.com",
            message="Review access should be restricted.",
        )

        anon_review = self.client.get(self.review_url)
        self.assertEqual(anon_review.status_code, 302)
        self.assertIn(reverse("admin:login"), anon_review.url)

        anon_avatar = self.client.get(reverse("portfolio:submission_avatar", args=[submission.public_id]))
        self.assertEqual(anon_avatar.status_code, 302)
        self.assertIn(reverse("admin:login"), anon_avatar.url)

        anon_document = self.client.get(reverse("portfolio:submission_document", args=[submission.public_id]))
        self.assertEqual(anon_document.status_code, 302)
        self.assertIn(reverse("admin:login"), anon_document.url)

        viewer_review = self.viewer_client.get(self.review_url)
        self.assertEqual(viewer_review.status_code, 302)
        self.assertIn(reverse("admin:login"), viewer_review.url)

        staff_review = self.staff_client.get(self.review_url)
        self.assertEqual(staff_review.status_code, 200)
        self.assertContains(staff_review, "Access Test")

"""
charles/uploads.py

Validation and storage helpers for profile avatar and document uploads.
The goal is to keep uploaded files predictable, small, and non-executable.
"""

from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError


MAX_AVATAR_UPLOAD_SIZE = 2 * 1024 * 1024
MAX_DOCUMENT_UPLOAD_SIZE = 5 * 1024 * 1024

ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_DOCUMENT_CONTENT_TYPES = {"application/pdf"}

AVATAR_EXTENSIONS_BY_CONTENT_TYPE = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/gif": {".gif"},
    "image/webp": {".webp"},
}

DOCUMENT_EXTENSIONS_BY_CONTENT_TYPE = {
    "application/pdf": {".pdf"},
}

CONTENT_TYPE_ALIASES = {
    "application/x-pdf": "application/pdf",
    "image/jpg": "image/jpeg",
    "image/pjpeg": "image/jpeg",
}


def _upload_extension(uploaded_file):
    file_name = getattr(uploaded_file, "name", uploaded_file)
    return Path(str(file_name)).suffix.lower()


def _upload_content_type(uploaded_file):
    declared = (getattr(uploaded_file, "content_type", "") or "").lower()
    return CONTENT_TYPE_ALIASES.get(declared, declared)


def _read_prefix(uploaded_file, size):
    uploaded_file.seek(0)
    prefix = uploaded_file.read(size)
    uploaded_file.seek(0)
    return prefix


def _detect_avatar_content_type(uploaded_file):
    prefix = _read_prefix(uploaded_file, 12)
    if prefix.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if prefix.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a"):
        return "image/gif"
    if len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP":
        return "image/webp"
    return None


def _detect_document_content_type(uploaded_file):
    prefix = _read_prefix(uploaded_file, 5)
    if prefix.startswith(b"%PDF-"):
        return "application/pdf"
    return None


def _build_upload_path(instance, folder, uploaded_file):
    extension = _upload_extension(uploaded_file)
    return f"profile-assets/{instance.user_id}/{folder}/{uuid4().hex}{extension}"


def validate_avatar_upload(uploaded_file):
    """Reject unsafe avatar files before they are accepted."""

    if uploaded_file.size > MAX_AVATAR_UPLOAD_SIZE:
        raise ValidationError("Avatar files must be 2 MB or smaller.")

    declared_content_type = _upload_content_type(uploaded_file)
    detected_content_type = _detect_avatar_content_type(uploaded_file)
    extension = _upload_extension(uploaded_file)

    if detected_content_type is None:
        raise ValidationError("Avatar uploads must be PNG, JPEG, GIF, or WEBP images.")

    if detected_content_type not in ALLOWED_AVATAR_CONTENT_TYPES:
        raise ValidationError("Avatar uploads must be PNG, JPEG, GIF, or WEBP images.")

    if declared_content_type and declared_content_type not in {
        detected_content_type,
        "application/octet-stream",
    }:
        raise ValidationError("Avatar file type does not match the uploaded content.")

    if extension not in AVATAR_EXTENSIONS_BY_CONTENT_TYPE[detected_content_type]:
        raise ValidationError("Avatar file extension does not match the uploaded content.")


def validate_document_upload(uploaded_file):
    """Reject unsafe document files before they are accepted."""

    if uploaded_file.size > MAX_DOCUMENT_UPLOAD_SIZE:
        raise ValidationError("Document files must be 5 MB or smaller.")

    declared_content_type = _upload_content_type(uploaded_file)
    detected_content_type = _detect_document_content_type(uploaded_file)
    extension = _upload_extension(uploaded_file)

    if detected_content_type is None:
        raise ValidationError("Document uploads must be PDF files.")

    if detected_content_type not in ALLOWED_DOCUMENT_CONTENT_TYPES:
        raise ValidationError("Document uploads must be PDF files.")

    if declared_content_type and declared_content_type not in {
        detected_content_type,
        "application/octet-stream",
    }:
        raise ValidationError("Document file type does not match the uploaded content.")

    if extension not in DOCUMENT_EXTENSIONS_BY_CONTENT_TYPE[detected_content_type]:
        raise ValidationError("Document file extension does not match the uploaded content.")


def avatar_upload_to(instance, filename):
    return _build_upload_path(instance, "avatars", filename)


def document_upload_to(instance, filename):
    return _build_upload_path(instance, "documents", filename)

import mimetypes
from pathlib import Path

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from .forms import SubmissionForm
from .models import Submission


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


def _serve_submission_file(uploaded_file, attachment=False):
    if not uploaded_file or not uploaded_file.name or not uploaded_file.storage.exists(uploaded_file.name):
        raise Http404

    file_handle = uploaded_file.open("rb")
    response = FileResponse(file_handle, content_type=_guess_upload_content_type(uploaded_file.name))
    disposition = "attachment" if attachment else "inline"
    response["Content-Disposition"] = f'{disposition}; filename="{Path(uploaded_file.name).name}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def home(request):
    return render(request, "portfolio/home.html")


def gallery(request):
    return render(request, "portfolio/gallery.html")


def about(request):
    return render(request, "portfolio/about.html")


def contact(request):
    if request.method == "POST":
        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Your inquiry has been received securely.")
            return redirect("portfolio:contact")
    else:
        form = SubmissionForm()

    return render(request, "portfolio/contact.html", {"form": form})


@staff_member_required
def submissions_review(request):
    submissions = Submission.objects.all()
    return render(request, "portfolio/submissions.html", {"submissions": submissions})


@staff_member_required
@require_GET
def submission_avatar(request, public_id):
    submission = get_object_or_404(Submission, public_id=public_id)
    return _serve_submission_file(submission.avatar, attachment=False)


@staff_member_required
@require_GET
def submission_document(request, public_id):
    submission = get_object_or_404(Submission, public_id=public_id)
    return _serve_submission_file(submission.document, attachment=True)

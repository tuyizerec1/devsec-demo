from django import forms

from .models import Submission


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ("name", "email", "message", "avatar", "document")
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "autocomplete": "name",
                    "placeholder": "NAME / ORGANIZATION",
                    "class": "w-full bg-transparent border-0 border-b border-outline-variant/40 focus:ring-0 focus:border-primary text-on-surface placeholder:text-outline/40 py-4 font-body transition-all",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "autocomplete": "email",
                    "placeholder": "EMAIL ADDRESS",
                    "class": "w-full bg-transparent border-0 border-b border-outline-variant/40 focus:ring-0 focus:border-primary text-on-surface placeholder:text-outline/40 py-4 font-body transition-all",
                }
            ),
            "message": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "DESCRIBE YOUR PROJECT OR ARCHIVE REQUEST...",
                    "class": "w-full bg-transparent border-0 border-b border-outline-variant/40 focus:ring-0 focus:border-primary text-on-surface placeholder:text-outline/40 py-4 font-body resize-none transition-all",
                }
            ),
            "avatar": forms.FileInput(
                attrs={
                    "accept": ".png,.jpg,.jpeg,.gif,.webp",
                    "class": "w-full text-sm text-on-surface",
                }
            ),
            "document": forms.FileInput(
                attrs={
                    "accept": ".pdf",
                    "class": "w-full text-sm text-on-surface",
                }
            ),
        }

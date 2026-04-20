"""
charles/forms.py

We build on Django's built-in auth forms rather than writing our own from
scratch. This is intentional - those forms already handle password hashing,
timing-safe comparison, and validation in a battle-tested way.

Docs: https://docs.djangoproject.com/en/5.2/topics/auth/default/#module-django.contrib.auth.forms
"""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Profile


class RegistrationForm(UserCreationForm):
    """
    Extends UserCreationForm to add an email field.

    UserCreationForm already provides:
      - username validation (uniqueness, allowed characters)
      - password1 / password2 match check
      - the full AUTH_PASSWORD_VALIDATORS pipeline (length, common passwords, etc.)

    We only add email on top; everything else is inherited.

    Docs: https://docs.djangoproject.com/en/5.2/topics/auth/default/#django.contrib.auth.forms.UserCreationForm
    """

    email = forms.EmailField(
        required=True,
        help_text="Required. Enter a valid email address.",
    )

    class Meta:
        model = User
        # Field order determines the render order in templates.
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        """
        Persist the email field, which UserCreationForm does not include
        by default. The Profile is created by the post_save signal, so we
        do not need to create it here.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    """
    Thin subclass of AuthenticationForm so we can apply custom widget
    attributes (e.g. autofocus, placeholder) while keeping all the
    authentication logic intact.

    AuthenticationForm already:
      - validates credentials with authenticate()
      - blocks inactive accounts
      - does NOT reveal whether the username or the password was wrong
        (prevents user enumeration via error messages)

    Docs: https://docs.djangoproject.com/en/5.2/topics/auth/default/#django.contrib.auth.forms.AuthenticationForm
    """

    username = forms.CharField(
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class ProfileUpdateForm(forms.ModelForm):
    """
    Lets users update their own Profile (bio only).
    Using ModelForm means validation and saving are handled by Django.

    Docs: https://docs.djangoproject.com/en/5.2/topics/forms/modelforms/
    """

    class Meta:
        model = Profile
        fields = ("bio",)
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 4, "placeholder": "Tell us a little about yourself..."}),
        }


class ProfileAssetForm(forms.ModelForm):
    """
    Lets users upload an avatar image or PDF document.

    File validation lives on the model fields so the same rules apply in the
    form, the admin, and any future save path that uses model validation.
    """

    class Meta:
        model = Profile
        fields = ("avatar", "document")
        widgets = {
            "avatar": forms.FileInput(
                attrs={
                    "accept": ".png,.jpg,.jpeg,.gif,.webp",
                }
            ),
            "document": forms.FileInput(
                attrs={
                    "accept": ".pdf",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()

        if self.errors:
            return cleaned_data

        if not cleaned_data.get("avatar") and not cleaned_data.get("document"):
            raise forms.ValidationError("Choose an avatar image or PDF document to upload.")

        return cleaned_data

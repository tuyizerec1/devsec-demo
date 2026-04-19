"""
URL configuration for devsec_demo project.

All charles authentication routes are included under the /charles/ prefix.
Using include() keeps this file clean and lets the charles app manage its
own URL patterns independently.

Docs: https://docs.djangoproject.com/en/6.0/topics/http/urls/#url-namespaces
"""
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    # Redirect the bare root to the login page so visiting / works naturally.
    path('', RedirectView.as_view(pattern_name='charles:login', permanent=False)),

    path('admin/', admin.site.urls),

    # Mount the charles authentication app at /charles/
    path('charles/', include('charles.urls')),
]

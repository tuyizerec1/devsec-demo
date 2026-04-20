from django.urls import path
from . import views

app_name = 'portfolio'

urlpatterns = [
    path('', views.home, name='home'),
    path('gallery/', views.gallery, name='gallery'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('submissions/', views.submissions_review, name='submissions_review'),
    path('submissions/<uuid:public_id>/avatar/', views.submission_avatar, name='submission_avatar'),
    path('submissions/<uuid:public_id>/document/', views.submission_document, name='submission_document'),
]

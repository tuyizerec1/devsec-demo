from django.shortcuts import render


def home(request):
    return render(request, 'portfolio/home.html')


def gallery(request):
    return render(request, 'portfolio/gallery.html')


def about(request):
    return render(request, 'portfolio/about.html')


def contact(request):
    return render(request, 'portfolio/contact.html')

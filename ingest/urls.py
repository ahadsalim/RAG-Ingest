"""ingest URL Configuration"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from .admin import admin_site

# Import the view directly
from ingest.apps.documents.views import get_parent_options

# Embedding registration is now handled in embeddings/admin.py

def redirect_to_admin(request):
    return redirect('/admin/')

urlpatterns = [
    path('', redirect_to_admin, name='home'),
    path('ajax/documents/parent-options/', get_parent_options, name='documents_parent_options'),
    path('admin/', admin_site.urls),
    path('admin/embeddings/', include('ingest.apps.embeddings.urls')),
    path('admin/documents/', include('ingest.apps.documents.urls')),
    path('admin/accounts/', include('ingest.apps.accounts.urls')),
    path('api/', include('ingest.api.urls')),
]

# Serve static files only in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

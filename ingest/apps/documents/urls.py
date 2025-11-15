"""
URL patterns for documents app.
"""

from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('ajax/parent-options/', views.get_parent_options, name='get_parent_options'),
]

"""URLs for accounts app."""
from django.urls import path
from . import admin_views

app_name = 'accounts'

urlpatterns = [
    path('user-activity-report/', admin_views.user_activity_report, name='user_activity_report'),
    path('payroll-summary-report/', admin_views.payroll_summary_report, name='payroll_summary_report'),
]

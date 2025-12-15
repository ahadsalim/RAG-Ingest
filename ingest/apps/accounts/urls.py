"""URLs for accounts app."""
from django.urls import path
from . import admin_views
from .auth_views import OTPLoginView, OTPVerifyView, ResendOTPView, OTPLogoutView

app_name = 'accounts'

urlpatterns = [
    # OTP Authentication
    path('login/', OTPLoginView.as_view(), name='otp_login'),
    path('verify/', OTPVerifyView.as_view(), name='otp_verify'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('logout/', OTPLogoutView.as_view(), name='otp_logout'),
    
    # Reports
    path('user-activity-report/', admin_views.user_activity_report, name='user_activity_report'),
    path('payroll-summary-report/', admin_views.payroll_summary_report, name='payroll_summary_report'),
]

"""URLs for accounts app."""
from django.urls import path
from .auth_views import OTPLoginView, OTPVerifyView, ResendOTPView, OTPLogoutView

app_name = 'accounts'

urlpatterns = [
    # OTP Authentication
    path('login/', OTPLoginView.as_view(), name='otp_login'),
    path('verify/', OTPVerifyView.as_view(), name='otp_verify'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('logout/', OTPLogoutView.as_view(), name='otp_logout'),
]

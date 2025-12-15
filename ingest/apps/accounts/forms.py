"""
Forms for OTP-based authentication.
"""
from django import forms
from django.core.validators import RegexValidator
from django.contrib.auth.models import User
from .models import UserProfile, OTPCode


mobile_validator = RegexValidator(
    regex=r'^09\d{9}$',
    message='شماره موبایل باید با 09 شروع شود و 11 رقم باشد.'
)


class MobileLoginForm(forms.Form):
    """Form for entering mobile number to request OTP."""
    mobile = forms.CharField(
        max_length=11,
        min_length=11,
        label='شماره موبایل',
        validators=[mobile_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09123456789',
            'dir': 'ltr',
            'autocomplete': 'tel',
            'inputmode': 'numeric',
            'pattern': '09[0-9]{9}'
        })
    )
    
    def clean_mobile(self):
        mobile = self.cleaned_data['mobile']
        # Normalize mobile number
        mobile = mobile.replace(' ', '').replace('-', '')
        
        # Check if user exists
        if not UserProfile.objects.filter(mobile=mobile).exists():
            raise forms.ValidationError('این شماره موبایل در سیستم ثبت نشده است.')
        
        return mobile


class OTPVerifyForm(forms.Form):
    """Form for entering OTP code."""
    mobile = forms.CharField(widget=forms.HiddenInput())
    code = forms.CharField(
        max_length=6,
        min_length=6,
        label='کد تایید',
        widget=forms.TextInput(attrs={
            'class': 'form-control otp-input',
            'placeholder': '------',
            'dir': 'ltr',
            'autocomplete': 'one-time-code',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
            'maxlength': '6',
            'style': 'text-align: center; font-size: 24px; letter-spacing: 10px;'
        })
    )
    
    def clean_code(self):
        code = self.cleaned_data['code']
        if not code.isdigit():
            raise forms.ValidationError('کد تایید باید فقط شامل اعداد باشد.')
        return code


class UserProfileForm(forms.ModelForm):
    """Form for creating/editing user profile with mobile."""
    
    class Meta:
        model = UserProfile
        fields = ['mobile']
        widgets = {
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '09123456789',
                'dir': 'ltr'
            })
        }


class UserWithProfileForm(forms.ModelForm):
    """Form for creating user with profile (admin use)."""
    mobile = forms.CharField(
        max_length=11,
        min_length=11,
        label='شماره موبایل',
        validators=[mobile_validator],
        help_text='شماره موبایل باید در پیام‌رسان بله ثبت‌نام شده باشد',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '09123456789',
            'dir': 'ltr'
        })
    )
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_staff', 'is_active']
    
    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'mobile': self.cleaned_data['mobile'],
                    'is_mobile_verified': True
                }
            )
        return user

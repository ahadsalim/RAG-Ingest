"""
OTP-based authentication views for admin login.
"""
import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from .forms import MobileLoginForm, OTPVerifyForm
from .services import otp_service
from .models import LoginEvent, UserActivityLog, UserWorkSession

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@method_decorator(csrf_protect, name='dispatch')
class OTPLoginView(View):
    """View for OTP-based login - Step 1: Enter mobile number."""
    template_name = 'admin/otp_login.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('admin:index')
        
        form = MobileLoginForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = MobileLoginForm(request.POST)
        
        if form.is_valid():
            mobile = form.cleaned_data['mobile']
            
            # Send OTP
            result = otp_service.send_otp(mobile)
            
            if result['success']:
                # Store mobile in session for verification step
                request.session['otp_mobile'] = mobile
                messages.success(request, result['message'])
                return redirect('accounts:otp_verify')
            else:
                messages.error(request, result['error'])
        
        return render(request, self.template_name, {'form': form})


@method_decorator(csrf_protect, name='dispatch')
class OTPVerifyView(View):
    """View for OTP verification - Step 2: Enter OTP code."""
    template_name = 'admin/otp_verify.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('admin:index')
        
        mobile = request.session.get('otp_mobile')
        if not mobile:
            messages.error(request, 'لطفاً ابتدا شماره موبایل خود را وارد کنید.')
            return redirect('accounts:otp_login')
        
        form = OTPVerifyForm(initial={'mobile': mobile})
        # Mask mobile for display
        masked_mobile = f"{mobile[:4]}****{mobile[-3:]}"
        
        return render(request, self.template_name, {
            'form': form,
            'masked_mobile': masked_mobile
        })
    
    def post(self, request):
        mobile = request.session.get('otp_mobile')
        if not mobile:
            return redirect('accounts:otp_login')
        
        form = OTPVerifyForm(request.POST)
        
        if form.is_valid():
            code = form.cleaned_data['code']
            
            # Verify OTP
            result = otp_service.verify_otp(mobile, code)
            
            if result['success']:
                user = result['user']
                
                # Check if user is staff
                if not user.is_staff:
                    messages.error(request, 'شما دسترسی به پنل مدیریت ندارید.')
                    return redirect('accounts:otp_login')
                
                # Log the user in
                login(request, user)
                
                # Record login event
                ip = get_client_ip(request)
                LoginEvent.objects.create(
                    user=user,
                    ip_address=ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                    success=True
                )
                
                # Create work session
                UserWorkSession.objects.create(
                    user=user,
                    login_time=user.last_login,
                    ip_address=ip
                )
                
                # Clear session data
                del request.session['otp_mobile']
                
                messages.success(request, f'خوش آمدید {user.get_full_name() or user.username}!')
                
                # Redirect to next or admin
                next_url = request.GET.get('next', 'admin:index')
                return redirect(next_url)
            else:
                messages.error(request, result['error'])
        
        masked_mobile = f"{mobile[:4]}****{mobile[-3:]}"
        return render(request, self.template_name, {
            'form': form,
            'masked_mobile': masked_mobile
        })


class ResendOTPView(View):
    """View for resending OTP code."""
    
    def post(self, request):
        mobile = request.session.get('otp_mobile')
        if not mobile:
            return JsonResponse({
                'success': False,
                'error': 'شماره موبایل یافت نشد.'
            })
        
        result = otp_service.send_otp(mobile)
        return JsonResponse(result)


class OTPLogoutView(View):
    """View for logging out."""
    
    def get(self, request):
        return self.post(request)
    
    def post(self, request):
        if request.user.is_authenticated:
            # Update work session
            try:
                from django.utils import timezone
                session = UserWorkSession.objects.filter(
                    user=request.user,
                    logout_time__isnull=True
                ).latest('login_time')
                session.logout_time = timezone.now()
                session.calculate_duration()
            except UserWorkSession.DoesNotExist:
                pass
            
            # Record logout activity
            UserActivityLog.objects.create(
                user=request.user,
                action='logout',
                ip_address=get_client_ip(request)
            )
            
            logout(request)
            messages.success(request, 'با موفقیت خارج شدید.')
        
        return redirect('accounts:otp_login')

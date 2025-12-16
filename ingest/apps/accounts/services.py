"""
Bale Messenger OTP Service
Sends OTP codes via Bale Safir API (https://safir.bale.ai)
"""
import logging
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class BaleMessengerService:
    """
    Service for sending OTP codes via Bale Safir API.
    
    API Documentation: https://safir.bale.ai
    
    Required settings:
        BALE_API_URL: Base URL for Safir API (default: https://safir.bale.ai/api/v2)
        BALE_CLIENT_ID: OAuth2 client ID
        BALE_CLIENT_SECRET: OAuth2 client secret
    """
    
    TOKEN_CACHE_KEY = 'bale_access_token'
    TOKEN_CACHE_TIMEOUT = 3500  # ~58 minutes (tokens usually valid for 1 hour)
    
    def __init__(self):
        self.api_url = getattr(settings, 'BALE_API_URL', 'https://safir.bale.ai/api/v2')
        self.client_id = getattr(settings, 'BALE_CLIENT_ID', None)
        self.client_secret = getattr(settings, 'BALE_CLIENT_SECRET', None)
        
        if not self.client_id or not self.client_secret:
            logger.warning("Bale API credentials not configured (BALE_CLIENT_ID, BALE_CLIENT_SECRET)")
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token from Bale Safir API."""
        # Check cache first
        cached_token = cache.get(self.TOKEN_CACHE_KEY)
        if cached_token:
            return cached_token
        
        if not self.client_id or not self.client_secret:
            logger.error("Bale API credentials not configured")
            return None
        
        try:
            # Auth token endpoint (per Bale Safir API docs)
            token_url = f"{self.api_url}/auth/token"
            
            # Must be sent as form-data with specific parameters
            payload = {
                'grant_type': 'client_credentials',
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'scope': 'read'
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            response = requests.post(token_url, data=payload, headers=headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            access_token = result.get('access_token')
            
            if access_token:
                # Cache the token
                cache.set(self.TOKEN_CACHE_KEY, access_token, self.TOKEN_CACHE_TIMEOUT)
                logger.info("Bale access token obtained successfully")
                return access_token
            else:
                logger.error(f"No access token in response: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Bale access token: {e}")
            return None
    
    def _normalize_phone(self, mobile: str) -> str:
        """
        Normalize phone number to Bale format (98XXXXXXXXX).
        
        Input formats:
            - 09123456789 -> 989123456789
            - 9123456789 -> 989123456789
            - +989123456789 -> 989123456789
            - 989123456789 -> 989123456789
        """
        # Remove spaces, dashes, and plus sign
        phone = mobile.replace(' ', '').replace('-', '').replace('+', '')
        
        # Remove leading zero if present
        if phone.startswith('0'):
            phone = phone[1:]
        
        # Add country code if not present
        if not phone.startswith('98'):
            phone = '98' + phone
        
        return phone
    
    def send_otp(self, mobile: str, code: str) -> dict:
        """
        Send OTP code to user via Bale Safir API.
        
        Args:
            mobile: User's mobile number (any format)
            code: OTP code (3-8 digits)
        
        Returns:
            dict with 'success', 'message' or 'error', and optionally 'balance'
        """
        access_token = self._get_access_token()
        if not access_token:
            return {
                'success': False,
                'error': 'خطا در اتصال به سرویس بله. لطفاً بعداً تلاش کنید.'
            }
        
        try:
            url = f"{self.api_url}/send_otp"
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'phone': self._normalize_phone(mobile),
                'otp': int(code)
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            # Handle specific error codes
            if response.status_code == 400:
                result = response.json()
                if result.get('code') == 8:
                    return {
                        'success': False,
                        'error': 'شماره موبایل نامعتبر است.'
                    }
                return {
                    'success': False,
                    'error': f"خطای درخواست: {result.get('message', 'نامشخص')}"
                }
            
            elif response.status_code == 404:
                return {
                    'success': False,
                    'error': 'این شماره در پیام‌رسان بله ثبت‌نام نکرده است.'
                }
            
            elif response.status_code == 402:
                logger.error("Bale OTP service: insufficient balance")
                return {
                    'success': False,
                    'error': 'خطای سرویس. لطفاً با پشتیبانی تماس بگیرید.'
                }
            
            elif response.status_code == 429:
                return {
                    'success': False,
                    'error': 'تعداد درخواست‌ها بیش از حد مجاز است. لطفاً کمی صبر کنید.'
                }
            
            elif response.status_code == 500:
                return {
                    'success': False,
                    'error': 'خطای سرور بله. لطفاً بعداً تلاش کنید.'
                }
            
            response.raise_for_status()
            
            result = response.json()
            balance = result.get('balance', 0)
            
            logger.info(f"OTP sent to {mobile[:4]}****. Balance: {balance}")
            
            return {
                'success': True,
                'message': 'کد تایید به پیام‌رسان بله ارسال شد.',
                'balance': balance
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send OTP via Bale: {e}")
            return {
                'success': False,
                'error': 'خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.'
            }


class OTPService:
    """Service for managing OTP authentication."""
    
    def __init__(self):
        self.bale_service = BaleMessengerService()
    
    def send_otp(self, mobile: str) -> dict:
        """Generate and send OTP to user via Bale Safir API."""
        from .models import OTPCode, UserProfile
        
        # Check if user exists with this mobile
        try:
            profile = UserProfile.objects.get(mobile=mobile)
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'error': 'شماره موبایل در سیستم ثبت نشده است.'
            }
        
        # Generate OTP
        otp = OTPCode.generate_code(mobile)
        
        # Send via Bale Safir API (uses phone number directly, no chat_id needed)
        result = self.bale_service.send_otp(mobile, otp.code)
        
        if result['success']:
            return {
                'success': True,
                'message': result.get('message', 'کد تایید به پیام‌رسان بله ارسال شد.'),
                'expires_in': 300  # 5 minutes
            }
        else:
            return result
    
    def verify_otp(self, mobile: str, code: str) -> dict:
        """Verify OTP code and return user if valid."""
        from .models import OTPCode, UserProfile
        from django.contrib.auth.models import User
        
        # Get latest unused OTP for this mobile
        try:
            otp = OTPCode.objects.filter(
                mobile=mobile,
                is_used=False
            ).latest('created_at')
        except OTPCode.DoesNotExist:
            return {
                'success': False,
                'error': 'کد تایید یافت نشد. لطفاً کد جدید درخواست کنید.'
            }
        
        if otp.verify(code):
            # Get user
            try:
                profile = UserProfile.objects.get(mobile=mobile)
                profile.is_mobile_verified = True
                profile.save()
                
                return {
                    'success': True,
                    'user': profile.user
                }
            except UserProfile.DoesNotExist:
                return {
                    'success': False,
                    'error': 'کاربر یافت نشد.'
                }
        else:
            if otp.attempts >= 5:
                return {
                    'success': False,
                    'error': 'تعداد تلاش‌های مجاز به پایان رسید. لطفاً کد جدید درخواست کنید.'
                }
            return {
                'success': False,
                'error': 'کد تایید نادرست است.'
            }


# Singleton instance
otp_service = OTPService()

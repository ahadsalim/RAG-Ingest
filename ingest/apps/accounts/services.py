"""
SMS OTP Service
Sends OTP codes via SMS API (Kavenegar or any HTTP SMS API)
"""
import logging
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


class SMSService:
    """
    Service for sending OTP codes via SMS API.
    
    Supports Kavenegar SMS API by default, but can be configured for any HTTP SMS API.
    
    Required settings:
        SMS_API_URL: Base URL for SMS API
        SMS_API_KEY: API key for SMS service
        SMS_SENDER: Sender number or ID
        SMS_API_TYPE: API type ('kavenegar', 'generic', etc.)
        SMS_TEMPLATE_NAME: Template name for OTP messages (for Kavenegar)
    """
    
    def __init__(self):
        self.api_url = getattr(settings, 'SMS_API_URL', 'https://api.kavenegar.com/v1')
        self.api_key = getattr(settings, 'SMS_API_KEY', None)
        self.sender = getattr(settings, 'SMS_SENDER', '100010010')
        self.api_type = getattr(settings, 'SMS_API_TYPE', 'kavenegar')
        self.template_name = getattr(settings, 'SMS_TEMPLATE_NAME', 'otp')
        
        if not self.api_key:
            logger.warning("SMS API credentials not configured (SMS_API_KEY)")
    
    def _normalize_phone(self, mobile: str) -> str:
        """
        Normalize phone number to Iranian format (09XXXXXXXXX).
        
        Input formats:
            - 09123456789 -> 09123456789
            - 9123456789 -> 09123456789
            - +989123456789 -> 09123456789
            - 989123456789 -> 09123456789
        """
        # Remove spaces, dashes, and plus sign
        phone = mobile.replace(' ', '').replace('-', '').replace('+', '')
        
        # Remove leading 98 if present and add 0
        if phone.startswith('98') and len(phone) == 12:
            phone = '0' + phone[2:]
        # Add leading 0 if missing and number starts with 9
        elif phone.startswith('9') and len(phone) == 10:
            phone = '0' + phone
        
        return phone
    
    def send_otp(self, mobile: str, code: str) -> dict:
        """
        Send OTP code to user via SMS API.
        
        Args:
            mobile: User's mobile number (any format)
            code: OTP code (3-8 digits)
        
        Returns:
            dict with 'success', 'message' or 'error'
        """
        if not self.api_key:
            return {
                'success': False,
                'error': 'سرویس پیامک پیکربندی نشده است. لطفاً با پشتیبانی تماس بگیرید.'
            }
        
        try:
            if self.api_type == 'kavenegar':
                return self._send_kavenegar_otp(mobile, code)
            else:
                return self._send_generic_otp(mobile, code)
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send OTP via SMS: {e}")
            return {
                'success': False,
                'error': 'خطا در ارسال پیامک. لطفاً دوباره تلاش کنید.'
            }
    
    def _send_kavenegar_otp(self, mobile: str, code: str) -> dict:
        """Send OTP via Kavenegar API."""
        normalized_mobile = self._normalize_phone(mobile)
        
        # Kavenegar verify lookup API for OTP
        url = f"{self.api_url}/{self.api_key}/verify/lookup.json"
        
        payload = {
            'receptor': normalized_mobile,
            'token': code,
            'template': self.template_name  # Use template name from settings
        }
        
        response = requests.post(url, data=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('return', {}).get('status') == 200:
                logger.info(f"OTP sent to {normalized_mobile[:4]}**** via SMS")
                return {
                    'success': True,
                    'message': 'کد تایید به شماره موبایل شما ارسال شد.'
                }
            else:
                error_message = result.get('return', {}).get('message', 'خطای نامشخص')
                logger.error(f"Kavenegar API error: {error_message}")
                return {
                    'success': False,
                    'error': f"خطا در ارسال پیامک: {error_message}"
                }
        else:
            logger.error(f"Kavenegar HTTP error: {response.status_code}")
            return {
                'success': False,
                'error': 'خطا در ارتباط با سرویس پیامک.'
            }
    
    def _send_generic_otp(self, mobile: str, code: str) -> dict:
        """Send OTP via generic HTTP SMS API."""
        normalized_mobile = self._normalize_phone(mobile)
        
        # Generic SMS API - adjust according to your SMS provider
        url = f"{self.api_url}/send"
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'to': normalized_mobile,
            'from': self.sender,
            'message': f'کد تایید شما: {code}\n\nاین کد ۵ دقیقه معتبر است.'
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"OTP sent to {normalized_mobile[:4]}**** via SMS")
            return {
                'success': True,
                'message': 'کد تایید به شماره موبایل شما ارسال شد.'
            }
        else:
            logger.error(f"Generic SMS API error: {response.status_code}")
            return {
                'success': False,
                'error': 'خطا در ارسال پیامک.'
            }


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
    """Service for managing OTP authentication.
    
    Note: In this system, username = mobile number.
    """
    
    def __init__(self):
        self.sms_service = SMSService()
        self.bale_service = BaleMessengerService()
        self.use_sms = getattr(settings, 'USE_SMS_FOR_OTP', True)  # Default to SMS
    
    def send_otp(self, mobile: str) -> dict:
        """Generate and send OTP to user via SMS or Bale."""
        from .models import OTPCode
        from django.contrib.auth.models import User
        
        # Check if user exists (username = mobile number)
        if not User.objects.filter(username=mobile).exists():
            return {
                'success': False,
                'error': 'شماره موبایل در سیستم ثبت نشده است.'
            }
        
        # Generate OTP
        otp = OTPCode.generate_code(mobile)
        
        # Send via SMS or Bale based on configuration
        if self.use_sms:
            result = self.sms_service.send_otp(mobile, otp.code)
            if result['success']:
                result['message'] = result.get('message', 'کد تایید به شماره موبایل شما ارسال شد.')
        else:
            result = self.bale_service.send_otp(mobile, otp.code)
        
        if result['success']:
            return {
                'success': True,
                'message': result.get('message', 'کد تایید ارسال شد.'),
                'expires_in': 300  # 5 minutes
            }
        else:
            return result
    
    def verify_otp(self, mobile: str, code: str) -> dict:
        """Verify OTP code and return user if valid."""
        from .models import OTPCode
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
            # Get user (username = mobile number)
            try:
                user = User.objects.get(username=mobile)
                return {
                    'success': True,
                    'user': user
                }
            except User.DoesNotExist:
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

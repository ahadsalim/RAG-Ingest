"""
Bale Messenger OTP Service
Sends OTP codes via Bale messenger bot API
"""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BaleMessengerService:
    """Service for sending OTP codes via Bale messenger."""
    
    BASE_URL = "https://tapi.bale.ai/bot"
    
    def __init__(self):
        self.token = getattr(settings, 'BALE_BOT_TOKEN', None)
        if not self.token:
            logger.warning("BALE_BOT_TOKEN not configured")
    
    @property
    def api_url(self):
        return f"{self.BASE_URL}{self.token}"
    
    def send_message(self, chat_id: str, text: str) -> bool:
        """Send a message to a Bale chat."""
        if not self.token:
            logger.error("Bale bot token not configured")
            return False
        
        try:
            url = f"{self.api_url}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                logger.info(f"Message sent to chat_id: {chat_id}")
                return True
            else:
                logger.error(f"Bale API error: {result}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Bale message: {e}")
            return False
    
    def send_otp(self, chat_id: str, code: str) -> bool:
        """Send OTP code to user via Bale."""
        message = f"""🔐 *کد تایید ورود*

کد تایید شما: `{code}`

⏱ این کد تا ۵ دقیقه معتبر است.

⚠️ این کد را با کسی به اشتراک نگذارید."""
        
        return self.send_message(chat_id, message)
    
    def get_updates(self, offset: int = None) -> list:
        """Get updates from Bale bot (for receiving chat_id from users)."""
        if not self.token:
            return []
        
        try:
            url = f"{self.api_url}/getUpdates"
            params = {}
            if offset:
                params['offset'] = offset
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('ok'):
                return result.get('result', [])
            return []
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Bale updates: {e}")
            return []


class OTPService:
    """Service for managing OTP authentication."""
    
    def __init__(self):
        self.bale_service = BaleMessengerService()
    
    def send_otp(self, mobile: str, bale_chat_id: str = None) -> dict:
        """Generate and send OTP to user."""
        from .models import OTPCode, UserProfile
        
        # Check if user exists with this mobile
        try:
            profile = UserProfile.objects.get(mobile=mobile)
            chat_id = bale_chat_id or profile.bale_chat_id
        except UserProfile.DoesNotExist:
            return {
                'success': False,
                'error': 'شماره موبایل در سیستم ثبت نشده است.'
            }
        
        if not chat_id:
            return {
                'success': False,
                'error': 'شناسه چت بله برای این کاربر تنظیم نشده است.'
            }
        
        # Generate OTP
        otp = OTPCode.generate_code(mobile)
        
        # Send via Bale
        if self.bale_service.send_otp(chat_id, otp.code):
            return {
                'success': True,
                'message': 'کد تایید به پیام‌رسان بله ارسال شد.',
                'expires_in': 300  # 5 minutes
            }
        else:
            return {
                'success': False,
                'error': 'خطا در ارسال کد تایید. لطفاً دوباره تلاش کنید.'
            }
    
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

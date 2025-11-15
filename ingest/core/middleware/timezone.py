"""
Timezone middleware for uniform display timezone activation.
Activates the configured display timezone for all requests.
"""
from django.utils import timezone
from django.conf import settings


class ActivateDisplayTimezoneMiddleware:
    """
    Middleware to activate the display timezone for all requests.
    
    This ensures that all datetime displays use the configured
    DISPLAY_TIME_ZONE while keeping database storage in UTC.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.display_timezone = getattr(settings, 'DISPLAY_TIME_ZONE', 'Asia/Tehran')
    
    def __call__(self, request):
        # Activate the display timezone for this request
        timezone.activate(self.display_timezone)
        
        try:
            response = self.get_response(request)
        finally:
            # Deactivate timezone to prevent leaks
            timezone.deactivate()
        
        return response

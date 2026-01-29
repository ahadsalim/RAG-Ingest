    #!/usr/bin/env python
"""
Test script for SMS OTP functionality
"""
import os
import sys
import django

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.base')
django.setup()

from apps.accounts.services import SMSService, OTPService

def test_sms_service():
    print("=== SMS Service Test ===")
    
    # Test SMS service initialization
    sms_service = SMSService()
    print(f'API URL: {sms_service.api_url}')
    print(f'API Key configured: {bool(sms_service.api_key)}')
    print(f'Sender: {sms_service.sender}')
    print(f'API Type: {sms_service.api_type}')
    
    # Test phone normalization
    test_numbers = ['09123456789', '9123456789', '+989123456789', '989123456789']
    print('\nPhone number normalization test:')
    for num in test_numbers:
        normalized = sms_service._normalize_phone(num)
        print(f'  {num} -> {normalized}')
    
    # Test OTP sending (will fail gracefully due to no API key)
    print('\nTesting OTP send (should fail gracefully):')
    result = sms_service.send_otp('09123456789', '123456')
    print(f'Result: {result}')
    
    return result

def test_otp_service():
    print("\n=== OTP Service Test ===")
    
    otp_service = OTPService()
    print(f'Using SMS: {otp_service.use_sms}')
    print(f'SMS Service initialized: {hasattr(otp_service, "sms_service")}')
    print(f'Bale Service initialized: {hasattr(otp_service, "bale_service")}')
    
    # Test with a user that exists in the database
    print('\nTesting OTP send for existing user:')
    result = otp_service.send_otp('09122711309')  # This user exists in the restored database
    print(f'Result: {result}')
    
    return result

if __name__ == '__main__':
    test_sms_service()
    test_otp_service()
    print("\n=== Test Complete ===")

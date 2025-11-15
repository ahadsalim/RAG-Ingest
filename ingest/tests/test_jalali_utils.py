"""
Tests for Jalali date utilities.
"""
from datetime import datetime, date
from django.test import TestCase, override_settings
from django.utils import timezone
from ingest.core.jalali import (
    to_jalali_date,
    to_jalali_datetime,
    parse_jalali_date,
    parse_jalali_datetime,
    format_jalali_verbose,
    persian_digits,
    english_digits,
    get_jalali_month_name,
    get_jalali_weekday_name
)


class JalaliUtilsTest(TestCase):
    """Test Jalali date utility functions."""
    
    def setUp(self):
        """Set up test data."""
        # Known Gregorian to Jalali conversions
        self.gregorian_date = date(2024, 3, 20)  # First day of spring (Nowruz)
        self.expected_jalali_date = "1403/01/01"
        
        # Timezone-aware datetime
        self.gregorian_datetime = timezone.make_aware(
            datetime(2024, 3, 20, 14, 30, 0),
            timezone.get_current_timezone()
        )
    
    def test_to_jalali_date(self):
        """Test Gregorian to Jalali date conversion."""
        result = to_jalali_date(self.gregorian_date)
        self.assertEqual(result, self.expected_jalali_date)
        
        # Test with None
        self.assertEqual(to_jalali_date(None), "")
        
        # Test with datetime object
        result = to_jalali_date(self.gregorian_datetime)
        self.assertEqual(result, self.expected_jalali_date)
    
    def test_to_jalali_datetime(self):
        """Test Gregorian to Jalali datetime conversion."""
        result = to_jalali_datetime(self.gregorian_datetime)
        self.assertIn("1403/01/01", result)
        self.assertIn("14:30", result)
        
        # Test with None
        self.assertEqual(to_jalali_datetime(None), "")
        
        # Test with timezone info
        result = to_jalali_datetime(self.gregorian_datetime, include_timezone=True)
        self.assertIn("1403/01/01", result)
        self.assertIn("14:30", result)
    
    def test_parse_jalali_date(self):
        """Test Jalali date string parsing."""
        # Test various formats
        test_cases = [
            "1403/01/01",
            "1403/1/1",
            "1403-01-01",
            "1403-1-1",
        ]
        
        for jalali_str in test_cases:
            result = parse_jalali_date(jalali_str)
            self.assertIsInstance(result, date)
            # Should be around March 20, 2024
            self.assertEqual(result.year, 2024)
            self.assertEqual(result.month, 3)
        
        # Test invalid inputs
        self.assertIsNone(parse_jalali_date(""))
        self.assertIsNone(parse_jalali_date(None))
        self.assertIsNone(parse_jalali_date("invalid"))
        self.assertIsNone(parse_jalali_date("1403/13/01"))  # Invalid month
    
    def test_parse_jalali_datetime(self):
        """Test Jalali datetime string parsing."""
        # Test various formats
        test_cases = [
            "1403/01/01 14:30",
            "1403/1/1 14:30:45",
            "1403-01-01 14:30",
        ]
        
        for jalali_str in test_cases:
            result = parse_jalali_datetime(jalali_str)
            self.assertIsInstance(result, datetime)
            self.assertTrue(timezone.is_aware(result))
            # Should be in UTC
            self.assertEqual(result.tzinfo, timezone.utc)
        
        # Test invalid inputs
        self.assertIsNone(parse_jalali_datetime(""))
        self.assertIsNone(parse_jalali_datetime(None))
        self.assertIsNone(parse_jalali_datetime("invalid"))
    
    def test_format_jalali_verbose(self):
        """Test verbose Jalali formatting."""
        result = format_jalali_verbose(self.gregorian_date)
        self.assertIn("فروردین", result)  # Should contain month name
        self.assertIn("۱۴۰۳", result)     # Should contain Persian year
        
        # Test with None
        self.assertEqual(format_jalali_verbose(None), "")
    
    def test_persian_digits(self):
        """Test English to Persian digit conversion."""
        test_cases = [
            ("123", "۱۲۳"),
            ("2024", "۲۰۲۴"),
            ("0", "۰"),
            ("abc123def", "abc۱۲۳def"),
        ]
        
        for english, expected_persian in test_cases:
            result = persian_digits(english)
            self.assertEqual(result, expected_persian)
    
    def test_english_digits(self):
        """Test Persian to English digit conversion."""
        test_cases = [
            ("۱۲۳", "123"),
            ("۲۰۲۴", "2024"),
            ("۰", "0"),
            ("abc۱۲۳def", "abc123def"),
        ]
        
        for persian, expected_english in test_cases:
            result = english_digits(persian)
            self.assertEqual(result, expected_english)
    
    def test_get_jalali_month_name(self):
        """Test Jalali month name retrieval."""
        self.assertEqual(get_jalali_month_name(1), "فروردین")
        self.assertEqual(get_jalali_month_name(12), "اسفند")
        self.assertEqual(get_jalali_month_name(13), "13")  # Invalid month
    
    def test_get_jalali_weekday_name(self):
        """Test Jalali weekday name retrieval."""
        self.assertEqual(get_jalali_weekday_name(0), "شنبه")  # Saturday
        self.assertEqual(get_jalali_weekday_name(6), "جمعه")  # Friday
        self.assertEqual(get_jalali_weekday_name(7), "7")    # Invalid weekday
    
    @override_settings(DISPLAY_TIME_ZONE='Europe/Berlin')
    def test_timezone_handling(self):
        """Test that display timezone is respected."""
        # This test ensures timezone middleware works correctly
        utc_datetime = timezone.make_aware(
            datetime(2024, 3, 20, 12, 0, 0),
            timezone.utc
        )
        
        result = to_jalali_datetime(utc_datetime)
        # Should convert to Berlin time before Jalali conversion
        self.assertIn("1403/01/01", result)
    
    def test_roundtrip_conversion(self):
        """Test that date conversion roundtrips correctly."""
        # Gregorian -> Jalali -> Gregorian should be consistent
        original_date = date(2024, 3, 20)
        jalali_str = to_jalali_date(original_date)
        converted_back = parse_jalali_date(jalali_str)
        
        self.assertEqual(original_date, converted_back)
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Test leap year handling
        leap_year_date = date(2024, 2, 29)  # 2024 is a leap year
        jalali_str = to_jalali_date(leap_year_date)
        self.assertIsNotNone(jalali_str)
        
        # Test year boundaries
        new_year_date = date(2024, 3, 20)  # Persian New Year
        jalali_str = to_jalali_date(new_year_date)
        self.assertEqual(jalali_str, "1403/01/01")
        
        # Test end of Persian year
        end_year_date = date(2025, 3, 19)  # Last day of Persian year
        jalali_str = to_jalali_date(end_year_date)
        self.assertIn("1403/12/", jalali_str)

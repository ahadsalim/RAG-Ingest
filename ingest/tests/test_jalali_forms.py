"""
Tests for Jalali form fields and widgets.
"""
from datetime import datetime, date
from django.test import TestCase
from django.forms import ValidationError
from django.utils import timezone
from ingest.core.forms.fields import JalaliDateField, JalaliDateTimeField
from ingest.core.forms.widgets import JalaliDateInput, JalaliDateTimeInput


class JalaliFormFieldsTest(TestCase):
    """Test Jalali form fields."""
    
    def test_jalali_date_field_valid_input(self):
        """Test JalaliDateField with valid inputs."""
        field = JalaliDateField()
        
        # Test various valid formats
        test_cases = [
            "1403/01/01",
            "1403/1/1",
            "1403-01-01",
            "۱۴۰۳/۰۱/۰۱",  # Persian digits
        ]
        
        for jalali_str in test_cases:
            result = field.to_python(jalali_str)
            self.assertIsInstance(result, date)
            # Should be around March 2024
            self.assertEqual(result.year, 2024)
    
    def test_jalali_date_field_invalid_input(self):
        """Test JalaliDateField with invalid inputs."""
        field = JalaliDateField()
        
        invalid_inputs = [
            "1403/13/01",  # Invalid month
            "1403/01/32",  # Invalid day
            "invalid",
            "1403",
            "",
        ]
        
        for invalid_input in invalid_inputs:
            if invalid_input == "":
                # Empty string should return None, not raise error
                result = field.to_python(invalid_input)
                self.assertIsNone(result)
            else:
                with self.assertRaises(ValidationError):
                    field.to_python(invalid_input)
    
    def test_jalali_date_field_prepare_value(self):
        """Test JalaliDateField value preparation for display."""
        field = JalaliDateField()
        
        # Test with Gregorian date
        gregorian_date = date(2024, 3, 20)  # Nowruz
        prepared = field.prepare_value(gregorian_date)
        self.assertEqual(prepared, "1403/01/01")
        
        # Test with None
        self.assertEqual(field.prepare_value(None), "")
        
        # Test with string (should return as-is)
        self.assertEqual(field.prepare_value("1403/01/01"), "1403/01/01")
    
    def test_jalali_datetime_field_valid_input(self):
        """Test JalaliDateTimeField with valid inputs."""
        field = JalaliDateTimeField()
        
        test_cases = [
            "1403/01/01 14:30",
            "1403/1/1 14:30:45",
            "1403-01-01 14:30",
            "۱۴۰۳/۰۱/۰۱ ۱۴:۳۰",  # Persian digits
        ]
        
        for jalali_str in test_cases:
            result = field.to_python(jalali_str)
            self.assertIsInstance(result, datetime)
            self.assertTrue(timezone.is_aware(result))
            # Should be in UTC
            self.assertEqual(result.tzinfo, timezone.utc)
    
    def test_jalali_datetime_field_invalid_input(self):
        """Test JalaliDateTimeField with invalid inputs."""
        field = JalaliDateTimeField()
        
        invalid_inputs = [
            "1403/13/01 14:30",  # Invalid month
            "1403/01/01 25:30",  # Invalid hour
            "invalid datetime",
            "1403/01/01",  # Missing time part is actually valid (defaults to 00:00)
        ]
        
        for invalid_input in invalid_inputs:
            if invalid_input == "1403/01/01":
                # Date without time should work (defaults to midnight)
                result = field.to_python(invalid_input)
                self.assertIsInstance(result, datetime)
            elif invalid_input == "":
                # Empty string should return None
                result = field.to_python(invalid_input)
                self.assertIsNone(result)
            else:
                with self.assertRaises(ValidationError):
                    field.to_python(invalid_input)
    
    def test_jalali_datetime_field_prepare_value(self):
        """Test JalaliDateTimeField value preparation for display."""
        field = JalaliDateTimeField()
        
        # Test with Gregorian datetime
        gregorian_dt = timezone.make_aware(
            datetime(2024, 3, 20, 14, 30, 0),
            timezone.get_current_timezone()
        )
        prepared = field.prepare_value(gregorian_dt)
        self.assertIn("1403/01/01", prepared)
        self.assertIn("14:30", prepared)
        
        # Test with None
        self.assertEqual(field.prepare_value(None), "")


class JalaliWidgetsTest(TestCase):
    """Test Jalali form widgets."""
    
    def test_jalali_date_input_attrs(self):
        """Test JalaliDateInput widget attributes."""
        widget = JalaliDateInput()
        
        # Check default attributes
        self.assertIn('jalali-date-input', widget.attrs['class'])
        self.assertIn('data-jalali', widget.attrs)
        self.assertEqual(widget.attrs['data-jalali'], '1')
        self.assertEqual(widget.attrs['dir'], 'ltr')
        self.assertIn('1402/', widget.attrs['placeholder'])
    
    def test_jalali_date_input_media(self):
        """Test JalaliDateInput widget media files."""
        widget = JalaliDateInput()
        media = widget.media
        
        # Check CSS files
        self.assertIn('vendor/persian-datepicker/persian-datepicker.min.css', str(media))
        self.assertIn('css/jalali-widgets.css', str(media))
        
        # Check JS files
        self.assertIn('vendor/persian-date/persian-date.min.js', str(media))
        self.assertIn('vendor/persian-datepicker/persian-datepicker.min.js', str(media))
        self.assertIn('js/jalali-init.js', str(media))
    
    def test_jalali_datetime_input_attrs(self):
        """Test JalaliDateTimeInput widget attributes."""
        widget = JalaliDateTimeInput()
        
        # Check default attributes
        self.assertIn('jalali-datetime-input', widget.attrs['class'])
        self.assertIn('data-jalali', widget.attrs)
        self.assertEqual(widget.attrs['data-jalali'], '1')
        self.assertIn('data-timepicker', widget.attrs)
        self.assertEqual(widget.attrs['data-timepicker'], '1')
        self.assertEqual(widget.attrs['dir'], 'ltr')
        self.assertIn('14:30', widget.attrs['placeholder'])
    
    def test_widget_custom_attrs(self):
        """Test widgets with custom attributes."""
        custom_attrs = {
            'class': 'custom-class',
            'placeholder': 'Custom placeholder',
        }
        
        widget = JalaliDateInput(attrs=custom_attrs)
        
        # Should merge with default attrs
        self.assertIn('custom-class', widget.attrs['class'])
        self.assertIn('jalali-date-input', widget.attrs['class'])
        self.assertEqual(widget.attrs['placeholder'], 'Custom placeholder')
        self.assertEqual(widget.attrs['data-jalali'], '1')  # Default should remain
    
    def test_widget_template_names(self):
        """Test widget template names."""
        date_widget = JalaliDateInput()
        datetime_widget = JalaliDateTimeInput()
        
        self.assertEqual(date_widget.template_name, "core/widgets/jalali_date.html")
        self.assertEqual(datetime_widget.template_name, "core/widgets/jalali_datetime.html")


class JalaliFormIntegrationTest(TestCase):
    """Integration tests for Jalali forms."""
    
    def test_form_field_roundtrip(self):
        """Test that form fields handle roundtrip conversion correctly."""
        field = JalaliDateField()
        
        # Original Gregorian date
        original_date = date(2024, 3, 20)
        
        # Prepare for display (Gregorian -> Jalali string)
        jalali_str = field.prepare_value(original_date)
        self.assertEqual(jalali_str, "1403/01/01")
        
        # Parse back from form input (Jalali string -> Gregorian)
        parsed_date = field.to_python(jalali_str)
        self.assertEqual(parsed_date, original_date)
    
    def test_form_field_with_persian_digits(self):
        """Test form fields with Persian digit input."""
        field = JalaliDateField()
        
        # Input with Persian digits
        persian_input = "۱۴۰۳/۰۱/۰۱"
        result = field.to_python(persian_input)
        
        self.assertIsInstance(result, date)
        self.assertEqual(result, date(2024, 3, 20))
    
    def test_datetime_field_timezone_handling(self):
        """Test that datetime fields handle timezones correctly."""
        field = JalaliDateTimeField()
        
        # Parse Jalali datetime
        result = field.to_python("1403/01/01 14:30")
        
        # Should be timezone-aware and in UTC
        self.assertTrue(timezone.is_aware(result))
        self.assertEqual(result.tzinfo, timezone.utc)
        
        # Time should be adjusted for timezone
        # (This depends on DISPLAY_TIME_ZONE setting)
        self.assertIsInstance(result, datetime)

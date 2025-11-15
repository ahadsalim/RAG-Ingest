"""
Tests for Jalali template filters.
"""
from datetime import datetime, date
from django.test import TestCase
from django.template import Context, Template
from django.utils import timezone


class JalaliTemplateFiltersTest(TestCase):
    """Test Jalali template filters."""
    
    def setUp(self):
        """Set up test data."""
        self.test_date = date(2024, 3, 20)  # Nowruz 1403/01/01
        self.test_datetime = timezone.make_aware(
            datetime(2024, 3, 20, 14, 30, 0),
            timezone.get_current_timezone()
        )
    
    def test_jalali_filter(self):
        """Test the jalali template filter."""
        template = Template("{% load jalali %}{{ date_value|jalali }}")
        context = Context({'date_value': self.test_date})
        result = template.render(context)
        
        self.assertEqual(result, "1403/01/01")
    
    def test_jalali_datetime_filter(self):
        """Test the jalali_datetime template filter."""
        template = Template("{% load jalali %}{{ datetime_value|jalali_datetime }}")
        context = Context({'datetime_value': self.test_datetime})
        result = template.render(context)
        
        self.assertIn("1403/01/01", result)
        self.assertIn("14:30", result)
    
    def test_jalali_datetime_with_timezone(self):
        """Test jalali_datetime filter with timezone info."""
        template = Template("{% load jalali %}{{ datetime_value|jalali_datetime:True }}")
        context = Context({'datetime_value': self.test_datetime})
        result = template.render(context)
        
        self.assertIn("1403/01/01", result)
        self.assertIn("14:30", result)
        # Should include timezone info when requested
    
    def test_jalali_verbose_filter(self):
        """Test the jalali_verbose template filter."""
        template = Template("{% load jalali %}{{ date_value|jalali_verbose }}")
        context = Context({'date_value': self.test_date})
        result = template.render(context)
        
        self.assertIn("فروردین", result)  # Month name
        self.assertIn("۱۴۰۳", result)     # Persian year
    
    def test_persian_digits_filter(self):
        """Test the persian_digits template filter."""
        template = Template("{% load jalali %}{{ number|persian_digits }}")
        context = Context({'number': "123"})
        result = template.render(context)
        
        self.assertEqual(result, "۱۲۳")
    
    def test_english_digits_filter(self):
        """Test the english_digits template filter."""
        template = Template("{% load jalali %}{{ persian_number|english_digits }}")
        context = Context({'persian_number': "۱۲۳"})
        result = template.render(context)
        
        self.assertEqual(result, "123")
    
    def test_jalali_now_tag(self):
        """Test the jalali_now template tag."""
        template = Template("{% load jalali %}{% jalali_now %}")
        result = template.render(Context())
        
        # Should return current datetime in Jalali format
        self.assertRegex(result, r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}')
    
    def test_jalali_today_tag(self):
        """Test the jalali_today template tag."""
        template = Template("{% load jalali %}{% jalali_today %}")
        result = template.render(Context())
        
        # Should return current date in Jalali format
        self.assertRegex(result, r'\d{4}/\d{2}/\d{2}')
    
    def test_filters_with_none_values(self):
        """Test filters handle None values gracefully."""
        template = Template("""
            {% load jalali %}
            Date: {{ none_date|jalali }}
            DateTime: {{ none_datetime|jalali_datetime }}
            Verbose: {{ none_date|jalali_verbose }}
            Persian: {{ none_number|persian_digits }}
            English: {{ none_number|english_digits }}
        """)
        context = Context({
            'none_date': None,
            'none_datetime': None,
            'none_number': None,
        })
        result = template.render(context)
        
        # All should render empty strings, not error
        self.assertIn("Date:", result)
        self.assertIn("DateTime:", result)
        self.assertIn("Verbose:", result)
    
    def test_jalali_date_display_tag(self):
        """Test the jalali_date_display inclusion tag."""
        template = Template("""
            {% load jalali %}
            {% jalali_date_display date_value show_verbose=True %}
        """)
        context = Context({'date_value': self.test_date})
        result = template.render(context)
        
        # Should include the date display template
        self.assertIn("jalali-date-display", result)
    
    def test_jalali_datetime_display_tag(self):
        """Test the jalali_datetime_display inclusion tag."""
        template = Template("""
            {% load jalali %}
            {% jalali_datetime_display datetime_value show_timezone=True %}
        """)
        context = Context({'datetime_value': self.test_datetime})
        result = template.render(context)
        
        # Should include the datetime display template
        self.assertIn("jalali-datetime-display", result)
    
    def test_filter_chaining(self):
        """Test chaining multiple filters."""
        template = Template("{% load jalali %}{{ number|persian_digits|english_digits }}")
        context = Context({'number': "123"})
        result = template.render(context)
        
        # Should convert to Persian then back to English
        self.assertEqual(result, "123")
    
    def test_complex_template_usage(self):
        """Test complex template with multiple Jalali features."""
        template = Template("""
            {% load jalali %}
            <div class="date-info">
                <span class="date">{{ date_value|jalali }}</span>
                <span class="verbose">{{ date_value|jalali_verbose }}</span>
                <span class="datetime">{{ datetime_value|jalali_datetime }}</span>
                <span class="current">{% jalali_today %}</span>
                <span class="number">{{ "2024"|persian_digits }}</span>
            </div>
        """)
        context = Context({
            'date_value': self.test_date,
            'datetime_value': self.test_datetime,
        })
        result = template.render(context)
        
        # Check all components are present
        self.assertIn("1403/01/01", result)
        self.assertIn("فروردین", result)
        self.assertIn("14:30", result)
        self.assertIn("۲۰۲۴", result)
        self.assertIn("date-info", result)

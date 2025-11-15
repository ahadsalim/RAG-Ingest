"""
Unit tests for Jalali date forms functionality.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.forms import forms
from jalali_date.widgets import AdminJalaliDateWidget, AdminSplitJalaliDateTime
from jalali_date.fields import JalaliDateField, SplitJalaliDateTimeField
import jdatetime
from datetime import date, datetime

from ingest.apps.documents.forms import (
    InstrumentExpressionForm,
    InstrumentManifestationForm, 
    InstrumentRelationForm
)
from ingest.apps.documents.models import (
    InstrumentWork,
    InstrumentExpression,
    InstrumentManifestation,
    InstrumentRelation
)
from ingest.apps.masterdata.models import Jurisdiction, IssuingAuthority, Language


class JalaliFormsTestCase(TestCase):
    """Base test case with common setup for Jalali forms tests."""
    
    def setUp(self):
        """Set up test data."""
        # Create test jurisdiction
        self.jurisdiction = Jurisdiction.objects.create(
            name='تست حوزه قضایی',
            short_name='test'
        )
        
        # Create test issuing authority
        self.authority = IssuingAuthority.objects.create(
            name='مرجع تست',
            short_name='test_auth',
            uri='test://authority',
            jurisdiction=self.jurisdiction
        )
        
        # Create test language
        self.language = Language.objects.create(
            name='فارسی',
            code='fa'
        )
        
        # Create test work
        self.work = InstrumentWork.objects.create(
            title_official='قانون تست',
            doc_type='law',
            jurisdiction=self.jurisdiction,
            authority=self.authority,
            urn_lex='ir:test:law:2024-01-01:1'
        )


class InstrumentExpressionFormTest(JalaliFormsTestCase):
    """Test InstrumentExpressionForm with Jalali date support."""
    
    def test_form_has_jalali_date_field(self):
        """Test that the form has JalaliDateField for expression_date."""
        form = InstrumentExpressionForm()
        
        # Check that expression_date is a JalaliDateField
        self.assertIsInstance(form.fields['expression_date'], JalaliDateField)
        
        # Check that it uses AdminJalaliDateWidget
        self.assertIsInstance(form.fields['expression_date'].widget, AdminJalaliDateWidget)
    
    def test_jalali_date_conversion_to_gregorian(self):
        """Test that Jalali date input is converted to Gregorian for database storage."""
        # Jalali date: 1403/01/15 (should convert to 2024-04-03)
        form_data = {
            'work': self.work.id,
            'language': self.language.id,
            'consolidation_level': 'base',
            'expression_date': '1403/01/15'  # Jalali format
        }
        
        form = InstrumentExpressionForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Save the form and check the stored date
        expression = form.save()
        
        # The stored date should be Gregorian (2024-04-03)
        expected_gregorian_date = date(2024, 4, 3)
        self.assertEqual(expression.expression_date, expected_gregorian_date)
    
    def test_empty_jalali_date_field(self):
        """Test that empty date field is handled correctly."""
        form_data = {
            'work': self.work.id,
            'language': self.language.id,
            'consolidation_level': 'base',
            'expression_date': ''  # Empty date
        }
        
        form = InstrumentExpressionForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        expression = form.save()
        self.assertIsNone(expression.expression_date)


class InstrumentManifestationFormTest(JalaliFormsTestCase):
    """Test InstrumentManifestationForm with Jalali date support."""
    
    def setUp(self):
        super().setUp()
        # Create test expression
        self.expression = InstrumentExpression.objects.create(
            work=self.work,
            language=self.language,
            consolidation_level='base',
            expression_date=date(2024, 1, 1)
        )
    
    def test_form_has_jalali_date_fields(self):
        """Test that the form has JalaliDateField for date fields."""
        form = InstrumentManifestationForm()
        
        # Check date fields
        self.assertIsInstance(form.fields['publication_date'], JalaliDateField)
        self.assertIsInstance(form.fields['in_force_from'], JalaliDateField)
        self.assertIsInstance(form.fields['in_force_to'], JalaliDateField)
        
        # Check datetime field
        self.assertIsInstance(form.fields['retrieval_date'], SplitJalaliDateTimeField)
        
        # Check widgets
        self.assertIsInstance(form.fields['publication_date'].widget, AdminJalaliDateWidget)
        self.assertIsInstance(form.fields['in_force_from'].widget, AdminJalaliDateWidget)
        self.assertIsInstance(form.fields['in_force_to'].widget, AdminJalaliDateWidget)
        self.assertIsInstance(form.fields['retrieval_date'].widget, AdminSplitJalaliDateTime)
    
    def test_jalali_dates_conversion(self):
        """Test that multiple Jalali dates are converted correctly."""
        form_data = {
            'expr': self.expression.id,
            'publication_date': '1403/01/01',  # Should convert to 2024-03-20
            'in_force_from': '1403/01/15',     # Should convert to 2024-04-03
            'repeal_status': 'in_force'
        }
        
        form = InstrumentManifestationForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        manifestation = form.save()
        
        # Check converted dates
        self.assertEqual(manifestation.publication_date, date(2024, 3, 20))
        self.assertEqual(manifestation.in_force_from, date(2024, 4, 3))
    
    def test_repeal_validation_with_jalali_dates(self):
        """Test custom validation for repealed documents with Jalali dates."""
        # Test invalid case: repealed without in_force_to
        form_data = {
            'expr': self.expression.id,
            'publication_date': '1403/01/01',
            'repeal_status': 'repealed',  # Repealed but no in_force_to
        }
        
        form = InstrumentManifestationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('in_force_to', form.errors)
        
        # Test valid case: repealed with in_force_to
        form_data['in_force_to'] = '1403/06/01'  # Add end date
        
        form = InstrumentManifestationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        manifestation = form.save()
        self.assertEqual(manifestation.in_force_to, date(2024, 8, 22))  # Converted date


class InstrumentRelationFormTest(JalaliFormsTestCase):
    """Test InstrumentRelationForm with Jalali date support."""
    
    def setUp(self):
        super().setUp()
        # Create second work for relation
        self.work2 = InstrumentWork.objects.create(
            title_official='قانون تست دوم',
            doc_type='regulation',
            jurisdiction=self.jurisdiction,
            authority=self.authority,
            urn_lex='ir:test:regulation:2024-01-01:2'
        )
    
    def test_form_has_jalali_date_field(self):
        """Test that the form has JalaliDateField for effective_date."""
        form = InstrumentRelationForm()
        
        self.assertIsInstance(form.fields['effective_date'], JalaliDateField)
        self.assertIsInstance(form.fields['effective_date'].widget, AdminJalaliDateWidget)
    
    def test_jalali_effective_date_conversion(self):
        """Test that Jalali effective_date is converted correctly."""
        form_data = {
            'from_work': self.work.id,
            'to_work': self.work2.id,
            'relation_type': 'amends',
            'effective_date': '1403/02/01'  # Should convert to 2024-04-20
        }
        
        form = InstrumentRelationForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        relation = form.save()
        self.assertEqual(relation.effective_date, date(2024, 4, 20))
    
    def test_empty_effective_date(self):
        """Test that empty effective_date is handled correctly."""
        form_data = {
            'from_work': self.work.id,
            'to_work': self.work2.id,
            'relation_type': 'references',
            'effective_date': ''  # Empty date
        }
        
        form = InstrumentRelationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        relation = form.save()
        self.assertIsNone(relation.effective_date)


class JalaliDateWidgetRenderingTest(TestCase):
    """Test Jalali date widget rendering and attributes."""
    
    def test_jalali_date_widget_attributes(self):
        """Test that Jalali date widgets have correct attributes."""
        form = InstrumentExpressionForm()
        
        # Check widget attributes
        widget = form.fields['expression_date'].widget
        self.assertIn('placeholder', widget.attrs)
        self.assertEqual(widget.attrs['placeholder'], 'YYYY/MM/DD')
        self.assertIn('class', widget.attrs)
        self.assertEqual(widget.attrs['class'], 'form-control')
    
    def test_manifestation_form_widget_attributes(self):
        """Test that all date widgets in manifestation form have correct attributes."""
        form = InstrumentManifestationForm()
        
        date_fields = ['publication_date', 'in_force_from', 'in_force_to']
        
        for field_name in date_fields:
            widget = form.fields[field_name].widget
            self.assertIn('placeholder', widget.attrs)
            self.assertEqual(widget.attrs['placeholder'], 'YYYY/MM/DD')
            self.assertIn('class', widget.attrs)
            self.assertEqual(widget.attrs['class'], 'form-control')
    
    def test_datetime_widget_attributes(self):
        """Test that datetime widget has correct attributes."""
        form = InstrumentManifestationForm()
        
        widget = form.fields['retrieval_date'].widget
        self.assertIn('class', widget.attrs)
        self.assertEqual(widget.attrs['class'], 'form-control')


class JalaliDateConversionTest(TestCase):
    """Test Jalali to Gregorian date conversion accuracy."""
    
    def test_specific_jalali_dates(self):
        """Test conversion of specific Jalali dates to Gregorian."""
        test_cases = [
            ('1403/01/01', date(2024, 3, 20)),  # Nowruz 1403
            ('1403/06/31', date(2024, 9, 21)),  # End of summer 1403
            ('1403/12/29', date(2025, 3, 19)),  # End of year 1403 (normal year)
            ('1400/01/01', date(2021, 3, 21)),  # Nowruz 1400
        ]
        
        for jalali_str, expected_gregorian in test_cases:
            with self.subTest(jalali_date=jalali_str):
                # Create a form with the Jalali date
                form_data = {'expression_date': jalali_str}
                field = JalaliDateField()
                
                # The field should convert the Jalali string to Gregorian date
                converted_date = field.to_python(jalali_str)
                self.assertEqual(converted_date, expected_gregorian)

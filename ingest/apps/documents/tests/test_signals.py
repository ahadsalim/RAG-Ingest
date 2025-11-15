"""Tests for document processing signals."""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase

from ..models import LegalUnit
from ..processing.signals import track_legal_unit_changes, process_legal_unit_on_save


class TestLegalUnitSignals(TestCase):
    """Test signal handlers for LegalUnit processing."""

    def setUp(self):
        """Set up test data."""
        self.legal_unit_data = {
            'path_label': 'Test Unit',
            'content': 'Original content',
            'unit_type': 'article',
            'position': 1
        }

    @patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay')
    def test_creating_legal_unit_enqueues_task(self, mock_delay):
        """Test A: Creating a LegalUnit enqueues process_legal_unit_chunks with the created id."""
        # Create a new LegalUnit
        legal_unit = LegalUnit.objects.create(**self.legal_unit_data)
        
        # Verify the task was called with the correct ID
        mock_delay.assert_called_once_with(str(legal_unit.id))

    @patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay')
    def test_updating_content_enqueues_task(self, mock_delay):
        """Test B: Updating LegalUnit.content enqueues the task."""
        # Create a LegalUnit first
        legal_unit = LegalUnit.objects.create(**self.legal_unit_data)
        mock_delay.reset_mock()  # Clear the creation call
        
        # Update the content
        legal_unit.content = 'Updated content'
        legal_unit.save()
        
        # Verify the task was called again due to content change
        mock_delay.assert_called_once_with(str(legal_unit.id))

    @patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay')
    def test_updating_non_content_field_does_not_enqueue(self, mock_delay):
        """Test C: Updating a non-content field does NOT enqueue."""
        # Create a LegalUnit first
        legal_unit = LegalUnit.objects.create(**self.legal_unit_data)
        mock_delay.reset_mock()  # Clear the creation call
        
        # Update a non-content field
        legal_unit.path_label = 'Updated Label'
        legal_unit.save()
        
        # Verify the task was NOT called
        mock_delay.assert_not_called()

    def test_pre_save_signal_tracks_content_changes_new_instance(self):
        """Test pre_save signal correctly identifies new instances."""
        legal_unit = LegalUnit(**self.legal_unit_data)
        
        # Simulate pre_save signal
        track_legal_unit_changes(LegalUnit, legal_unit)
        
        # New instance should have _content_changed = True
        self.assertTrue(legal_unit._content_changed)

    def test_pre_save_signal_tracks_content_changes_existing_instance(self):
        """Test pre_save signal correctly identifies content changes in existing instances."""
        # Create and save a LegalUnit
        legal_unit = LegalUnit.objects.create(**self.legal_unit_data)
        
        # Modify content
        legal_unit.content = 'Modified content'
        
        # Simulate pre_save signal
        track_legal_unit_changes(LegalUnit, legal_unit)
        
        # Should detect content change
        self.assertTrue(legal_unit._content_changed)

    def test_pre_save_signal_no_content_change(self):
        """Test pre_save signal correctly identifies when content hasn't changed."""
        # Create and save a LegalUnit
        legal_unit = LegalUnit.objects.create(**self.legal_unit_data)
        
        # Modify non-content field only
        legal_unit.path_label = 'Modified label'
        
        # Simulate pre_save signal
        track_legal_unit_changes(LegalUnit, legal_unit)
        
        # Should not detect content change
        self.assertFalse(legal_unit._content_changed)

    @patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay')
    def test_post_save_signal_respects_content_changed_flag(self, mock_delay):
        """Test post_save signal only processes when content changed or created."""
        legal_unit = LegalUnit(**self.legal_unit_data)
        legal_unit.id = 1  # Simulate existing instance
        
        # Test with content changed
        legal_unit._content_changed = True
        process_legal_unit_on_save(LegalUnit, legal_unit, created=False)
        mock_delay.assert_called_once_with(str(legal_unit.id))
        
        mock_delay.reset_mock()
        
        # Test without content changed
        legal_unit._content_changed = False
        process_legal_unit_on_save(LegalUnit, legal_unit, created=False)
        mock_delay.assert_not_called()

    @patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay')
    def test_post_save_signal_always_processes_new_instances(self, mock_delay):
        """Test post_save signal always processes new instances regardless of _content_changed."""
        legal_unit = LegalUnit(**self.legal_unit_data)
        legal_unit.id = 1
        legal_unit._content_changed = False  # Even if False, should process because created=True
        
        process_legal_unit_on_save(LegalUnit, legal_unit, created=True)
        mock_delay.assert_called_once_with(str(legal_unit.id))

    def test_integration_full_workflow(self):
        """Integration test: Full workflow from creation to update."""
        with patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay') as mock_delay:
            # Create new instance
            legal_unit = LegalUnit.objects.create(**self.legal_unit_data)
            self.assertEqual(mock_delay.call_count, 1)
            
            # Update content - should trigger processing
            mock_delay.reset_mock()
            legal_unit.content = 'New content'
            legal_unit.save()
            self.assertEqual(mock_delay.call_count, 1)
            
            # Update non-content field - should NOT trigger processing
            mock_delay.reset_mock()
            legal_unit.path_label = 'New label'
            legal_unit.save()
            self.assertEqual(mock_delay.call_count, 0)


@pytest.mark.django_db
class TestLegalUnitSignalsPytest:
    """Pytest version of signal tests for additional coverage."""
    
    @pytest.fixture
    def legal_unit_data(self):
        return {
            'path_label': 'Test Unit',
            'content': 'Original content',
            'unit_type': 'article',
            'position': 1
        }

    @patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay')
    def test_multiple_saves_same_content_only_processes_once(self, mock_delay, legal_unit_data):
        """Test that saving the same content multiple times doesn't trigger unnecessary processing."""
        # Create instance
        legal_unit = LegalUnit.objects.create(**legal_unit_data)
        mock_delay.reset_mock()
        
        # Save without changes multiple times
        legal_unit.save()
        legal_unit.save()
        legal_unit.save()
        
        # Should not trigger any processing calls
        mock_delay.assert_not_called()

    @patch('ingest.apps.documents.processing.signals.process_legal_unit_chunks.delay')
    def test_exception_handling_in_pre_save(self, mock_delay, legal_unit_data):
        """Test that pre_save signal handles DoesNotExist exceptions gracefully."""
        legal_unit = LegalUnit(**legal_unit_data)
        legal_unit.pk = 999999  # Non-existent ID
        
        # Should not raise exception and should set _content_changed to True
        track_legal_unit_changes(LegalUnit, legal_unit)
        
        self.assertTrue(legal_unit._content_changed)

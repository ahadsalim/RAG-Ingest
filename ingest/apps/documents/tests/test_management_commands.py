"""Tests for management commands in the documents app."""
import sys
from io import StringIO
from unittest.mock import patch, MagicMock, call
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from ingest.apps.documents.models import Document, LegalUnit, Chunk


class TestProcessChunksCommand(TestCase):
    """Test the process_chunks management command."""

    @classmethod
    def setUpTestData(cls):
        """Set up test data for all test methods."""
        cls.document = Document.objects.create(
            title="Test Document",
            description="Test Description",
            status=Document.Status.PUBLISHED,
        )
        cls.legal_unit = LegalUnit.objects.create(
            title="Test Legal Unit",
            document=cls.document,
            content="This is a test legal unit content. " * 10,  # Make it longer for chunking
            order=1,
        )
        
        # Create a second document with multiple units
        cls.document2 = Document.objects.create(
            title="Another Test Document",
            description="Another Test Description",
            status=Document.Status.PUBLISHED,
        )
        cls.legal_unit2a = LegalUnit.objects.create(
            title="First Unit",
            document=cls.document2,
            content="First unit content. " * 20,
            order=1,
        )
        cls.legal_unit2b = LegalUnit.objects.create(
            title="Second Unit",
            document=cls.document2,
            content="Second unit content. " * 20,
            order=2,
        )
    
    def setUp(self):
        """Set up before each test method."""
        self.stdout = StringIO()
        self.stderr = StringIO()
        sys.stdout = self.stdout
        sys.stderr = self.stderr

    def test_process_specific_document(self):
        """Test processing a specific document by ID."""
        with patch(
            'ingest.apps.documents.management.commands.process_chunks.get_chunk_processor'
        ) as mock_get_processor:
            # Set up mock processor
            mock_processor = MagicMock()
            mock_processor.process_document.return_value = {
                'success': True,
                'chunks_created': 2,
                'chunks_skipped': 0,
                'chunks_failed': 0,
                'unit_results': {
                    str(self.legal_unit.id): {
                        'success': True,
                        'chunks_created': 2,
                        'chunks_skipped': 0,
                        'chunks_failed': 0,
                        'error': None,
                    }
                }
            }
            mock_get_processor.return_value = mock_processor

            # Call the command
            call_command(
                'process_chunks',
                f'--document-id={self.document.id}',
                '--chunk-size=50',
                '--chunk-overlap=10',
                stdout=self.stdout,
                stderr=self.stderr
            )

            # Verify the processor was called with the correct document ID
            mock_processor.process_document.assert_called_once_with(
                str(self.document.id),
                chunk_size=50,
                chunk_overlap=10
            )
            
            # Verify output
            output = self.stdout.getvalue()
            self.assertIn(f'Processing document: {self.document.id}', output)
            self.assertIn('Successfully processed document', output)
            self.assertIn('Chunks created: 2', output)

    def test_process_specific_unit(self):
        """Test processing a specific legal unit by ID."""
        with patch(
            'ingest.apps.documents.management.commands.process_chunks.get_chunk_processor'
        ) as mock_get_processor:
            # Set up mock processor
            mock_processor = MagicMock()
            mock_processor.process_legal_unit.return_value = {
                'success': True,
                'chunks_created': 3,
                'chunks_skipped': 0,
                'chunks_failed': 0,
                'error': None
            }
            mock_get_processor.return_value = mock_processor

            # Call the command with verbosity=2 for more detailed output
            call_command(
                'process_chunks',
                f'--unit-id={self.legal_unit.id}',
                '--chunk-size=30',
                '--chunk-overlap=5',
                verbosity=2,
                stdout=self.stdout,
                stderr=self.stderr
            )

            # Verify the processor was called with the correct unit ID and chunking params
            mock_processor.process_legal_unit.assert_called_once_with(
                str(self.legal_unit.id),
                chunk_size=30,
                chunk_overlap=5
            )
            
            # Verify verbose output
            output = self.stdout.getvalue()
            self.assertIn(f'Processing legal unit: {self.legal_unit.id}', output)
            self.assertIn('Chunks created: 3', output)

    def test_process_all_documents(self):
        """Test processing all documents in batches."""
        with patch(
            'ingest.apps.documents.management.commands.process_chunks.get_chunk_processor'
        ) as mock_get_processor:
            # Set up mock processor
            mock_processor = MagicMock()
            
            # First call for document 1
            def process_document_side_effect(doc_id, **kwargs):
                if doc_id == str(self.document.id):
                    return {
                        'success': True,
                        'chunks_created': 2,
                        'chunks_skipped': 0,
                        'chunks_failed': 0,
                        'unit_results': {
                            str(self.legal_unit.id): {
                                'success': True,
                                'chunks_created': 2,
                                'chunks_skipped': 0,
                                'chunks_failed': 0,
                                'error': None,
                            }
                        }
                    }
                elif doc_id == str(self.document2.id):
                    return {
                        'success': True,
                        'chunks_created': 4,
                        'chunks_skipped': 0,
                        'chunks_failed': 0,
                        'unit_results': {
                            str(self.legal_unit2a.id): {
                                'success': True,
                                'chunks_created': 3,
                                'chunks_skipped': 0,
                                'chunks_failed': 0,
                                'error': None,
                            },
                            str(self.legal_unit2b.id): {
                                'success': True,
                                'chunks_created': 1,
                                'chunks_skipped': 0,
                                'chunks_failed': 0,
                                'error': None,
                            },
                        }
                    }
                return {'success': False, 'error': 'Document not found'}
            
            mock_processor.process_document.side_effect = process_document_side_effect
            mock_get_processor.return_value = mock_processor

            # Call the command with --all flag and batch size of 1
            call_command(
                'process_chunks',
                '--all',
                '--batch-size=1',
                '--chunk-size=50',
                '--chunk-overlap=10',
                stdout=self.stdout,
                stderr=self.stderr
            )

            # Verify the processor was called for each document
            expected_calls = [
                call(str(self.document.id), chunk_size=50, chunk_overlap=10),
                call(str(self.document2.id), chunk_size=50, chunk_overlap=10),
            ]
            mock_processor.process_document.assert_has_calls(expected_calls, any_order=True)
            
            # Verify output contains summary information
            output = self.stdout.getvalue()
            self.assertIn('Processing all documents in batches of 1', output)
            self.assertIn('Total documents processed: 2', output)
            self.assertIn('Total chunks created: 6', output)
            self.assertIn('Batch 1/2', output)
            self.assertIn('Batch 2/2', output)

    def test_invalid_document_id(self):
        """Test handling of invalid document ID."""
        invalid_id = str(uuid4())
        with pytest.raises(CommandError) as exc_info:
            call_command(
                'process_chunks', 
                f'--document-id={invalid_id}',
                stdout=self.stdout,
                stderr=self.stderr
            )
        assert f'Document {invalid_id} not found' in str(exc_info.value)
        
        # Verify error is also in stderr
        error_output = self.stderr.getvalue()
        self.assertIn('Error', error_output)
        self.assertIn('not found', error_output)

    def test_invalid_unit_id(self):
        """Test handling of invalid legal unit ID."""
        invalid_id = str(uuid4())
        with pytest.raises(CommandError) as exc_info:
            call_command(
                'process_chunks', 
                f'--unit-id={invalid_id}',
                stdout=self.stdout,
                stderr=self.stderr
            )
        assert f'Legal unit {invalid_id} not found' in str(exc_info.value)
        
        # Verify error is also in stderr
        error_output = self.stderr.getvalue()
        self.assertIn('Error', error_output)
        self.assertIn('not found', error_output)

    def test_missing_required_argument(self):
        """Test that an error is raised when no required argument is provided."""
        with pytest.raises(CommandError) as exc_info:
            call_command(
                'process_chunks',
                stdout=self.stdout,
                stderr=self.stderr
            )
        error_msg = str(exc_info.value)
        self.assertIn('Please specify --document-id, --unit-id, or --all', error_msg)
        
        # Verify help is shown in stderr
        error_output = self.stderr.getvalue()
        self.assertIn('usage:', error_output.lower())
        self.assertIn('--document-id', error_output)
        self.assertIn('--unit-id', error_output)
        self.assertIn('--all', error_output)

    @patch('ingest.apps.documents.management.commands.process_chunks.django')
    def test_django_not_available(self, mock_django):
        """Test behavior when Django is not properly configured."""
        mock_django.get.return_value = None
        with pytest.raises(SystemExit):
            call_command(
                'process_chunks', 
                '--document-id=123',
                stdout=self.stdout,
                stderr=self.stderr
            )
        
        # Verify error message in stderr
        error_output = self.stderr.getvalue()
        self.assertIn('Django is not properly configured', error_output)

    def test_processor_error_handling(self):
        """Test error handling when processor raises an exception."""
        with patch(
            'ingest.apps.documents.management.commands.process_chunks.get_chunk_processor'
        ) as mock_get_processor:
            # Set up mock processor to raise an exception
            mock_processor = MagicMock()
            error_message = 'Test error: Something went wrong during processing'
            mock_processor.process_document.side_effect = Exception(error_message)
            mock_get_processor.return_value = mock_processor

            # Call the command and capture output
            with self.assertRaises(SystemExit):
                call_command(
                    'process_chunks',
                    f'--document-id={self.document.id}',
                    stdout=self.stdout,
                    stderr=self.stderr
                )

            # Verify the error was logged
            mock_processor.process_document.assert_called_once_with(
                str(self.document.id),
                chunk_size=None,
                chunk_overlap=None
            )
            
            # Verify error output
            error_output = self.stderr.getvalue()
            self.assertIn('Error processing document', error_output)
            self.assertIn(error_message, error_output)
    
    def test_dry_run_mode(self):
        """Test dry run mode with --dry-run flag."""
        with patch(
            'ingest.apps.documents.management.commands.process_chunks.get_chunk_processor'
        ) as mock_get_processor:
            # Set up mock processor
            mock_processor = MagicMock()
            mock_processor.process_document.return_value = {
                'success': True,
                'chunks_created': 2,
                'chunks_skipped': 0,
                'chunks_failed': 0,
                'unit_results': {
                    str(self.legal_unit.id): {
                        'success': True,
                        'chunks_created': 2,
                        'chunks_skipped': 0,
                        'chunks_failed': 0,
                        'error': None,
                    }
                }
            }
            mock_get_processor.return_value = mock_processor

            # Call the command with --dry-run flag
            call_command(
                'process_chunks',
                f'--document-id={self.document.id}',
                '--dry-run',
                stdout=self.stdout,
                stderr=self.stderr
            )

            # Verify the processor was called with dry_run=True
            mock_processor.process_document.assert_called_once_with(
                str(self.document.id),
                chunk_size=None,
                chunk_overlap=None,
                dry_run=True
            )
            
            # Verify dry run message in output
            output = self.stdout.getvalue()
            self.assertIn('DRY RUN MODE - No changes will be saved', output)
            self.assertIn('Would create 2 chunks', output)
    
    @override_settings(DEBUG=True)
    def test_debug_mode(self):
        """Test debug mode output when DEBUG=True."""
        with patch(
            'ingest.apps.documents.management.commands.process_chunks.get_chunk_processor'
        ) as mock_get_processor, \
             patch('sys.exc_info') as mock_exc_info:
            # Set up mock processor to raise an exception
            mock_processor = MagicMock()
            error = ValueError('Test debug error')
            mock_processor.process_document.side_effect = error
            mock_get_processor.return_value = mock_processor
            
            # Set up traceback for debug output
            mock_exc_info.return_value = (type(error), error, None)

            # Call the command with --document-id
            with self.assertRaises(SystemExit):
                call_command(
                    'process_chunks',
                    f'--document-id={self.document.id}',
                    stdout=self.stdout,
                    stderr=self.stderr
                )
            
            # Verify debug output includes traceback
            error_output = self.stderr.getvalue()
            self.assertIn('DEBUG: Exception details:', error_output)
            self.assertIn('Test debug error', error_output)
    
    def test_verbosity_levels(self):
        """Test different verbosity levels for command output."""
        with patch(
            'ingest.apps.documents.management.commands.process_chunks.get_chunk_processor'
        ) as mock_get_processor:
            # Set up mock processor
            mock_processor = MagicMock()
            mock_processor.process_document.return_value = {
                'success': True,
                'chunks_created': 2,
                'chunks_skipped': 1,
                'chunks_failed': 0,
                'unit_results': {
                    str(self.legal_unit.id): {
                        'success': True,
                        'chunks_created': 2,
                        'chunks_skipped': 1,
                        'chunks_failed': 0,
                        'error': None,
                    }
                }
            }
            mock_get_processor.return_value = mock_processor
            
            # Test verbosity=0 (quiet)
            call_command(
                'process_chunks',
                f'--document-id={self.document.id}',
                verbosity=0,
                stdout=self.stdout,
                stderr=self.stderr
            )
            output = self.stdout.getvalue()
            self.assertEqual(output.strip(), '')  # No output at verbosity 0
            
            # Reset stdout
            self.stdout = StringIO()
            sys.stdout = self.stdout
            
            # Test verbosity=1 (normal)
            call_command(
                'process_chunks',
                f'--document-id={self.document.id}',
                verbosity=1,
                stdout=self.stdout,
                stderr=self.stderr
            )
            output = self.stdout.getvalue()
            self.assertIn('Processing document:', output)
            self.assertIn('Successfully processed document', output)
            self.assertNotIn('Chunk details', output)  # No verbose details
            
            # Reset stdout
            self.stdout = StringIO()
            sys.stdout = self.stdout
            
            # Test verbosity=2 (verbose)
            call_command(
                'process_chunks',
                f'--document-id={self.document.id}',
                verbosity=2,
                stdout=self.stdout,
                stderr=self.stderr
            )
            output = self.stdout.getvalue()
            self.assertIn('Processing document:', output)
            self.assertIn('Successfully processed document', output)
            self.assertIn('Chunk details:', output)  # Verbose details included
            self.assertIn('chunks_created: 2', output)
            self.assertIn('chunks_skipped: 1', output)
    
    def tearDown(self):
        """Clean up after each test method."""
        # Restore stdout and stderr
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        super().tearDown()

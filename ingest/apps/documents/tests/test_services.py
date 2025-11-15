"""Tests for document processing services."""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase

from ingest.apps.documents.models import Document, LegalUnit
from ingest.apps.documents.processing import ChunkProcessingService


class TestChunkProcessingService(TestCase):
    """Test the ChunkProcessingService class."""

    def setUp(self):
        ""Set up test data."""
        self.document = Document.objects.create(
            title="Test Document",
            description="Test Description",
        )
        self.legal_unit = LegalUnit.objects.create(
            title="Test Legal Unit",
            document=self.document,
            content="This is a test legal unit content.",
            order=1,
        )
        self.service = ChunkProcessingService()

    def test_process_document(self):
        ""Test processing a document."""
        with patch.object(self.service, 'process_legal_unit') as mock_process_unit:
            mock_process_unit.return_value = {
                'success': True,
                'chunks_created': 1,
                'chunks_skipped': 0,
                'chunks_failed': 0,
            }
            
            result = self.service.process_document(str(self.document.id))
            
            self.assertTrue(result['success'])
            self.assertEqual(len(result['unit_results']), 1)
            self.assertEqual(result['chunks_created'], 1)
            self.assertEqual(result['chunks_skipped'], 0)
            self.assertEqual(result['chunks_failed'], 0)
            mock_process_unit.assert_called_once_with(str(self.legal_unit.id))

    def test_process_legal_unit(self):
        ""Test processing a legal unit."""
        with patch('ingest.apps.documents.processing.chunking.split_into_chunks') as mock_split:
            mock_split.return_value = ["Chunk 1", "Chunk 2"]
            
            result = self.service.process_legal_unit(str(self.legal_unit.id))
            
            self.assertTrue(result['success'])
            self.assertEqual(result['chunks_created'], 2)
            self.assertEqual(result['chunks_skipped'], 0)
            self.assertEqual(result['chunks_failed'], 0)
            mock_split.assert_called_once_with(
                self.legal_unit.content,
                chunk_size=self.service.chunk_size,
                chunk_overlap=self.service.chunk_overlap
            )

    def test_process_legal_unit_with_empty_content(self):
        ""Test processing a legal unit with empty content."""
        self.legal_unit.content = ""
        self.legal_unit.save()
        
        result = self.service.process_legal_unit(str(self.legal_unit.id))
        
        self.assertFalse(result['success'])
        self.assertEqual(result['chunks_created'], 0)
        self.assertEqual(result['chunks_skipped'], 0)
        self.assertEqual(result['chunks_failed'], 0)
        self.assertIn('error', result)

    @patch('ingest.apps.documents.processing.chunking.split_into_chunks')
    def test_process_legal_unit_with_chunk_creation_error(self, mock_split):
        ""Test handling of chunk creation errors."""
        mock_split.return_value = ["Chunk 1"]
        with patch.object(self.service, '_create_chunk') as mock_create_chunk:
            mock_create_chunk.return_value = None
            
            result = self.service.process_legal_unit(str(self.legal_unit.id))
            
            self.assertFalse(result['success'])
            self.assertEqual(result['chunks_created'], 0)
            self.assertEqual(result['chunks_skipped'], 0)
            self.assertEqual(result['chunks_failed'], 1)

    def test_create_chunk(self):
        ""Test creating a chunk."""
        from ingest.apps.documents.models import Chunk
        
        chunk = self.service._create_chunk(
            legal_unit=self.legal_unit,
            content="Test chunk content",
            order=1,
            metadata={"key": "value"}
        )
        
        self.assertIsNotNone(chunk)
        self.assertEqual(chunk.content, "Test chunk content")
        self.assertEqual(chunk.order, 1)
        self.assertEqual(chunk.metadata, {"key": "value"})
        self.assertEqual(chunk.legal_unit, self.legal_unit)

    def test_get_chunk_processor(self):
        ""Test getting a chunk processor instance."""
        from ingest.apps.documents.processing import get_chunk_processor
        
        processor = get_chunk_processor()
        
        self.assertIsInstance(processor, ChunkProcessingService)
        self.assertEqual(processor.chunk_size, 1000)  # Default chunk size
        self.assertEqual(processor.chunk_overlap, 100)  # Default overlap

    @patch('ingest.apps.documents.processing.chunking.ChunkProcessingService')
    def test_get_chunk_processor_with_custom_params(self, mock_service_class):
        ""Test getting a chunk processor with custom parameters."""
        from ingest.apps.documents.processing import get_chunk_processor
        
        mock_instance = MagicMock()
        mock_service_class.return_value = mock_instance
        
        processor = get_chunk_processor(chunk_size=500, chunk_overlap=50)
        
        mock_service_class.assert_called_once_with(chunk_size=500, chunk_overlap=50)
        self.assertEqual(processor, mock_instance)


class TestChunkProcessingServiceIntegration(TestCase):
    """Integration tests for ChunkProcessingService with database."""
    
    def setUp(self):
        ""Set up test data."""
        self.document = Document.objects.create(
            title="Test Document",
            description="Test Description",
        )
        self.legal_unit = LegalUnit.objects.create(
            title="Test Legal Unit",
            document=self.document,
            content="This is a test legal unit content. It should be split into chunks." * 100,
            order=1,
        )
        self.service = ChunkProcessingService(chunk_size=100, chunk_overlap=20)
    
    def test_integration_process_document(self):
        ""Test processing a document end-to-end."""
        from ingest.apps.documents.models import Chunk
        
        result = self.service.process_document(str(self.document.id))
        
        self.assertTrue(result['success'])
        self.assertGreater(result['chunks_created'], 0)
        
        # Verify chunks were created in the database
        chunks = Chunk.objects.filter(legal_unit=self.legal_unit)
        self.assertEqual(chunks.count(), result['chunks_created'])
        
        # Verify chunk content
        for i, chunk in enumerate(chunks):
            self.assertIsNotNone(chunk.content)
            self.assertEqual(chunk.order, i + 1)
            self.assertIn('chunk_number', chunk.metadata)
            self.assertEqual(chunk.metadata['chunk_number'], i + 1)
    
    def test_integration_process_legal_unit(self):
        ""Test processing a legal unit end-to-end."""
        from ingest.apps.documents.models import Chunk
        
        result = self.service.process_legal_unit(str(self.legal_unit.id))
        
        self.assertTrue(result['success'])
        self.assertGreater(result['chunks_created'], 0)
        
        # Verify chunks were created in the database
        chunks = Chunk.objects.filter(legal_unit=self.legal_unit)
        self.assertEqual(chunks.count(), result['chunks_created'])
        
        # Verify chunk content
        for i, chunk in enumerate(chunks):
            self.assertIsNotNone(chunk.content)
            self.assertEqual(chunk.order, i + 1)
            self.assertIn('chunk_number', chunk.metadata)
            self.assertEqual(chunk.metadata['chunk_number'], i + 1)

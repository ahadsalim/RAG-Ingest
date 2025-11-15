"""
Tests for embedding backends.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from django.test import TestCase, override_settings

from ingest.apps.embeddings.backends.base import EmbeddingBackend, EmbeddingResult, EmbeddingError
from ingest.apps.embeddings.backends.factory import get_backend, validate_provider_config
from ingest.apps.embeddings.backends.hakim_http import HakimHTTP
from ingest.apps.embeddings.backends.sbert_hf import SBertHF


class TestEmbeddingBackendBase(TestCase):
    """Test the base embedding backend functionality."""
    
    def test_normalize_vectors(self):
        """Test vector normalization."""
        class TestBackend(EmbeddingBackend):
            def embed(self, texts, *, task=None):
                return EmbeddingResult([], "test", 0)
            def model_id(self):
                return "test"
            def default_dim(self):
                return None
            def supports_dual_encoder(self):
                return False
        
        backend = TestBackend()
        
        # Test normal vector
        vectors = [[3.0, 4.0]]  # Length = 5
        normalized = backend.normalize_vectors(vectors)
        expected = [[0.6, 0.8]]  # 3/5, 4/5
        
        np.testing.assert_array_almost_equal(normalized[0], expected[0], decimal=5)
    
    def test_validate_texts(self):
        """Test text validation."""
        class TestBackend(EmbeddingBackend):
            def embed(self, texts, *, task=None):
                return EmbeddingResult([], "test", 0)
            def model_id(self):
                return "test"
            def default_dim(self):
                return None
            def supports_dual_encoder(self):
                return False
        
        backend = TestBackend()
        
        # Valid texts
        texts = ["Hello", "World"]
        validated = backend.validate_texts(texts)
        self.assertEqual(validated, ["Hello", "World"])
        
        # Empty texts should raise error
        with self.assertRaises(ValueError):
            backend.validate_texts([])
        
        # All empty strings should raise error
        with self.assertRaises(ValueError):
            backend.validate_texts(["", "  ", ""])


class TestBackendFactory(TestCase):
    """Test the backend factory."""
    
    @override_settings(EMBEDDING_PROVIDER='hakim')
    @patch.dict('os.environ', {'EMBEDDING_HAKIM_API_URL': 'http://test.com'})
    def test_get_hakim_backend(self):
        """Test getting Hakim backend."""
        backend = get_backend()
        self.assertIsInstance(backend, HakimHTTP)
    
    @override_settings(EMBEDDING_PROVIDER='sbert')
    @patch.dict('os.environ', {'EMBEDDING_SBERT_MODEL_NAME': 'test-model'})
    def test_get_sbert_backend(self):
        """Test getting SBERT backend."""
        backend = get_backend()
        self.assertIsInstance(backend, SBertHF)
    
    def test_invalid_provider(self):
        """Test invalid provider raises error."""
        with self.assertRaises(Exception):
            get_backend('invalid_provider')
    
    def test_validate_provider_config(self):
        """Test provider configuration validation."""
        # Test Hakim validation
        with patch.dict('os.environ', {'EMBEDDING_HAKIM_API_URL': 'http://test.com'}):
            validation = validate_provider_config('hakim')
            self.assertTrue(validation['valid'])
        
        # Test missing config
        with patch.dict('os.environ', {}, clear=True):
            validation = validate_provider_config('hakim')
            self.assertFalse(validation['valid'])
            self.assertIn('EMBEDDING_HAKIM_API_URL', validation['missing_config'])


class TestHakimBackend(TestCase):
    """Test Hakim HTTP backend."""
    
    def setUp(self):
        """Set up test environment."""
        self.patcher = patch.dict('os.environ', {
            'EMBEDDING_HAKIM_API_URL': 'http://test-hakim.com',
            'EMBEDDING_HAKIM_API_KEY': 'test-key',
            'EMBEDDING_HAKIM_MODEL_NAME': 'test-hakim'
        })
        self.patcher.start()
    
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
    
    @patch('requests.Session.post')
    def test_embed_success(self, mock_post):
        """Test successful embedding."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'embeddings': [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
            'usage': {'tokens': 10, 'api_calls': 1}
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        
        backend = HakimHTTP()
        result = backend.embed(['Hello', 'World'], task='retrieval.query')
        
        self.assertEqual(len(result.vectors), 2)
        self.assertEqual(result.model_id, 'hakim-test-hakim')
        self.assertEqual(result.usage['api_calls'], 1)
        
        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertIn('texts', call_args[1]['json'])
        self.assertIn('prompt_type', call_args[1]['json'])
    
    def test_model_id(self):
        """Test model ID generation."""
        backend = HakimHTTP()
        self.assertEqual(backend.model_id(), 'hakim-test-hakim')
    
    def test_supports_dual_encoder(self):
        """Test dual encoder support."""
        backend = HakimHTTP()
        self.assertTrue(backend.supports_dual_encoder())
    
    def test_task_mapping(self):
        """Test task to prompt mapping."""
        backend = HakimHTTP()
        
        self.assertEqual(backend._map_task_to_prompt('retrieval.query'), 'query')
        self.assertEqual(backend._map_task_to_prompt('retrieval.passage'), 'passage')
        self.assertIsNone(backend._map_task_to_prompt('unknown'))


class TestSBertBackend(TestCase):
    """Test SBERT HuggingFace backend."""
    
    def setUp(self):
        """Set up test environment."""
        self.patcher = patch.dict('os.environ', {
            'EMBEDDING_SBERT_MODEL_NAME': 'test-sbert-model',
            'EMBEDDING_DEVICE': 'cpu'
        })
        self.patcher.start()
    
    def tearDown(self):
        """Clean up test environment."""
        self.patcher.stop()
    
    @patch('sentence_transformers.SentenceTransformer')
    def test_embed_success(self, mock_st):
        """Test successful embedding."""
        # Mock sentence transformer
        mock_model = Mock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
        mock_model.get_sentence_embedding_dimension.return_value = 3
        mock_st.return_value = mock_model
        
        backend = SBertHF()
        result = backend.embed(['Hello', 'World'])
        
        self.assertEqual(len(result.vectors), 2)
        self.assertEqual(result.model_id, 'sbert-test-sbert-model')
        self.assertEqual(result.dim, 3)
        
        # Verify model call
        mock_model.encode.assert_called_once()
    
    def test_model_id(self):
        """Test model ID generation."""
        backend = SBertHF()
        self.assertEqual(backend.model_id(), 'sbert-test-sbert-model')
    
    def test_supports_dual_encoder(self):
        """Test dual encoder support."""
        backend = SBertHF()
        self.assertFalse(backend.supports_dual_encoder())


class TestPersianEmbeddingSmoke(TestCase):
    """Smoke tests with Persian text samples."""
    
    def test_persian_text_normalization(self):
        """Test that Persian text is properly normalized."""
        class MockBackend(EmbeddingBackend):
            def embed(self, texts, *, task=None):
                # Return mock vectors for Persian text
                vectors = [[0.1, 0.2, 0.3] for _ in texts]
                return EmbeddingResult(vectors, "mock", 3)
            
            def model_id(self):
                return "mock-persian"
            
            def default_dim(self):
                return 3
            
            def supports_dual_encoder(self):
                return False
        
        backend = MockBackend()
        
        # Test Persian legal text
        persian_texts = [
            "اصل ۴۴ قانون اساسی جمهوری اسلامی ایران",
            "ماده ۱۰ قانون مدنی",
            "بند الف تبصره ۲ ماده ۵۶ قانون مالیات‌های مستقیم"
        ]
        
        result = backend.embed(persian_texts)
        
        self.assertEqual(len(result.vectors), 3)
        self.assertEqual(result.model_id, "mock-persian")
        
        # Verify vectors are normalized
        for vector in result.vectors:
            norm = np.linalg.norm(vector)
            self.assertAlmostEqual(norm, 1.0, places=5)


if __name__ == '__main__':
    unittest.main()

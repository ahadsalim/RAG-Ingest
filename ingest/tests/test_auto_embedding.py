"""
Test for automatic chunking and embedding system.
Tests both Legal Unit and QA Entry automatic processing with proper Django test framework.
"""
import time
from django.test import TestCase
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from ingest.apps.documents.models import LegalUnit, Chunk, QAEntry
from ingest.apps.embeddings.models import Embedding


class AutoEmbeddingTest(TestCase):
    """Test automatic chunking and embedding system"""
    
    def setUp(self):
        """Set up test data"""
        self.test_content = (
            'این یک متن تست برای بررسی سیستم خودکار chunking و embedding است. '
            'این متن باید به طور خودکار به چانک تبدیل شود. '
            'سپس برای هر چانک، embedding خودکار ساخته شود. '
            'این فرآیند کاملاً خودکار است و نیازی به دخالت کاربر ندارد.'
        )
    
    def test_legal_unit_auto_chunking(self):
        """Test that Legal Unit automatically creates chunks"""
        # Create Legal Unit
        lu = LegalUnit.objects.create(
            type='law',
            title='تست خودکار - Legal Unit',
            approval_date=timezone.now().date(),
            content=self.test_content
        )
        
        # Wait for signal processing
        time.sleep(3)
        
        # Check chunks created
        chunks = Chunk.objects.filter(unit_id=lu.id)
        self.assertGreater(chunks.count(), 0, "Chunks should be created automatically")
        
        # Verify chunk content
        for chunk in chunks:
            self.assertIsNotNone(chunk.chunk_text)
            self.assertGreater(len(chunk.chunk_text), 0)
    
    def test_chunk_auto_embedding(self):
        """Test that chunks automatically create embeddings"""
        # Create Legal Unit (which creates chunks)
        lu = LegalUnit.objects.create(
            type='law',
            title='تست خودکار - Embedding',
            approval_date=timezone.now().date(),
            content=self.test_content
        )
        
        # Wait for chunking and embedding
        time.sleep(8)
        
        # Get chunks
        chunks = Chunk.objects.filter(unit_id=lu.id)
        self.assertGreater(chunks.count(), 0)
        
        # Check embeddings
        chunk_ct = ContentType.objects.get_for_model(Chunk)
        chunk_ids = list(chunks.values_list('id', flat=True))
        embeddings = Embedding.objects.filter(
            content_type=chunk_ct,
            object_id__in=[str(cid) for cid in chunk_ids]
        )
        
        self.assertGreater(
            embeddings.count(), 
            0, 
            "Embeddings should be created automatically for chunks"
        )
        
        # Verify embedding properties
        for embedding in embeddings:
            self.assertIsNotNone(embedding.vector)
            self.assertGreater(len(embedding.vector), 0)
    
    def test_qa_entry_auto_embedding(self):
        """Test that QA Entry automatically creates embedding"""
        # Create QA Entry
        qa = QAEntry.objects.create(
            question='آیا سیستم خودکار embedding کار می‌کند؟',
            answer='بله، سیستم به طور کامل خودکار است.',
            status='approved',
            category='test'
        )
        
        # Wait for embedding
        time.sleep(8)
        
        # Check QA embedding
        qa_ct = ContentType.objects.get_for_model(QAEntry)
        qa_embedding = Embedding.objects.filter(
            content_type=qa_ct,
            object_id=str(qa.id)
        )
        
        self.assertEqual(
            qa_embedding.count(), 
            1, 
            "One embedding should be created for QA Entry"
        )
        
        # Verify embedding
        embedding = qa_embedding.first()
        self.assertIsNotNone(embedding.vector)
        self.assertGreater(len(embedding.vector), 0)
    
    def test_full_workflow(self):
        """Test complete workflow from creation to embedding"""
        # Create Legal Unit
        lu = LegalUnit.objects.create(
            type='law',
            title='تست کامل سیستم',
            approval_date=timezone.now().date(),
            content=self.test_content
        )
        
        # Wait for complete processing
        time.sleep(10)
        
        # Verify full chain
        chunks = Chunk.objects.filter(unit_id=lu.id)
        self.assertGreater(chunks.count(), 0, "Chunks created")
        
        chunk_ct = ContentType.objects.get_for_model(Chunk)
        embeddings = Embedding.objects.filter(
            content_type=chunk_ct,
            object_id__in=[str(c.id) for c in chunks]
        )
        
        self.assertEqual(
            chunks.count(),
            embeddings.count(),
            "Each chunk should have one embedding"
        )


# Script mode for direct execution
if __name__ == '__main__':
    import os
    import sys
    import django
    
    # Setup Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ingest.settings.prod')
    django.setup()
    
    print('='*70)
    print('🧪 Running Automatic Embedding Tests')
    print('='*70)
    print()
    
    # Run tests
    from django.test.utils import get_runner
    from django.conf import settings
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=False)
    failures = test_runner.run_tests(['ingest.tests.test_auto_embedding'])
    
    if failures:
        sys.exit(1)

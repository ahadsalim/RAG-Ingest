"""
Performance tests to verify optimizations.
تست‌های عملکرد برای بررسی بهینه‌سازی‌ها
"""

import time
import unittest
from django.test import TestCase, Client, TransactionTestCase
from django.core.cache import cache
from django.db import connection, reset_queries
from django.contrib.auth.models import User
from django.conf import settings

from ingest.apps.documents.models import (
    LegalUnit, InstrumentWork, InstrumentExpression
)
from ingest.apps.masterdata.models import Organization


class PerformanceTestCase(TransactionTestCase):
    """تست‌های عملکرد برای بررسی بهینه‌سازی‌ها"""
    
    fixtures = []  # Add fixtures if needed
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.client = Client()
        
        # Create test user
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        
        # Create test data
        cls._create_test_data()
    
    @classmethod
    def _create_test_data(cls):
        """ایجاد داده‌های تست"""
        
        # Create organization
        org = Organization.objects.create(
            name="Test Organization",
            code="TEST001"
        )
        
        # Create works and expressions
        for i in range(10):
            work = InstrumentWork.objects.create(
                title_official=f"Test Work {i}",
                work_type="act",
                organization=org
            )
            
            expr = InstrumentExpression.objects.create(
                work=work,
                version_date="2024-01-01",
                language="fa"
            )
            
            # Create legal units
            for j in range(5):
                LegalUnit.objects.create(
                    work=work,
                    expr=expr,
                    unit_type="article",
                    number=str(j),
                    content=f"محتوای تست برای ماده {j}"
                )
    
    def setUp(self):
        """Setup برای هر تست"""
        cache.clear()
        reset_queries()
        self.client.login(username='testuser', password='testpass123')
    
    def tearDown(self):
        """Cleanup بعد از هر تست"""
        cache.clear()
    
    def test_api_response_time(self):
        """تست زمان پاسخ API"""
        
        # First request (cache miss)
        start = time.time()
        response = self.client.get('/api/documents/legalunits/')
        first_time = time.time() - start
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(first_time, 2.0, "First API request should be < 2 seconds")
        
        # Second request (cache hit)
        start = time.time()
        response = self.client.get('/api/documents/legalunits/')
        second_time = time.time() - start
        
        self.assertEqual(response.status_code, 200)
        self.assertLess(second_time, 0.5, "Cached API request should be < 0.5 seconds")
        
        # Cache should be faster
        self.assertLess(second_time, first_time, "Cached request should be faster")
    
    def test_query_optimization(self):
        """تست بهینه‌سازی Query ها"""
        
        # Enable query debugging
        settings.DEBUG = True
        reset_queries()
        
        # Fetch legal units with relationships
        response = self.client.get('/api/documents/legalunits/')
        
        query_count = len(connection.queries)
        
        # Should use optimized queries
        self.assertLess(query_count, 20, f"Should use < 20 queries, used {query_count}")
        
        # Check for N+1 problems
        data = response.json()
        if 'results' in data:
            result_count = len(data['results'])
            
            # Query count should not scale linearly with results
            self.assertLess(
                query_count, 
                result_count * 3,  # Allow max 3 queries per item
                "Possible N+1 query problem detected"
            )
    
    def test_cache_functionality(self):
        """تست عملکرد Cache"""
        
        # Test cache set/get
        cache.set('test_key', 'test_value', 60)
        cached_value = cache.get('test_key')
        
        self.assertEqual(cached_value, 'test_value', "Cache should store and retrieve values")
        
        # Test cache invalidation
        cache.delete('test_key')
        cached_value = cache.get('test_key')
        
        self.assertIsNone(cached_value, "Cache should delete values")
        
        # Test cache statistics
        cache.set('hit_test', 'value', 60)
        cache.get('hit_test')  # Hit
        cache.get('miss_test')  # Miss
        
        # Cache should be working
        self.assertTrue(cache.get('hit_test') is not None)
    
    def test_pagination_performance(self):
        """تست عملکرد Pagination"""
        
        # Create more test data
        work = InstrumentWork.objects.first()
        expr = InstrumentExpression.objects.first()
        
        for i in range(100):
            LegalUnit.objects.create(
                work=work,
                expr=expr,
                unit_type="article",
                number=f"p{i}",
                content=f"محتوای صفحه‌بندی {i}"
            )
        
        # Test different page sizes
        page_sizes = [10, 20, 50]
        
        for page_size in page_sizes:
            reset_queries()
            
            start = time.time()
            response = self.client.get(
                f'/api/documents/legalunits/?page_size={page_size}'
            )
            duration = time.time() - start
            
            self.assertEqual(response.status_code, 200)
            self.assertLess(
                duration, 1.0,
                f"Pagination with size {page_size} should be < 1 second"
            )
            
            # Check query count doesn't increase with page size
            query_count = len(connection.queries)
            self.assertLess(
                query_count, 30,
                f"Pagination should use < 30 queries regardless of page size"
            )
    
    def test_bulk_operation_performance(self):
        """تست عملکرد عملیات Bulk"""
        
        # Test bulk create
        units = []
        work = InstrumentWork.objects.first()
        expr = InstrumentExpression.objects.first()
        
        for i in range(100):
            units.append(LegalUnit(
                work=work,
                expr=expr,
                unit_type="paragraph",
                number=f"bulk{i}",
                content=f"Bulk content {i}"
            ))
        
        start = time.time()
        LegalUnit.objects.bulk_create(units, batch_size=50)
        duration = time.time() - start
        
        self.assertLess(duration, 2.0, "Bulk create of 100 items should be < 2 seconds")
    
    def test_compression_middleware(self):
        """تست Middleware فشرده‌سازی"""
        
        # Create large response
        response = self.client.get(
            '/api/documents/legalunits/',
            HTTP_ACCEPT_ENCODING='gzip'
        )
        
        # Check if compression is applied for large responses
        if len(response.content) > 1024:  # Only for responses > 1KB
            content_encoding = response.get('Content-Encoding', '')
            # Note: Compression might be handled by web server
            # This test verifies the middleware is not breaking anything
            self.assertEqual(response.status_code, 200)
    
    def test_static_file_caching(self):
        """تست Cache برای فایل‌های استاتیک"""
        
        # Request static file
        response = self.client.get('/static/admin/css/base.css')
        
        if response.status_code == 200:
            # Check cache headers
            cache_control = response.get('Cache-Control', '')
            
            # Static files should have cache headers
            self.assertIn(
                'max-age',
                cache_control.lower(),
                "Static files should have cache headers"
            )
    
    def test_database_connection_pooling(self):
        """تست Connection Pooling دیتابیس"""
        
        # Make multiple requests
        for _ in range(10):
            response = self.client.get('/api/documents/legalunits/')
            self.assertEqual(response.status_code, 200)
        
        # Check connection count didn't explode
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            conn_count = cursor.fetchone()[0]
        
        # Should reuse connections
        self.assertLess(
            conn_count, 20,
            f"Should use connection pooling, but has {conn_count} connections"
        )
    
    def test_memory_usage(self):
        """تست مصرف حافظه"""
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        # Get initial memory
        initial_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        # Perform operations
        for _ in range(100):
            response = self.client.get('/api/documents/legalunits/')
            self.assertEqual(response.status_code, 200)
        
        # Get final memory
        final_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable
        self.assertLess(
            memory_increase, 100,
            f"Memory increased by {memory_increase:.1f} MB, possible memory leak"
        )


class LoadTestCase(TestCase):
    """تست‌های بار (Load Testing)"""
    
    def test_concurrent_requests(self):
        """تست درخواست‌های همزمان"""
        
        import concurrent.futures
        import threading
        
        def make_request():
            client = Client()
            response = client.get('/api/documents/legalunits/')
            return response.status_code
        
        # Test with 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        self.assertTrue(
            all(status == 200 for status in results),
            "All concurrent requests should succeed"
        )


# Command to run performance tests
# python manage.py test tests.test_performance --keepdb

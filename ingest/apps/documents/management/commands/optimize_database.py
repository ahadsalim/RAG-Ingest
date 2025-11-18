"""
Management command to optimize database performance.
دستور مدیریت برای بهینه‌سازی عملکرد دیتابیس
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings
import time


class Command(BaseCommand):
    help = 'بهینه‌سازی دیتابیس با اضافه کردن Index ها و تحلیل جداول'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--create-indexes',
            action='store_true',
            help='Create missing database indexes'
        )
        parser.add_argument(
            '--analyze',
            action='store_true',
            help='Run ANALYZE on all tables'
        )
        parser.add_argument(
            '--vacuum',
            action='store_true',
            help='Run VACUUM on all tables (locks tables!)'
        )
        parser.add_argument(
            '--check-slow-queries',
            action='store_true',
            help='Check for slow queries'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimizations'
        )
    
    def handle(self, *args, **options):
        if options['all']:
            options['create_indexes'] = True
            options['analyze'] = True
            options['check_slow_queries'] = True
            # Don't auto-run vacuum as it locks tables
        
        if options['create_indexes']:
            self.create_indexes()
        
        if options['analyze']:
            self.analyze_tables()
        
        if options['vacuum']:
            self.vacuum_tables()
        
        if options['check_slow_queries']:
            self.check_slow_queries()
        
        self.stdout.write(self.style.SUCCESS('بهینه‌سازی دیتابیس با موفقیت انجام شد'))
    
    def create_indexes(self):
        """ایجاد Index های مفید برای Query های پرتکرار"""
        self.stdout.write('Creating database indexes...')
        
        indexes = [
            # Indexes for LegalUnit queries
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_legalunit_work_type 
               ON documents_legalunit(work_id, unit_type);""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_legalunit_valid_dates 
               ON documents_legalunit(valid_from, valid_to) 
               WHERE valid_to IS NOT NULL;""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_legalunit_active 
               ON documents_legalunit(work_id) 
               WHERE valid_to IS NULL OR valid_to > CURRENT_DATE;""",
            
            # Indexes for Chunk queries
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_chunk_hash_expr 
               ON documents_chunk(hash, expr_id);""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_chunk_unit_created 
               ON documents_chunk(unit_id, created_at DESC);""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_chunk_node_id 
               ON documents_chunk(node_id) 
               WHERE node_id IS NOT NULL;""",
            
            # Indexes for SyncLog queries
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_synclog_status_retry 
               ON embeddings_synclog(status, retry_count) 
               WHERE status IN ('failed', 'pending_retry');""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_synclog_unverified 
               ON embeddings_synclog(synced_at) 
               WHERE status = 'synced' AND verified_at IS NULL;""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_synclog_chunk_status 
               ON embeddings_synclog(chunk_id, status);""",
            
            # Indexes for Embedding queries
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_embedding_content_object 
               ON embeddings_embedding(content_type_id, object_id);""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_embedding_model_created 
               ON embeddings_embedding(model_id, created_at DESC);""",
            
            # Full text search indexes (GIN indexes for text search)
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_legalunit_content_gin 
               ON documents_legalunit 
               USING gin(to_tsvector('simple', content));""",
            
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_chunk_text_gin 
               ON documents_chunk 
               USING gin(to_tsvector('simple', chunk_text));""",
            
            # JSONB indexes
            """CREATE INDEX CONCURRENTLY IF NOT EXISTS 
               idx_chunk_citation_gin 
               ON documents_chunk 
               USING gin(citation_payload_json);""",
        ]
        
        with connection.cursor() as cursor:
            for index_sql in indexes:
                try:
                    start_time = time.time()
                    cursor.execute(index_sql)
                    duration = time.time() - start_time
                    index_name = index_sql.split('IF NOT EXISTS')[1].split('ON')[0].strip()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Created index {index_name} in {duration:.2f}s'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ✗ Failed to create index: {e}')
                    )
    
    def analyze_tables(self):
        """اجرای ANALYZE برای به‌روزرسانی آمار جداول"""
        self.stdout.write('Analyzing tables...')
        
        tables = [
            'documents_legalunit',
            'documents_chunk',
            'documents_instrumentwork',
            'documents_instrumentexpression',
            'documents_instrumentmanifestation',
            'documents_fileasset',
            'documents_qaentry',
            'embeddings_embedding',
            'embeddings_synclog',
            'masterdata_organization',
            'masterdata_vocabularyterm',
        ]
        
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    start_time = time.time()
                    cursor.execute(f"ANALYZE {table};")
                    duration = time.time() - start_time
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  ✓ Analyzed {table} in {duration:.2f}s'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ✗ Failed to analyze {table}: {e}')
                    )
    
    def vacuum_tables(self):
        """اجرای VACUUM برای بازیابی فضای disk (توجه: جداول را قفل می‌کند)"""
        confirm = input(
            'WARNING: VACUUM will lock tables! Continue? (yes/no): '
        )
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING('VACUUM cancelled'))
            return
        
        self.stdout.write('Running VACUUM...')
        
        with connection.cursor() as cursor:
            try:
                start_time = time.time()
                cursor.execute("VACUUM ANALYZE;")
                duration = time.time() - start_time
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ VACUUM completed in {duration:.2f}s'
                    )
                )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ VACUUM failed: {e}')
                )
    
    def check_slow_queries(self):
        """بررسی Query های کند"""
        self.stdout.write('Checking for slow queries...')
        
        # Check current running queries
        query = """
            SELECT 
                pid,
                now() - pg_stat_activity.query_start AS duration,
                query,
                state
            FROM pg_stat_activity
            WHERE (now() - pg_stat_activity.query_start) > interval '1 second'
                AND state != 'idle'
                AND query NOT ILIKE '%pg_stat_activity%'
            ORDER BY duration DESC
            LIMIT 10;
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query)
            slow_queries = cursor.fetchall()
            
            if slow_queries:
                self.stdout.write(self.style.WARNING('Slow queries found:'))
                for pid, duration, query_text, state in slow_queries:
                    self.stdout.write(
                        f'  PID: {pid}, Duration: {duration}, State: {state}'
                    )
                    self.stdout.write(f'  Query: {query_text[:200]}...\n')
            else:
                self.stdout.write(
                    self.style.SUCCESS('No slow queries currently running')
                )
        
        # Check missing indexes
        self.check_missing_indexes()
    
    def check_missing_indexes(self):
        """بررسی Index های پیشنهادی توسط PostgreSQL"""
        query = """
            SELECT 
                schemaname,
                tablename,
                attname,
                n_distinct,
                most_common_vals,
                most_common_freqs,
                histogram_bounds
            FROM pg_stats
            WHERE schemaname = 'public'
                AND n_distinct > 100
                AND tablename LIKE 'documents_%'
            ORDER BY n_distinct DESC
            LIMIT 10;
        """
        
        with connection.cursor() as cursor:
            cursor.execute(query)
            stats = cursor.fetchall()
            
            if stats:
                self.stdout.write('\nColumns that might benefit from indexing:')
                for row in stats:
                    schema, table, column, n_distinct, *_ = row
                    self.stdout.write(
                        f'  {table}.{column} (distinct values: {n_distinct})'
                    )

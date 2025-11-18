"""
Management command for monitoring application performance.
دستور مدیریت برای مانیتورینگ عملکرد برنامه
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import connection
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
import json
import time
import psutil
import os


class Command(BaseCommand):
    help = 'مانیتورینگ عملکرد برنامه و نمایش متریک‌ها'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--live',
            action='store_true',
            help='Live monitoring mode (updates every 5 seconds)'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=60,
            help='Duration for live monitoring in seconds (default: 60)'
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Output in JSON format'
        )
    
    def handle(self, *args, **options):
        if options['live']:
            self.live_monitoring(options['duration'])
        else:
            metrics = self.collect_metrics()
            
            if options['json']:
                self.stdout.write(json.dumps(metrics, indent=2, default=str))
            else:
                self.display_metrics(metrics)
    
    def collect_metrics(self):
        """جمع‌آوری متریک‌های عملکرد"""
        
        metrics = {
            'timestamp': timezone.now().isoformat(),
            'system': self.get_system_metrics(),
            'database': self.get_database_metrics(),
            'cache': self.get_cache_metrics(),
            'application': self.get_application_metrics(),
        }
        
        return metrics
    
    def get_system_metrics(self):
        """متریک‌های سیستم"""
        
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_mb': memory.used / (1024 * 1024),
                'memory_available_mb': memory.available / (1024 * 1024),
                'disk_percent': disk.percent,
                'disk_free_gb': disk.free / (1024 * 1024 * 1024),
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_database_metrics(self):
        """متریک‌های دیتابیس"""
        
        metrics = {}
        
        with connection.cursor() as cursor:
            # Database size
            cursor.execute("""
                SELECT pg_database_size(current_database()) as size
            """)
            db_size = cursor.fetchone()[0]
            metrics['size_mb'] = db_size / (1024 * 1024)
            
            # Connection count
            cursor.execute("""
                SELECT count(*) FROM pg_stat_activity
                WHERE datname = current_database()
            """)
            metrics['connections'] = cursor.fetchone()[0]
            
            # Table statistics
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    n_live_tup as rows,
                    n_dead_tup as dead_rows,
                    last_vacuum,
                    last_analyze
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY n_live_tup DESC
                LIMIT 10
            """)
            
            tables = []
            for row in cursor.fetchall():
                tables.append({
                    'table': f"{row[0]}.{row[1]}",
                    'rows': row[2],
                    'dead_rows': row[3],
                    'last_vacuum': row[4].isoformat() if row[4] else None,
                    'last_analyze': row[5].isoformat() if row[5] else None,
                })
            
            metrics['top_tables'] = tables
            
            # Slow queries
            cursor.execute("""
                SELECT 
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    query
                FROM pg_stat_statements
                WHERE query NOT LIKE '%pg_stat%'
                ORDER BY mean_exec_time DESC
                LIMIT 5
            """)
            
            slow_queries = []
            for row in cursor.fetchall():
                slow_queries.append({
                    'calls': row[0],
                    'total_time_ms': row[1],
                    'mean_time_ms': row[2],
                    'query': row[3][:100],
                })
            
            if slow_queries:
                metrics['slow_queries'] = slow_queries
            
            # Index usage
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    indexrelname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                    AND idx_scan = 0
                LIMIT 10
            """)
            
            unused_indexes = []
            for row in cursor.fetchall():
                unused_indexes.append({
                    'table': f"{row[0]}.{row[1]}",
                    'index': row[2],
                    'scans': row[3],
                })
            
            if unused_indexes:
                metrics['unused_indexes'] = unused_indexes
        
        return metrics
    
    def get_cache_metrics(self):
        """متریک‌های Cache"""
        
        try:
            # Get Redis info
            from django_redis import get_redis_connection
            redis_conn = get_redis_connection("default")
            info = redis_conn.info()
            
            metrics = {
                'used_memory_mb': info.get('used_memory', 0) / (1024 * 1024),
                'connected_clients': info.get('connected_clients', 0),
                'total_keys': redis_conn.dbsize(),
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
            }
            
            # Calculate hit rate
            total = metrics['hits'] + metrics['misses']
            if total > 0:
                metrics['hit_rate_percent'] = (metrics['hits'] / total) * 100
            else:
                metrics['hit_rate_percent'] = 0
            
            # Get cache stats from Django
            perf_stats = cache.get('performance_stats', {})
            if perf_stats:
                metrics['django_stats'] = perf_stats
            
            return metrics
            
        except Exception as e:
            return {'error': str(e)}
    
    def get_application_metrics(self):
        """متریک‌های اپلیکیشن"""
        
        from ingest.apps.documents.models import (
            LegalUnit, Chunk, InstrumentWork, InstrumentExpression
        )
        from ingest.apps.embeddings.models_synclog import SyncLog
        from ingest.apps.embeddings.models import Embedding
        
        metrics = {
            'counts': {
                'legal_units': LegalUnit.objects.count(),
                'chunks': Chunk.objects.count(),
                'works': InstrumentWork.objects.count(),
                'expressions': InstrumentExpression.objects.count(),
                'embeddings': Embedding.objects.count(),
                'sync_logs': SyncLog.objects.count(),
            },
            'sync_status': {
                'synced': SyncLog.objects.filter(status='synced').count(),
                'verified': SyncLog.objects.filter(status='verified').count(),
                'failed': SyncLog.objects.filter(status='failed').count(),
                'pending': SyncLog.objects.filter(status='pending').count(),
            }
        }
        
        # Recent activity
        last_hour = timezone.now() - timedelta(hours=1)
        metrics['recent_activity'] = {
            'chunks_created': Chunk.objects.filter(created_at__gte=last_hour).count(),
            'embeddings_created': Embedding.objects.filter(created_at__gte=last_hour).count(),
        }
        
        return metrics
    
    def display_metrics(self, metrics):
        """نمایش متریک‌ها به صورت فرمت شده"""
        
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("📊 Performance Metrics Dashboard"))
        self.stdout.write("="*60)
        
        # System metrics
        self.stdout.write("\n🖥️  System Resources:")
        sys = metrics['system']
        self.stdout.write(f"  CPU: {sys.get('cpu_percent', 'N/A')}%")
        self.stdout.write(f"  Memory: {sys.get('memory_percent', 'N/A')}% "
                         f"({sys.get('memory_used_mb', 0):.1f} MB used)")
        self.stdout.write(f"  Disk: {sys.get('disk_percent', 'N/A')}% "
                         f"({sys.get('disk_free_gb', 0):.1f} GB free)")
        
        # Database metrics
        self.stdout.write("\n💾 Database:")
        db = metrics['database']
        self.stdout.write(f"  Size: {db.get('size_mb', 0):.1f} MB")
        self.stdout.write(f"  Connections: {db.get('connections', 0)}")
        
        if 'top_tables' in db:
            self.stdout.write("\n  Top Tables by Row Count:")
            for table in db['top_tables'][:5]:
                self.stdout.write(
                    f"    • {table['table']}: {table['rows']:,} rows"
                    f" ({table['dead_rows']} dead)"
                )
        
        if 'unused_indexes' in db and db['unused_indexes']:
            self.stdout.write(self.style.WARNING("\n  ⚠️  Unused Indexes:"))
            for idx in db['unused_indexes'][:3]:
                self.stdout.write(f"    • {idx['index']} on {idx['table']}")
        
        # Cache metrics
        self.stdout.write("\n💨 Cache:")
        cache_metrics = metrics['cache']
        if 'error' not in cache_metrics:
            self.stdout.write(f"  Memory Used: {cache_metrics.get('used_memory_mb', 0):.1f} MB")
            self.stdout.write(f"  Total Keys: {cache_metrics.get('total_keys', 0)}")
            self.stdout.write(f"  Hit Rate: {cache_metrics.get('hit_rate_percent', 0):.1f}%")
            
            hits = cache_metrics.get('hits', 0)
            misses = cache_metrics.get('misses', 0)
            self.stdout.write(f"  Hits/Misses: {hits:,} / {misses:,}")
        else:
            self.stdout.write(f"  Error: {cache_metrics['error']}")
        
        # Application metrics
        self.stdout.write("\n📱 Application:")
        app = metrics['application']
        
        self.stdout.write("  Document Counts:")
        for model, count in app['counts'].items():
            self.stdout.write(f"    • {model}: {count:,}")
        
        self.stdout.write("\n  Sync Status:")
        for status, count in app['sync_status'].items():
            color = self.style.SUCCESS if status in ['synced', 'verified'] else self.style.WARNING
            self.stdout.write(color(f"    • {status}: {count:,}"))
        
        self.stdout.write("\n  Recent Activity (last hour):")
        for activity, count in app['recent_activity'].items():
            self.stdout.write(f"    • {activity}: {count}")
        
        self.stdout.write("\n" + "="*60 + "\n")
    
    def live_monitoring(self, duration):
        """حالت مانیتورینگ زنده"""
        
        import os
        import sys
        
        start_time = time.time()
        
        try:
            while time.time() - start_time < duration:
                # Clear screen
                os.system('clear' if os.name == 'posix' else 'cls')
                
                # Collect and display metrics
                metrics = self.collect_metrics()
                self.display_metrics(metrics)
                
                remaining = duration - (time.time() - start_time)
                self.stdout.write(
                    self.style.WARNING(
                        f"⏱️  Live monitoring... {remaining:.0f}s remaining (Ctrl+C to stop)"
                    )
                )
                
                # Wait before next update
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.stdout.write("\n\n" + self.style.SUCCESS("✓ Monitoring stopped"))
    
    def generate_report(self):
        """تولید گزارش عملکرد"""
        
        metrics = self.collect_metrics()
        
        report = {
            'timestamp': metrics['timestamp'],
            'summary': {
                'health': 'good',  # Calculate based on metrics
                'recommendations': []
            },
            'metrics': metrics
        }
        
        # Add recommendations based on metrics
        if metrics['system']['cpu_percent'] > 80:
            report['summary']['recommendations'].append(
                "CPU usage is high. Consider scaling horizontally."
            )
        
        if metrics['cache']['hit_rate_percent'] < 50:
            report['summary']['recommendations'].append(
                "Cache hit rate is low. Review caching strategy."
            )
        
        return report

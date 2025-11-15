"""
Management command to show embedding system status.

Displays:
- Current configuration
- Backend information
- Database statistics
- Index status
- Model distribution
"""

import logging
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import connection
from django.conf import settings

from ingest.apps.embeddings.models import Embedding
from ingest.apps.embeddings.backends.factory import get_backend_info, validate_provider_config

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Show embedding system status and configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            type=str,
            help='Check status for specific provider (overrides current config)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information'
        )

    def handle(self, *args, **options):
        """Main command handler."""
        provider = options.get('provider') or settings.EMBEDDING_PROVIDER
        verbose = options['verbose']
        
        self.stdout.write("🔍 Embedding System Status")
        self.stdout.write("=" * 50)
        
        # Show configuration
        self.show_configuration(provider)
        
        # Show backend information
        self.show_backend_info(provider)
        
        # Show database statistics
        self.show_database_stats(verbose)
        
        # Show index status
        self.show_index_status()
        
        # Validate configuration
        self.show_validation_status(provider)

    def show_configuration(self, provider: str):
        """Show current embedding configuration."""
        self.stdout.write("\n📋 Configuration:")
        self.stdout.write(f"  Provider: {provider}")
        self.stdout.write(f"  Model ID: {getattr(settings, 'EMBEDDING_MODEL_ID', 'auto-detect')}")
        self.stdout.write(f"  Dimension: {getattr(settings, 'EMBEDDING_DIMENSION', 'auto-detect')}")
        self.stdout.write(f"  Batch Size: {getattr(settings, 'EMBEDDING_BATCH_SIZE', 32)}")
        self.stdout.write(f"  Read Model ID: {getattr(settings, 'EMBEDDINGS_READ_MODEL_ID', 'current')}")
        
        if provider == 'hakim':
            self.stdout.write(f"  Hakim API URL: {getattr(settings, 'EMBEDDING_HAKIM_API_URL', 'not set')}")
            self.stdout.write(f"  Hakim Model: {getattr(settings, 'EMBEDDING_HAKIM_MODEL_NAME', 'Hakim-v1')}")
        elif provider == 'sbert':
            self.stdout.write(f"  SBERT Model: {getattr(settings, 'EMBEDDING_SBERT_MODEL_NAME', 'MatinaSRoberta')}")
            self.stdout.write(f"  Device: {getattr(settings, 'EMBEDDING_DEVICE', 'auto')}")

    def show_backend_info(self, provider: str):
        """Show backend information."""
        self.stdout.write("\n🔧 Backend Information:")
        
        try:
            backend_info = get_backend_info(provider)
            
            if 'error' in backend_info:
                self.stdout.write(self.style.ERROR(f"  Error: {backend_info['error']}"))
                return
            
            self.stdout.write(f"  Backend Class: {backend_info.get('backend_class', 'Unknown')}")
            self.stdout.write(f"  Model ID: {backend_info.get('model_id', 'Unknown')}")
            self.stdout.write(f"  Default Dimension: {backend_info.get('default_dim', 'Unknown')}")
            self.stdout.write(f"  Dual Encoder: {backend_info.get('supports_dual_encoder', False)}")
            
            # Provider-specific info
            if 'api_url' in backend_info:
                self.stdout.write(f"  API URL: {backend_info['api_url']}")
            if 'model_name' in backend_info:
                self.stdout.write(f"  Model Name: {backend_info['model_name']}")
            if 'device' in backend_info:
                self.stdout.write(f"  Device: {backend_info['device']}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Failed to get backend info: {e}"))

    def show_database_stats(self, verbose: bool):
        """Show database statistics."""
        self.stdout.write("\n📊 Database Statistics:")
        
        try:
            # Total embeddings
            total_embeddings = Embedding.objects.count()
            self.stdout.write(f"  Total Embeddings: {total_embeddings:,}")
            
            if total_embeddings == 0:
                self.stdout.write("  No embeddings found in database")
                return
            
            # Group by model_id
            model_stats = defaultdict(lambda: {'count': 0, 'dimensions': set()})
            
            for embedding in Embedding.objects.values('model_id', 'dim'):
                model_id = embedding['model_id']
                dim = embedding['dim']
                model_stats[model_id]['count'] += 1
                model_stats[model_id]['dimensions'].add(dim)
            
            self.stdout.write("\n  📈 By Model:")
            for model_id, stats in model_stats.items():
                dims = ', '.join(map(str, sorted(stats['dimensions'])))
                self.stdout.write(f"    {model_id}: {stats['count']:,} embeddings (dim: {dims})")
            
            if verbose:
                # Content type distribution
                self.show_content_type_distribution()
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Failed to get database stats: {e}"))

    def show_content_type_distribution(self):
        """Show distribution by content type."""
        self.stdout.write("\n  📋 By Content Type:")
        
        try:
            from django.contrib.contenttypes.models import ContentType
            
            content_type_stats = (
                Embedding.objects
                .values('content_type__app_label', 'content_type__model')
                .annotate(count=models.Count('id'))
                .order_by('-count')
            )
            
            for stat in content_type_stats:
                app_label = stat['content_type__app_label']
                model = stat['content_type__model']
                count = stat['count']
                self.stdout.write(f"    {app_label}.{model}: {count:,}")
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"    Failed to get content type stats: {e}"))

    def show_index_status(self):
        """Show pgvector index status."""
        self.stdout.write("\n🗂️  Index Status:")
        
        try:
            with connection.cursor() as cursor:
                # Check for vector indexes
                cursor.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        indexdef
                    FROM pg_indexes 
                    WHERE tablename LIKE '%embedding%' 
                    AND indexdef LIKE '%vector%'
                    ORDER BY tablename, indexname
                """)
                
                indexes = cursor.fetchall()
                
                if indexes:
                    for schema, table, index_name, index_def in indexes:
                        self.stdout.write(f"  📇 {schema}.{table}.{index_name}")
                        if 'ivfflat' in index_def.lower():
                            self.stdout.write("    Type: IVFFlat")
                        elif 'hnsw' in index_def.lower():
                            self.stdout.write("    Type: HNSW")
                        else:
                            self.stdout.write("    Type: Unknown")
                else:
                    self.stdout.write("  No vector indexes found")
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Failed to check index status: {e}"))

    def show_validation_status(self, provider: str):
        """Show configuration validation status."""
        self.stdout.write("\n✅ Validation:")
        
        try:
            validation = validate_provider_config(provider)
            
            if validation['valid']:
                self.stdout.write(self.style.SUCCESS("  Configuration is valid"))
            else:
                self.stdout.write(self.style.ERROR("  Configuration has issues"))
            
            if validation['missing_config']:
                self.stdout.write("  ❌ Missing configuration:")
                for missing in validation['missing_config']:
                    self.stdout.write(f"    - {missing}")
            
            if validation['warnings']:
                self.stdout.write("  ⚠️  Warnings:")
                for warning in validation['warnings']:
                    self.stdout.write(f"    - {warning}")
                    
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Validation failed: {e}"))

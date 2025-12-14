"""
Service for syncing embeddings to Core system.
"""
import requests
import logging
from typing import List, Dict, Any
from django.utils import timezone
from django.db import transaction

from ingest.apps.embeddings.models import Embedding, CoreConfig
from ingest.apps.embeddings.models_synclog import SyncLog, SyncStats
from .payload_builder import build_summary_payload, calculate_metadata_hash

logger = logging.getLogger(__name__)


class CoreSyncService:
    """Service برای همگام‌سازی با Core."""
    
    def __init__(self):
        self.config = CoreConfig.get_config()
    
    def sync_new_embeddings(self, batch_size: int = None) -> Dict[str, Any]:
        """
        Sync embeddings جدید که هنوز به Core ارسال نشده‌اند.
        
        Returns:
            Dict با نتیجه sync
        """
        if not self.config.is_active:
            return {'status': 'disabled', 'message': 'Core sync is disabled'}
        
        if not self.config.auto_sync_enabled:
            return {'status': 'disabled', 'message': 'Auto sync is disabled'}
        
        batch_size = batch_size or self.config.sync_batch_size
        
        # Get unsynced embeddings
        # Note: prefetch_related removed because it causes errors with QAEntry
        # which doesn't have unit_id field. Prefetching is done in payload_builder.
        embeddings = Embedding.objects.filter(
            synced_to_core=False
        ).select_related(
            'content_type'
        )[:batch_size]
        
        if not embeddings:
            return {'status': 'nothing_to_sync', 'synced': 0}
        
        # Build payloads
        payloads = []
        embedding_map = {}  # embedding.id -> embedding
        
        for emb in embeddings:
            payload = build_summary_payload(emb)
            if payload:
                payloads.append(payload)
                embedding_map[str(emb.id)] = emb
                
                # Calculate and store metadata hash
                emb.metadata_hash = calculate_metadata_hash(payload)
        
        if not payloads:
            return {'status': 'error', 'message': 'Failed to build any payloads'}
        
        # Send to Core
        result = self._send_to_core(payloads)
        
        if result['success']:
            # Mark as synced
            now = timezone.now()
            
            with transaction.atomic():
                for payload in payloads:
                    emb_id = payload['id']
                    if emb_id in embedding_map:
                        emb = embedding_map[emb_id]
                        emb.synced_to_core = True
                        emb.synced_at = now
                        emb.last_metadata_sync = now
                        emb.sync_error = ''
                        emb.sync_retry_count = 0
                        emb.save(update_fields=[
                            'synced_to_core', 'synced_at', 'last_metadata_sync',
                            'sync_error', 'sync_retry_count', 'metadata_hash',
                            'updated_at'
                        ])
                
                # Update config stats
                self.config.last_successful_sync = now
                self.config.total_synced += len(payloads)
                self.config.last_sync_error = ''
                self.config.save()
                
            # SyncLog will be created by _save_sync_logs if Core returns node_ids
            
            logger.info(f"Successfully synced {len(payloads)} embeddings")
            return {
                'status': 'success',
                'synced': len(payloads),
                'timestamp': timezone.now().isoformat()
            }
        else:
            # Mark with error
            with transaction.atomic():
                for payload in payloads:
                    emb_id = payload['id']
                    if emb_id in embedding_map:
                        emb = embedding_map[emb_id]
                        emb.sync_error = result.get('error', 'Unknown error')[:500]
                        emb.sync_retry_count += 1
                        emb.save(update_fields=['sync_error', 'sync_retry_count', 'updated_at'])
                
                # Update config
                self.config.total_errors += 1
                self.config.last_sync_error = result.get('error', 'Unknown error')[:500]
                self.config.save()
            
            logger.error(f"Failed to sync embeddings: {result.get('error')}")
            return {
                'status': 'error',
                'error': result.get('error'),
                'timestamp': timezone.now().isoformat()
            }
    
    def sync_changed_metadata(self, batch_size: int = None) -> Dict[str, Any]:
        """
        Sync embeddings که metadata آنها تغییر کرده است.
        """
        if not self.config.track_metadata_changes:
            return {'status': 'disabled', 'message': 'Metadata tracking is disabled'}
        
        batch_size = batch_size or self.config.sync_batch_size
        
        # Get embeddings that need metadata resync
        # Note: prefetch_related removed because it causes errors with QAEntry
        embeddings = Embedding.objects.filter(
            synced_to_core=True,
            metadata_hash=''  # Only get embeddings with invalidated metadata
        ).select_related(
            'content_type'
        )[:batch_size]
        
        # Check which ones have changed metadata
        changed_embeddings = []
        payloads = []
        
        for emb in embeddings:
            payload = build_summary_payload(emb)
            if payload:
                current_hash = calculate_metadata_hash(payload)
                if current_hash != emb.metadata_hash:
                    changed_embeddings.append(emb)
                    payloads.append(payload)
                    emb.metadata_hash = current_hash
        
        if not payloads:
            return {'status': 'nothing_to_sync', 'changed': 0}
        
        # Send to Core
        result = self._send_to_core(payloads)
        
        if result['success']:
            with transaction.atomic():
                for emb in changed_embeddings:
                    emb.last_metadata_sync = timezone.now()
                    emb.save(update_fields=['metadata_hash', 'last_metadata_sync', 'updated_at'])
            
            logger.info(f"Successfully resynced {len(payloads)} changed embeddings")
            return {
                'status': 'success',
                'changed': len(payloads),
                'timestamp': timezone.now().isoformat()
            }
        else:
            logger.error(f"Failed to resync changed embeddings: {result.get('error')}")
            return {
                'status': 'error',
                'error': result.get('error'),
                'timestamp': timezone.now().isoformat()
            }
    
    def sync_all_embeddings(self) -> Dict[str, Any]:
        """
        همگام‌سازی تمام embeddings (برای اولین بار یا reset).
        """
        # Reset all embeddings
        Embedding.objects.all().update(
            synced_to_core=False,
            synced_at=None,
            sync_error='',
            sync_retry_count=0
        )
        
        # Sync in batches
        total_synced = 0
        total_errors = 0
        
        while True:
            result = self.sync_new_embeddings()
            
            if result['status'] == 'nothing_to_sync':
                break
            elif result['status'] == 'success':
                total_synced += result['synced']
            else:
                total_errors += 1
                break
        
        # Create SyncStats snapshot
        self._create_sync_stats()
        
        return {
            'status': 'completed',
            'total_synced': total_synced,
            'total_errors': total_errors,
            'timestamp': timezone.now().isoformat()
        }
    
    def _send_to_core(self, payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        ارسال payloads به Core API.
        """
        try:
            headers = {
                'Content-Type': 'application/json'
            }
            if self.config.core_api_key:
                headers['X-API-Key'] = self.config.core_api_key
            
            url = f"{self.config.core_api_url}/api/v1/sync/embeddings"
            
            response = requests.post(
                url,
                json={
                    'embeddings': payloads,
                    'sync_type': 'incremental'
                },
                headers=headers,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                # Save node_ids to SyncLog
                if 'node_ids' in result:
                    self._save_sync_logs(payloads, result['node_ids'], result.get('timestamp'))
                else:
                    # اگر Core node_ids برنگرداند، از embedding.id به عنوان node_id استفاده می‌کنیم
                    node_ids = [p['id'] for p in payloads]
                    self._save_sync_logs(payloads, node_ids, result.get('timestamp'))
                return {'success': True, 'response': result}
            else:
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}: {response.text[:500]}"
                }
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Request timeout'}
        except requests.exceptions.ConnectionError:
            return {'success': False, 'error': 'Connection error - Core API unreachable'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _save_sync_logs(self, payloads: List[Dict], node_ids: List[str], timestamp: str = None):
        """ذخیره node_ids در SyncLog."""
        try:
            from ingest.apps.documents.models import Chunk
            
            for payload, node_id in zip(payloads, node_ids):
                embedding_id = payload.get('id')
                
                if not embedding_id or not node_id:
                    continue
                
                # پیدا کردن Embedding و Chunk مربوطه
                try:
                    embedding = Embedding.objects.get(id=embedding_id)
                    chunk = embedding.content_object
                    
                    # فقط Chunk را پردازش می‌کنیم
                    if isinstance(chunk, Chunk):
                        # به‌روزرسانی node_id در Chunk
                        if not chunk.node_id:
                            chunk.node_id = node_id
                            chunk.save(update_fields=['node_id'])
                        
                        # ایجاد SyncLog
                        SyncLog.create_sync_log(
                            node_id=node_id,
                            chunk=chunk,
                            synced_at=timestamp
                        )
                    else:
                        logger.warning(f"Embedding {embedding_id} is not linked to a Chunk")
                        
                except Embedding.DoesNotExist:
                    logger.warning(f"Embedding {embedding_id} not found")
                    continue
                    
            logger.info(f"Saved {len(node_ids)} sync logs")
        except Exception as e:
            logger.error(f"Error saving sync logs: {e}")
    
    def verify_node_in_core(self, node_id: str) -> Dict[str, Any]:
        """
        بررسی یک نود در Core.
        
        Args:
            node_id: UUID نود برای بررسی
            
        Returns:
            Dict با اطلاعات نود یا None در صورت خطا
        """
        try:
            url = f"{self.config.core_api_url}/api/v1/sync/node/{node_id}"
            params = {}
            if self.config.core_api_key:
                params['api_key'] = self.config.core_api_key
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {'exists': False, 'node_id': node_id}
            else:
                return {'exists': False, 'node_id': node_id, 'error': f'HTTP {response.status_code}'}
                
        except requests.exceptions.Timeout:
            return {'exists': False, 'node_id': node_id, 'error': 'Timeout'}
        except requests.exceptions.ConnectionError:
            return {'exists': False, 'node_id': node_id, 'error': 'Connection error'}
        except Exception as e:
            return {'exists': False, 'node_id': node_id, 'error': str(e)}
    
    def verify_and_update_log(self, sync_log: SyncLog, max_retries: int = 3) -> bool:
        """
        بررسی و به‌روزرسانی sync_log.
        
        Args:
            sync_log: SyncLog instance
            max_retries: حداکثر تعداد retry
            
        Returns:
            True اگر verification موفق بود
        """
        result = self.verify_node_in_core(str(sync_log.node_id))
        
        if result.get('exists'):
            sync_log.mark_verified(core_response=result)
            logger.info(f"Verified node {sync_log.node_id}")
            return True
        else:
            error_msg = result.get('error', 'Node not found in Core')
            
            if sync_log.retry_count < max_retries:
                sync_log.mark_pending_retry()
                logger.warning(f"Node {sync_log.node_id} not found, will retry ({sync_log.retry_count}/{max_retries})")
            else:
                sync_log.mark_failed(error_msg)
                logger.error(f"Node {sync_log.node_id} verification failed after {max_retries} retries")
            
            return False
    
    def verify_batch(self, batch_size: int = 100, max_retries: int = 3) -> Dict[str, int]:
        """
        Verification دسته‌ای نودها.
        
        Args:
            batch_size: تعداد نودها در هر batch
            max_retries: حداکثر تعداد retry
            
        Returns:
            Dict با آمار verification
        """
        unverified_logs = SyncLog.get_unverified_logs(limit=batch_size)
        
        verified_count = 0
        failed_count = 0
        
        for sync_log in unverified_logs:
            if self.verify_and_update_log(sync_log, max_retries):
                verified_count += 1
            else:
                failed_count += 1
            
            # کمی صبر کن تا Core overload نشود
            import time
            time.sleep(0.1)
        
        return {
            'total': len(unverified_logs),
            'verified': verified_count,
            'failed': failed_count
        }
    
    def sync_with_verification(self, batch_size: int = None, verify_after_sync: bool = True) -> Dict[str, Any]:
        """
        ارسال embeddings به Core و بررسی آنها.
        
        Args:
            batch_size: تعداد embeddings در هر batch
            verify_after_sync: آیا بعد از sync، verification انجام شود؟
            
        Returns:
            Dict با نتیجه sync و verification
        """
        # 1. Sync embeddings
        sync_result = self.sync_new_embeddings(batch_size=batch_size)
        
        if sync_result['status'] != 'success':
            return sync_result
        
        result = {
            'status': 'success',
            'synced_count': sync_result.get('synced', 0),
            'verified_count': 0,
            'failed_count': 0
        }
        
        # 2. Verification (اختیاری)
        if verify_after_sync and sync_result.get('synced', 0) > 0:
            # کمی صبر کن تا Core نودها را index کند
            import time
            time.sleep(2)
            
            verify_result = self.verify_batch(batch_size=sync_result.get('synced', 0))
            result['verified_count'] = verify_result['verified']
            result['failed_count'] = verify_result['failed']
        
        return result
    
    def _create_sync_stats(self):
        """ایجاد snapshot آمار sync برای monitoring."""
        try:
            total = Embedding.objects.count()
            synced = Embedding.objects.filter(synced_to_core=True).count()
            
            synced_logs = SyncLog.objects.filter(status='synced').count()
            verified_logs = SyncLog.objects.filter(status='verified').count()
            failed_logs = SyncLog.objects.filter(status='failed').count()
            pending_logs = SyncLog.objects.filter(status='pending').count()
            
            sync_pct = round((synced / total * 100) if total > 0 else 0, 2)
            verify_pct = round((verified_logs / synced_logs * 100) if synced_logs > 0 else 0, 2)
            
            SyncStats.objects.create(
                total_embeddings=total,
                synced_count=synced,
                verified_count=verified_logs,
                failed_count=failed_logs,
                pending_count=pending_logs,
                sync_percentage=sync_pct,
                verification_percentage=verify_pct
            )
            logger.info(f"Created SyncStats snapshot: {synced}/{total} synced")
        except Exception as e:
            logger.error(f"Error creating SyncStats: {e}")

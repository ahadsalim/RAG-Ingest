"""
Core Node Verifier - بررسی و تایید نودها در Core/Qdrant
"""
import logging
import requests
from typing import Dict, Any, Optional, List, Tuple
from django.conf import settings

logger = logging.getLogger(__name__)


class CoreNodeVerifier:
    """بررسی و تایید نودها در Core API"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {'X-API-Key': self.api_key}
    
    def get_node(self, node_id: str, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """
        دریافت اطلاعات نود از Core.
        
        Args:
            node_id: UUID نود
            timeout: حداکثر زمان انتظار (ثانیه)
            
        Returns:
            دیکشنری اطلاعات نود یا None در صورت خطا
        """
        try:
            url = f"{self.base_url}/api/v1/sync/node/{node_id}"
            
            response = requests.get(
                url,
                headers=self.headers,
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.warning(f"Node {node_id} not found in Core")
                return {'exists': False, 'node_id': node_id}
            else:
                logger.error(f"Error getting node {node_id}: {response.status_code} - {response.text[:200]}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout getting node {node_id}")
            return None
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error getting node {node_id}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting node {node_id}: {e}")
            return None
    
    def node_exists(self, node_id: str) -> bool:
        """
        بررسی وجود نود در Core.
        
        Args:
            node_id: UUID نود
            
        Returns:
            True اگر نود موجود باشد
        """
        data = self.get_node(node_id)
        return data is not None and data.get('exists', False)
    
    def verify_node(self, node_id: str, expected_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        تایید صحت داده‌های نود.
        
        Args:
            node_id: UUID نود
            expected_data: داده‌های مورد انتظار
            
        Returns:
            (is_valid, error_messages): (True/False, لیست خطاها)
        """
        data = self.get_node(node_id)
        
        if data is None:
            return False, ["خطا در دریافت نود از Core"]
        
        if not data.get('exists', False):
            return False, [f"نود {node_id} در Core یافت نشد"]
        
        errors = []
        
        # بررسی فیلدهای مهم
        if 'text' in expected_data:
            if data.get('text') != expected_data['text']:
                errors.append("متن با داده مورد انتظار مطابقت ندارد")
        
        if 'document_id' in expected_data:
            if data.get('document_id') != expected_data['document_id']:
                errors.append(f"document_id مطابقت ندارد: {data.get('document_id')} != {expected_data['document_id']}")
        
        if 'document_type' in expected_data:
            if data.get('document_type') != expected_data['document_type']:
                errors.append(f"document_type مطابقت ندارد")
        
        if 'language' in expected_data:
            if data.get('language') != expected_data['language']:
                errors.append(f"language مطابقت ندارد")
        
        # بررسی بردار
        vector = data.get('vector', [])
        if not vector or len(vector) != 768:
            errors.append(f"بردار نامعتبر است (طول: {len(vector)}، انتظار: 768)")
        
        # بررسی metadata
        metadata = data.get('metadata', {})
        if not metadata:
            errors.append("metadata خالی است")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    def verify_multiple_nodes(
        self, 
        node_ids: List[str], 
        max_workers: int = 5
    ) -> Dict[str, Dict[str, Any]]:
        """
        بررسی چندین نود به صورت همزمان.
        
        Args:
            node_ids: لیست UUID های نود
            max_workers: تعداد worker های همزمان
            
        Returns:
            دیکشنری با node_id به عنوان کلید و نتیجه بررسی
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_node = {
                executor.submit(self.node_exists, node_id): node_id 
                for node_id in node_ids
            }
            
            for future in as_completed(future_to_node):
                node_id = future_to_node[future]
                try:
                    exists = future.result()
                    results[node_id] = {
                        'exists': exists,
                        'verified': exists,
                        'error': None if exists else 'نود یافت نشد'
                    }
                except Exception as e:
                    results[node_id] = {
                        'exists': False,
                        'verified': False,
                        'error': str(e)
                    }
        
        return results
    
    def get_node_metadata(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        دریافت فقط metadata نود (بدون بردار).
        
        Args:
            node_id: UUID نود
            
        Returns:
            دیکشنری metadata یا None
        """
        data = self.get_node(node_id)
        
        if data and data.get('exists'):
            return data.get('metadata', {})
        
        return None
    
    def compare_with_local(
        self, 
        node_id: str, 
        local_embedding
    ) -> Tuple[bool, List[str]]:
        """
        مقایسه نود در Core با Embedding محلی.
        
        Args:
            node_id: UUID نود
            local_embedding: Embedding instance از دیتابیس محلی
            
        Returns:
            (is_match, differences): (True/False, لیست تفاوت‌ها)
        """
        from ingest.core.sync.payload_builder import build_summary_payload
        
        # دریافت از Core
        core_data = self.get_node(node_id)
        
        if not core_data or not core_data.get('exists'):
            return False, ["نود در Core یافت نشد"]
        
        # ساخت payload محلی
        local_payload = build_summary_payload(local_embedding)
        
        if not local_payload:
            return False, ["خطا در ساخت payload محلی"]
        
        differences = []
        
        # مقایسه فیلدها
        if core_data.get('text') != local_payload.get('text'):
            differences.append("متن متفاوت است")
        
        if core_data.get('document_id') != local_payload.get('document_id'):
            differences.append("document_id متفاوت است")
        
        if core_data.get('document_type') != local_payload.get('document_type'):
            differences.append("document_type متفاوت است")
        
        # مقایسه metadata
        core_metadata = core_data.get('metadata', {})
        local_metadata = local_payload.get('metadata', {})
        
        for key in ['work_title', 'path_label', 'jurisdiction', 'authority']:
            if core_metadata.get(key) != local_metadata.get(key):
                differences.append(f"metadata.{key} متفاوت است")
        
        is_match = len(differences) == 0
        return is_match, differences


class CoreNodeDeleter:
    """حذف نودها از Core/Qdrant"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.headers = {'X-API-Key': self.api_key}
    
    def delete_node(self, node_id: str, timeout: int = 30) -> Tuple[bool, Optional[str]]:
        """
        حذف نود از Core.
        
        Args:
            node_id: UUID نود
            timeout: حداکثر زمان انتظار
            
        Returns:
            (success, error_message): (True/False, پیام خطا یا None)
        """
        try:
            url = f"{self.base_url}/api/v1/sync/node/{node_id}"
            
            response = requests.delete(
                url,
                headers=self.headers,
                timeout=timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully deleted node {node_id} from Core")
                return True, None
            elif response.status_code == 404:
                logger.warning(f"Node {node_id} not found in Core (already deleted?)")
                return True, None  # اگر نود وجود نداشت، موفق در نظر بگیر
            else:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.error(f"Error deleting node {node_id}: {error_msg}")
                return False, error_msg
                
        except requests.exceptions.Timeout:
            error_msg = f"Timeout deleting node {node_id}"
            logger.error(error_msg)
            return False, error_msg
        except requests.exceptions.ConnectionError:
            error_msg = f"Connection error deleting node {node_id}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error deleting node {node_id}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def delete_multiple_nodes(
        self, 
        node_ids: List[str], 
        max_workers: int = 5
    ) -> Dict[str, Dict[str, Any]]:
        """
        حذف چندین نود به صورت همزمان.
        
        Args:
            node_ids: لیست UUID های نود
            max_workers: تعداد worker های همزمان
            
        Returns:
            دیکشنری با node_id به عنوان کلید و نتیجه حذف
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_node = {
                executor.submit(self.delete_node, node_id): node_id 
                for node_id in node_ids
            }
            
            for future in as_completed(future_to_node):
                node_id = future_to_node[future]
                try:
                    success, error = future.result()
                    results[node_id] = {
                        'deleted': success,
                        'error': error
                    }
                except Exception as e:
                    results[node_id] = {
                        'deleted': False,
                        'error': str(e)
                    }
        
        return results


def create_verifier_from_config():
    """ساخت CoreNodeVerifier از تنظیمات CoreConfig"""
    from ingest.apps.embeddings.models import CoreConfig
    
    config = CoreConfig.get_config()
    
    return CoreNodeVerifier(
        base_url=config.core_api_url,
        api_key=config.core_api_key
    )


def create_deleter_from_config():
    """ساخت CoreNodeDeleter از تنظیمات CoreConfig"""
    from ingest.apps.embeddings.models import CoreConfig
    
    config = CoreConfig.get_config()
    
    return CoreNodeDeleter(
        base_url=config.core_api_url,
        api_key=config.core_api_key
    )

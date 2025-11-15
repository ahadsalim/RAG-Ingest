import hashlib
from datetime import datetime
from typing import Any, Dict
from django.utils import timezone


def calculate_file_hash(file_obj) -> str:
    """Calculate SHA256 hash of a file object."""
    hash_sha256 = hashlib.sha256()
    for chunk in iter(lambda: file_obj.read(4096), b""):
        hash_sha256.update(chunk)
    file_obj.seek(0)  # Reset file pointer
    return hash_sha256.hexdigest()


def format_datetime_iso(dt: datetime) -> str:
    """Format datetime as ISO-8601 with Z timezone."""
    if dt.tzinfo is None:
        dt = timezone.make_aware(dt)
    return dt.isoformat().replace('+00:00', 'Z')


def safe_get_nested(data: Dict[str, Any], keys: str, default=None) -> Any:
    """Safely get nested dictionary value using dot notation."""
    try:
        for key in keys.split('.'):
            data = data[key]
        return data
    except (KeyError, TypeError):
        return default


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to specified length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + '...'


def generate_object_key(context: str, object_id: str, filename: str) -> str:
    """Generate S3 object key based on context."""
    safe_filename = filename.replace(' ', '_').replace('/', '_')
    return f"{context}/{object_id}/{safe_filename}"

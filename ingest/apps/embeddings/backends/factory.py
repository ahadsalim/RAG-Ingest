"""Factory for creating embedding backends."""

import os
import logging
from typing import Optional

from .base import EmbeddingBackend, EmbeddingConfigError

logger = logging.getLogger(__name__)


def get_backend(provider: Optional[str] = None) -> EmbeddingBackend:
    """
    Create and return an embedding backend based on configuration.
    
    Args:
        provider: Override the provider from environment. If None, uses EMBEDDING_PROVIDER.
    
    Returns:
        Configured embedding backend instance.
    
    Raises:
        EmbeddingConfigError: If provider is unknown or configuration is invalid.
    """
    if provider is None:
        provider = os.getenv("EMBEDDING_PROVIDER", "e5").lower()
    else:
        provider = provider.lower()
    
    logger.info(f"Creating embedding backend: {provider}")
    
    if provider == "e5":
        from .e5_multilingual import E5Multilingual
        return E5Multilingual()
    
    else:
        available_providers = ["e5"]
        raise EmbeddingConfigError(
            f"Unknown EMBEDDING_PROVIDER='{provider}'. "
            f"Available providers: {', '.join(available_providers)}"
        )


def list_available_providers() -> list[str]:
    """Return list of available embedding providers."""
    return ["e5"]


def validate_provider_config(provider: str) -> dict:
    """
    Validate configuration for a specific provider.
    
    Returns:
        Dict with validation results and any missing configuration.
    """
    provider = provider.lower()
    validation = {
        'provider': provider,
        'valid': True,
        'missing_config': [],
        'warnings': []
    }
    
    if provider == "e5":
        # Check E5 configuration
        model_name = os.getenv('EMBEDDING_E5_MODEL_NAME', 'intfloat/multilingual-e5-base')
        if not model_name:
            validation['warnings'].append('EMBEDDING_E5_MODEL_NAME not set, using default')
        
        # Check if sentence-transformers is available
        try:
            import sentence_transformers
        except ImportError:
            validation['missing_config'].append('sentence-transformers package')
        
        # Check if transformers is available
        try:
            import transformers
        except ImportError:
            validation['missing_config'].append('transformers package')
    
    else:
        validation['valid'] = False
        validation['missing_config'].append(f'Unknown provider: {provider}')
    
    if validation['missing_config']:
        validation['valid'] = False
    
    return validation


def get_backend_info(provider: Optional[str] = None) -> dict:
    """
    Get information about the current or specified backend.
    
    Returns:
        Dict with backend information including model_id, dimension, etc.
    """
    try:
        backend = get_backend(provider)
        
        info = {
            'provider': provider or os.getenv("EMBEDDING_PROVIDER", "e5"),
            'model_id': backend.model_id(),
            'default_dim': backend.default_dim(),
            'supports_dual_encoder': backend.supports_dual_encoder(),
            'backend_class': backend.__class__.__name__,
        }
        
        # Add provider-specific info
        if hasattr(backend, 'model_name'):
            info['model_name'] = backend.model_name
        if hasattr(backend, 'device'):
            info['device'] = backend.device
        if hasattr(backend, 'model_path'):
            info['model_path'] = backend.model_path
        
        return info
        
    except Exception as e:
        return {
            'provider': provider or os.getenv("EMBEDDING_PROVIDER", "e5"),
            'error': str(e),
            'valid': False
        }

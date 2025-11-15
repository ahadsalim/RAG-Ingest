"""
Text processing utilities for Persian text normalization.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TextNormalizer:
    """Persian text normalizer using hazm library."""
    
    def __init__(self):
        self._normalizer = None
        self._stemmer = None
        self._lemmatizer = None
        
    def _get_normalizer(self):
        """Lazy load hazm normalizer."""
        if self._normalizer is None:
            try:
                from hazm import Normalizer
                self._normalizer = Normalizer()
                logger.info("Hazm normalizer initialized successfully")
            except ImportError:
                logger.warning("hazm library not available - text normalization disabled")
                self._normalizer = False
        return self._normalizer if self._normalizer is not False else None
    
    def _get_stemmer(self):
        """Lazy load hazm stemmer."""
        if self._stemmer is None:
            try:
                from hazm import Stemmer
                self._stemmer = Stemmer()
                logger.info("Hazm stemmer initialized successfully")
            except ImportError:
                logger.warning("hazm library not available - stemming disabled")
                self._stemmer = False
        return self._stemmer if self._stemmer is not False else None
    
    def normalize_text(self, text: str, apply_stemming: bool = False) -> str:
        """
        Normalize Persian text using hazm.
        
        Args:
            text: Input text to normalize
            apply_stemming: Whether to apply stemming (optional)
            
        Returns:
            Normalized text
        """
        if not text or not isinstance(text, str):
            return text or ""
        
        # Get normalizer
        normalizer = self._get_normalizer()
        if not normalizer:
            # Fallback to basic normalization if hazm not available
            return self._basic_normalize(text)
        
        try:
            # Apply hazm normalization
            normalized = normalizer.normalize(text)
            
            # Optional stemming for better embedding quality
            if apply_stemming:
                stemmer = self._get_stemmer()
                if stemmer:
                    # Split into words, stem each word, rejoin
                    words = normalized.split()
                    stemmed_words = []
                    for word in words:
                        try:
                            stemmed = stemmer.stem(word)
                            stemmed_words.append(stemmed)
                        except:
                            # If stemming fails for a word, use original
                            stemmed_words.append(word)
                    normalized = ' '.join(stemmed_words)
            
            return normalized
            
        except Exception as e:
            logger.warning(f"Text normalization failed: {e}, falling back to basic normalization")
            return self._basic_normalize(text)
    
    def _basic_normalize(self, text: str) -> str:
        """
        Basic text normalization without hazm.
        
        Args:
            text: Input text
            
        Returns:
            Basic normalized text
        """
        if not text:
            return ""
        
        # Basic Persian character normalization
        replacements = {
            'ي': 'ی',  # Arabic yeh to Persian yeh
            'ك': 'ک',  # Arabic kaf to Persian kaf
            'ء': '',   # Remove hamza
            '‌': ' ',   # Replace ZWNJ with space
            '\u200c': ' ',  # Replace ZWNJ with space
            '\u200d': ' ',  # Replace ZWJ with space (was empty)
            '\u200e': '',   # Remove LTR mark
            '\u200f': '',   # Remove RTL mark
        }
        
        normalized = text
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        # Clean up multiple spaces
        import re
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip()
        
        return normalized
    
    def prepare_for_embedding(self, text: str) -> str:
        """
        Prepare text for embedding generation.
        
        Args:
            text: Input text
            
        Returns:
            Text ready for embedding
        """
        # Normalize without stemming for embedding (stemming can lose semantic meaning)
        normalized = self.normalize_text(text, apply_stemming=False)
        
        # Additional cleaning for embedding
        if normalized:
            import re
            
            # Forcefully replace all ZWNJ (zero-width non-joiner) with space
            # This ensures consistency even if hazm doesn't handle it properly
            normalized = normalized.replace('‌', ' ').replace('‍', ' ')
            
            # Remove extra whitespace and control characters
            normalized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', normalized)  # Remove control chars
            normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
            normalized = normalized.strip()
        
        return normalized


# Global instance
_text_normalizer = None

def get_text_normalizer() -> TextNormalizer:
    """Get global text normalizer instance."""
    global _text_normalizer
    if _text_normalizer is None:
        _text_normalizer = TextNormalizer()
    return _text_normalizer

def normalize_text(text: str, apply_stemming: bool = False) -> str:
    """Convenience function for text normalization."""
    return get_text_normalizer().normalize_text(text, apply_stemming)

def prepare_for_embedding(text: str) -> str:
    """Convenience function to prepare text for embedding."""
    return get_text_normalizer().prepare_for_embedding(text)

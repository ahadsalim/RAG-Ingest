"""
DEPRECATED: Use ingest.core.forms.fields instead.
This module is kept for backward compatibility.
"""
import warnings
from ingest.core.forms.fields import JalaliDateField, JalaliDateTimeField

# Issue deprecation warning
warnings.warn(
    "ingest.apps.accounts.fields is deprecated. Use ingest.core.forms.fields instead.",
    DeprecationWarning,
    stacklevel=2
)

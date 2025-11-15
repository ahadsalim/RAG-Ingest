"""
DEPRECATED: Use ingest.core.forms.widgets instead.
This module is kept for backward compatibility.
"""
import warnings
from ingest.core.forms.widgets import JalaliDateInput as JalaliDateWidget, JalaliDateTimeInput as JalaliDateTimeWidget

# Issue deprecation warning
warnings.warn(
    "ingest.apps.accounts.widgets is deprecated. Use ingest.core.forms.widgets instead.",
    DeprecationWarning,
    stacklevel=2
)

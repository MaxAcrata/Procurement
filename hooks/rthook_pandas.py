"""Runtime hook to fix pandas circular import in PyInstaller."""
import sys
import os

# Add the pandas._libs.tslibs path to ensure nattype is loaded first
# This fixes the _pandas_datetime_CAPI circular import issue
try:
    # Force import the nattype module which sets _pandas_datetime_CAPI
    import pandas._libs.tslibs.nattype
except (ImportError, AttributeError):
    pass

"""Runtime hook to fix pandas circular import in PyInstaller."""

import contextlib

# Add the pandas._libs.tslibs path to ensure nattype is loaded first
# This fixes the _pandas_datetime_CAPI circular import issue
# Force import the nattype module which sets _pandas_datetime_CAPI
with contextlib.suppress(ImportError, AttributeError):
    import pandas._libs.tslibs.nattype  # noqa: F401

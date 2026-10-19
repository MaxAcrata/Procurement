"""Runtime hook to fix _SixMetaPathImporter missing _path attribute."""

import sys

# Patch six's _SixMetaPathImporter before shiboken6 tries to use it
if "six" in sys.modules:
    importer = getattr(sys.modules["six"], "_SixMetaPathImporter", None)
    if importer is not None and not hasattr(importer, "_path"):
        importer._path = ""

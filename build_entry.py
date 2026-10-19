"""Entry point for PyInstaller build."""

import sys
from pathlib import Path

# Ensure bundled data paths work
BASE_DIR = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))

# Fix six._SixMetaPathImporter missing _path attribute for PySide6/shiboken6
try:
    import six

    if hasattr(six, "_SixMetaPathImporter"):
        importer = six._SixMetaPathImporter
        if not hasattr(importer, "_path"):
            importer._path = ""
except ImportError:
    pass

# Check if GUI mode is requested
if "--gui" in sys.argv or len(sys.argv) == 1:
    # GUI mode
    from gui_app import main

    main()
else:
    # CLI mode
    try:
        from main import app

        app()
    except SystemExit:
        pass
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()

    # Wait for user input before closing console window
    if getattr(sys, "frozen", False):
        print("\nPress Enter to exit...")
        import contextlib

        with contextlib.suppress(EOFError):
            input()

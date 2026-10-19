"""Shared pytest fixtures and configuration."""

import pytest


def pytest_configure(config):
    """Set Qt platform to offscreen before any Qt import."""
    import os

    if "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication instance."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

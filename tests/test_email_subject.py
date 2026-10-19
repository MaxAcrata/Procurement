"""Email subject and supplier email management."""

from __future__ import annotations


def test_email_subject_default_format(tmp_path):
    import gui.services.backend_impl as bi
    from gui.services.backend_impl import ProcurementBackend

    object.__setattr__(bi.settings, "emails_db_path", tmp_path / "emails_db.json")

    backend = ProcurementBackend()
    subject = backend.get_email_subject()
    assert subject.startswith("Заявка от ")
    assert len(subject) > 10  # has a date


def test_email_subject_save_and_load(tmp_path):
    import gui.services.backend_impl as bi
    from gui.services.backend_impl import ProcurementBackend

    object.__setattr__(bi.settings, "emails_db_path", tmp_path / "emails_db.json")

    backend = ProcurementBackend()
    backend.save_email_subject("Заявка от 25.12.2026")
    assert backend.get_email_subject() == "Заявка от 25.12.2026"

    # New backend instance reads the saved value
    backend2 = ProcurementBackend()
    assert backend2.get_email_subject() == "Заявка от 25.12.2026"


def test_email_vm_subject_management(tmp_path):
    from PySide6.QtWidgets import QApplication

    import gui.services.backend_impl as bi
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.email_vm import EmailViewModel

    QApplication.instance() or QApplication([])
    object.__setattr__(bi.settings, "emails_db_path", tmp_path / "emails_db.json")

    backend = ProcurementBackend()
    vm = EmailViewModel(backend)
    vm.refresh()

    assert vm.email_subject.startswith("Заявка от ")

    vm.update_email_subject("Заявка от 01.01.2027")
    assert vm.email_subject == "Заявка от 01.01.2027"

    # Persisted
    assert backend.get_email_subject() == "Заявка от 01.01.2027"


def test_email_vm_add_email(tmp_path):
    from PySide6.QtWidgets import QApplication

    import gui.services.backend_impl as bi
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.email_vm import EmailViewModel

    QApplication.instance() or QApplication([])
    object.__setattr__(bi.settings, "emails_db_path", tmp_path / "emails_db.json")

    backend = ProcurementBackend()
    vm = EmailViewModel(backend)
    vm.refresh()

    vm.add_email("Test Supplier", "test@example.com")
    assert vm.emails.get("Test Supplier") == "test@example.com"


def test_email_vm_add_invalid_email_shows_error(tmp_path):
    from PySide6.QtWidgets import QApplication

    import gui.services.backend_impl as bi
    from gui.services.backend_impl import ProcurementBackend
    from gui.viewmodels.email_vm import EmailViewModel

    QApplication.instance() or QApplication([])
    object.__setattr__(bi.settings, "emails_db_path", tmp_path / "emails_db.json")

    backend = ProcurementBackend()
    vm = EmailViewModel(backend)
    errors: list[str] = []
    vm.error_occurred.connect(errors.append)

    vm.add_email("Test Supplier", "not-an-email")
    assert errors
    assert "Invalid" in errors[0] or "invalid" in errors[0].lower()


def test_send_purchase_order_email_subject_param(tmp_path):
    """Verify subject parameter is accepted (no real send)."""
    from mailer.sender import send_purchase_order_email

    f = tmp_path / "order.xlsx"
    f.write_bytes(b"fake")

    # Should fail on SMTP (no credentials) but accept subject param
    result = send_purchase_order_email(
        to="test@example.com",
        supplier_name="Test",
        attachment_path=f,
        subject="Заявка от 15.06.2026",
    )
    assert result["status"] == "error"  # no SMTP configured
    assert "SMTP" in result["message"] or "credentials" in result["message"].lower()

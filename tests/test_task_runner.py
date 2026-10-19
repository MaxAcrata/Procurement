"""TaskRunner — background execution contract (S1)."""

from __future__ import annotations

import time

import pytest
from PySide6.QtCore import QCoreApplication

from gui.services.task_runner import TaskRunner


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


@pytest.fixture
def runner(qapp):
    r = TaskRunner()
    yield r
    r.shutdown()


def _process_until(predicate, timeout_s: float = 3.0) -> bool:
    app = QCoreApplication.instance()
    assert app is not None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_run_executes_fn_off_caller_and_delivers_result(runner):
    seen: list[str] = []

    def heavy():
        return "done"

    assert runner.run(heavy, on_result=seen.append, on_error=seen.append) is True
    assert runner.busy is True
    assert _process_until(lambda: seen == ["done"])
    assert runner.busy is False


def test_run_delivers_error_message_on_exception(runner):
    errors: list[str] = []

    def boom():
        raise ValueError("kaput")

    assert runner.run(boom, on_result=lambda r: None, on_error=errors.append) is True
    assert _process_until(lambda: bool(errors))
    assert "kaput" in errors[0]


def test_second_run_is_ignored_while_busy(runner):
    results: list[str] = []

    def slow():
        time.sleep(0.2)
        return "first"

    assert runner.run(slow, on_result=results.append, on_error=lambda e: None) is True
    assert runner.run(lambda: "second", on_result=results.append, on_error=lambda e: None) is False
    assert _process_until(lambda: results == ["first"])
    assert results == ["first"]


# --- Task 2: VM integration ---

from pathlib import Path  # noqa: E402


class _FakeBackend:
    def __init__(self, result=None, error=None):
        self._result = result or {"status": "success", "count": 1, "errors": []}
        self._error = error
        self.calls = 0

    def process_files(self, files):
        self.calls += 1
        if self._error:
            raise RuntimeError(self._error)
        return self._result

    def generate_orders(self, output_dir=Path("output")):
        self.calls += 1
        if self._error:
            raise RuntimeError(self._error)
        return [Path("order1.xlsx")]

    def compare(self, order_path, invoice_paths):
        self.calls += 1
        if self._error:
            raise RuntimeError(self._error)
        return []

    def send_emails(self):
        self.calls += 1
        if self._error:
            raise RuntimeError(self._error)
        return [{"supplier": "S", "status": "sent"}]


def test_file_upload_vm_processes_in_background(qapp):
    from gui.viewmodels.file_upload_vm import FileUploadViewModel

    backend = _FakeBackend(result={"status": "success", "count": 2, "errors": []})
    vm = FileUploadViewModel(backend)
    started: list[bool] = []
    finished: list[dict] = []
    vm.processing_started.connect(lambda: started.append(True))
    vm.processing_finished.connect(finished.append)

    vm._files = [Path("a.xlsx")]
    vm.process_files()
    # Must return immediately — work runs on a worker thread.
    assert started == [True]
    assert not finished, "process_files must not block until result"

    assert _process_until(lambda: bool(finished))
    assert finished[0]["count"] == 2
    assert backend.calls == 1


def test_file_upload_vm_error_goes_to_error_occurred(qapp):
    from gui.viewmodels.file_upload_vm import FileUploadViewModel

    backend = _FakeBackend(error="boom")
    vm = FileUploadViewModel(backend)
    errors: list[str] = []
    vm.error_occurred.connect(errors.append)

    vm._files = [Path("a.xlsx")]
    vm.process_files()
    assert not errors, "must not block until error"

    assert _process_until(lambda: bool(errors))
    assert "boom" in errors[0]


def test_orders_vm_generates_in_background(qapp):
    from gui.viewmodels.orders_vm import OrdersViewModel

    backend = _FakeBackend()
    vm = OrdersViewModel(backend)
    generated: list[list] = []
    vm.orders_generated.connect(generated.append)

    vm.generate_orders()
    assert not generated, "generate_orders must not block"

    assert _process_until(lambda: bool(generated))
    assert generated[0] == [Path("order1.xlsx")]


def test_email_vm_sends_in_background(qapp):
    from gui.viewmodels.email_vm import EmailViewModel

    backend = _FakeBackend()
    vm = EmailViewModel(backend)
    sent: list[list] = []
    vm.emails_sent.connect(sent.append)

    vm.send_emails()
    assert not sent, "send_emails must not block"

    assert _process_until(lambda: bool(sent))
    assert sent[0] == [{"supplier": "S", "status": "sent"}]


def test_comparison_vm_compares_in_background(qapp):
    from gui.viewmodels.comparison_vm import ComparisonViewModel

    backend = _FakeBackend()
    vm = ComparisonViewModel(backend)
    done: list[tuple] = []
    vm.comparison_done.connect(lambda results, summary: done.append((results, summary)))

    vm.compare(Path("order.xlsx"), [Path("inv.xlsx")])
    assert not done, "compare must not block"

    assert _process_until(lambda: bool(done))
    assert done[0][0] == []


def test_task_runner_shutdown_stops_thread(qapp):
    runner = TaskRunner()
    assert runner.run(lambda: 1, on_result=lambda r: None, on_error=lambda e: None)
    runner.shutdown()
    # After shutdown the thread should be finished
    assert not runner._thread.isRunning() or runner._thread.wait(500)

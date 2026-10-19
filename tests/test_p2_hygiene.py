"""P2 hygiene: demo supplier names live in a named constant."""

import inspect

import main


def test_demo_suppliers_constant_exists():
    assert isinstance(main.DEMO_SUPPLIERS, tuple)
    assert all(isinstance(name, str) and name for name in main.DEMO_SUPPLIERS)


def test_demo_flow_uses_demo_suppliers_constant():
    source = inspect.getsource(main.demo)
    assert "DEMO_SUPPLIERS" in source
    for name in main.DEMO_SUPPLIERS:
        assert f'"{name}"' not in source

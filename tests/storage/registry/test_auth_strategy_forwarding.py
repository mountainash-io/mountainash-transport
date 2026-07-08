import pytest
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import BackendNotImplementedError
from mountainash_transport.storage.registry import registry as reg
from mountainash_transport.storage.registry import register_storage_backend, get_storage_backend


@pytest.fixture(autouse=True)
def restore_backend_registry():
    """Snapshot the global backend registry and restore it after each test, so the
    temporary LOCAL override below can't leak into other tests."""
    snapshot = dict(reg._backend_registry)
    try:
        yield
    finally:
        reg._backend_registry.clear()
        reg._backend_registry.update(snapshot)


def test_auth_strategy_forwarded_when_set():
    sentinel = object()
    captured = {}

    @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
    class _Probe:
        def __init__(self, profile, *, connection=None, auth_strategy=None):
            captured["auth_strategy"] = auth_strategy

    get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL, None, auth_strategy=sentinel)
    assert captured["auth_strategy"] is sentinel


def test_auth_strategy_omitted_when_none():
    captured = {}

    @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
    class _Probe2:
        def __init__(self, profile, *, connection=None):   # no auth_strategy kwarg
            captured["ok"] = True

    get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL, None)  # must not pass auth_strategy
    assert captured["ok"] is True


def test_auth_strategy_on_incapable_backend_raises_clear_error():
    """A strategy forwarded to a backend whose ctor can't accept it fails with a
    clear BackendNotImplementedError, not a bare TypeError."""
    @register_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL)
    class _NoAuthProbe:
        def __init__(self, profile, *, connection=None):   # no auth_strategy, no **kwargs
            pass

    with pytest.raises(BackendNotImplementedError, match="does not accept"):
        get_storage_backend(
            CONST_STORAGE_PROVIDER_TYPE.LOCAL, None, auth_strategy=object()
        )

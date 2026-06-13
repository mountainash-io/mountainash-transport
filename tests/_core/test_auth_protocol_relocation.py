"""The auth protocols live in _core/http after Phase 3 relocation."""
import pytest


@pytest.mark.unit
def test_protocols_importable_from_new_home():
    from mountainash_transport._core.http.auth_protocol import (  # noqa: F401
        AuthStrategy,
        RefreshableAuthStrategy,
    )


@pytest.mark.unit
def test_apply_only_object_is_authstrategy():
    from mountainash_transport._core.http.auth_protocol import AuthStrategy

    class _Stub:
        def apply(self, kwargs):
            return dict(kwargs)

    assert isinstance(_Stub(), AuthStrategy)

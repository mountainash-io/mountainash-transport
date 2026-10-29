"""Missing-extra conversion: only [http]-stack absence becomes MissingExtraError."""
import pytest

from mountainash_transport import MissingExtraError, StorageError
from mountainash_transport._core.extras import raise_for_missing_extra


def _missing(name: str) -> ModuleNotFoundError:
    return ModuleNotFoundError(f"No module named {name!r}", name=name)


@pytest.mark.parametrize("name", ["httpx", "upath", "mountainash_settings.secrets", "pydantic"])
def test_stack_absence_becomes_typed_error_naming_extra(name):
    original = _missing(name)
    with pytest.raises(MissingExtraError) as caught:
        raise_for_missing_extra("HTTP storage", "http", original)
    err = caught.value
    assert isinstance(err, StorageError) and isinstance(err, ImportError)
    assert err.extra == "http" and err.feature == "HTTP storage"
    assert str(err) == (
        "The [http] extra is required for HTTP storage: "
        "pip install 'mountainash-transport[http]'"
    )
    assert err.__cause__ is original


@pytest.mark.parametrize("exc", [
    _missing("boto3"),
    _missing("pydantic_core"),
    ImportError("cannot import name 'Client' from 'httpx'", name="httpx"),
])
def test_unrelated_import_error_is_not_converted(exc):
    with pytest.raises(type(exc)) as caught:
        raise_for_missing_extra("HTTP storage", "http", exc)
    assert caught.value is exc
    assert not isinstance(caught.value, MissingExtraError)

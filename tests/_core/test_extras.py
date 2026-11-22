"""Missing-extra conversion: a missing module becomes MissingExtraError only for the extra that provides it."""
import pytest

from mountainash_transport import MissingExtraError, StorageError
from mountainash_transport._core.extras import raise_for_missing_extra


def _missing(name: str) -> ModuleNotFoundError:
    return ModuleNotFoundError(f"No module named {name!r}", name=name)


@pytest.mark.parametrize("extra,name", [
    ("http", "httpx"),
    ("http", "upath"),
    ("http", "mountainash_settings.secrets"),
    ("http", "pydantic"),
    ("s3", "boto3"),
    ("s3", "botocore.session"),
    ("s3", "httpx"),            # [s3] includes [http]
    ("sftp", "paramiko"),
    ("sftp", "pydantic"),       # [sftp] includes [http]
    ("encryption", "gnupg"),
    ("oauth1", "authlib"),
])
def test_absence_of_an_extras_module_becomes_typed_error_naming_extra(extra, name):
    original = _missing(name)
    with pytest.raises(MissingExtraError) as caught:
        raise_for_missing_extra("the feature", extra, original)
    err = caught.value
    assert isinstance(err, StorageError) and isinstance(err, ImportError)
    assert err.extra == extra and err.feature == "the feature"
    assert str(err) == (
        f"The [{extra}] extra is required for the feature: "
        f"pip install 'mountainash-transport[{extra}]'"
    )
    assert err.__cause__ is original


@pytest.mark.parametrize("extra,exc", [
    ("http", _missing("boto3")),
    ("encryption", _missing("httpx")),  # [encryption] does not include [http]
    ("sftp", _missing("boto3")),
    ("encryption", _missing("paramiko")),
    ("http", _missing("pydantic_core")),
    ("s3", ImportError("cannot import name 'Config' from 'botocore.config'", name="botocore.config")),
])
def test_module_outside_the_extra_is_not_converted(extra, exc):
    with pytest.raises(type(exc)) as caught:
        raise_for_missing_extra("the feature", extra, exc)
    assert caught.value is exc
    assert not isinstance(caught.value, MissingExtraError)


def test_gpg_without_python_gnupg_names_encryption_extra(monkeypatch):
    import io
    import sys

    from mountainash_transport import GPG

    monkeypatch.setitem(sys.modules, "gnupg", None)
    with pytest.raises(MissingExtraError, match=r"mountainash-transport\[encryption\]") as caught:
        GPG(passphrase="secret").unwrap(io.BytesIO(b"ciphertext"))
    assert caught.value.extra == "encryption"

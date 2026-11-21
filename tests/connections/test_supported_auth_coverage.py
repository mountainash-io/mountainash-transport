"""Every auth mode an implemented provider declares builds a working connection (#7).

A mode listed in ``supported_auth`` that auth-client cannot render for the
provider's SDK would pass the admission check and then fail at first use. This
walks the registry, so a newly declared mode fails here until it is shown to work.
"""
from __future__ import annotations

import typing as t

import pytest
from mountainash_auth_client import (
    CertificateAuthProfile,
    IAMAuthProfile,
    KerberosAuthProfile,
    NoAuthProfile,
    OAuth2AuthProfile,
    PasswordAuthProfile,
    TokenAuthProfile,
)

from mountainash_transport import create_connection
from mountainash_transport.settings.storage.profiles import (
    HTTPStorageProfile,
    LocalStorageProfile,
    S3StorageProfile,
    SFTPStorageProfile,
)
from mountainash_transport.settings.storage.registry import STORAGE_REGISTRY

STORAGE: dict[str, t.Callable[[], t.Any]] = {
    "http": HTTPStorageProfile,
    "local": LocalStorageProfile,
    "s3": lambda: S3StorageProfile(FLAVOR="aws", REGION="us-east-1"),
    "sftp": lambda: SFTPStorageProfile(HOST="files.example.com", USERNAME="u"),
}
AUTH: dict[str, t.Callable[[], t.Any]] = {
    "none": NoAuthProfile,
    "password": lambda: PasswordAuthProfile(USERNAME="u", PASSWORD="p"),
    "token": lambda: TokenAuthProfile(TOKEN="t"),
    "oauth2": lambda: OAuth2AuthProfile(ACCESS_TOKEN="t"),
    "iam": lambda: IAMAuthProfile(ACCESS_KEY_ID="k", SECRET_ACCESS_KEY="s"),
    "certificate": lambda: CertificateAuthProfile(PRIVATE_KEY_PATH="/keys/id_ed25519"),
    "kerberos": KerberosAuthProfile,
}


def _declared() -> list[tuple[str, str]]:
    pairs = []
    for name in sorted(STORAGE_REGISTRY.specs):
        spec = STORAGE_REGISTRY.get_spec(name)
        if spec.implemented:
            pairs += [(name, mode.value) for mode in sorted(spec.supported_auth, key=lambda m: m.value)]
    return pairs


def test_every_implemented_provider_is_covered() -> None:
    implemented = {name for name in STORAGE_REGISTRY.specs if STORAGE_REGISTRY.get_spec(name).implemented}
    assert implemented == set(STORAGE)


@pytest.mark.parametrize(("provider", "mode"), _declared())
def test_declared_mode_builds_a_connection(provider: str, mode: str) -> None:
    assert mode in AUTH, f"{provider} declares {mode!r}: add an auth fixture and prove it here"
    connection = create_connection(STORAGE[provider](), AUTH[mode]())
    try:
        assert connection is not None
    finally:
        close = getattr(connection, "disconnect", None)
        if close is not None:
            close()

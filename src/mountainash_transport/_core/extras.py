"""Translate absence of an optional extra's packages into MissingExtraError."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.exceptions import MissingExtraError

HTTP_STACK: frozenset[str] = frozenset({
    "mountainash_settings", "mountainash_auth_client", "pydantic", "upath", "httpx", "fsspec",
})

# Top-level modules each extra installs, including the extras it pulls in
# (pyproject.toml: [s3], [sftp] and [oauth1] include [http]; [encryption] does not).
EXTRA_MODULES: dict[str, frozenset[str]] = {
    "http": HTTP_STACK,
    "s3": HTTP_STACK | {"boto3", "botocore", "s3transfer", "aiobotocore", "s3fs", "minio"},
    "sftp": HTTP_STACK | {"paramiko", "smart_open"},
    "encryption": frozenset({"gnupg"}),
    "oauth1": HTTP_STACK | {"authlib"},
}


def raise_for_missing_extra(feature: str, extra: str, exc: ImportError) -> t.NoReturn:
    """Raise MissingExtraError if *exc* is a missing module that *extra* installs; else re-raise *exc*.

    Args:
        feature: User-facing name of what needed the extra.
        extra: Extra that provides the missing module.
        exc: The caught import failure.
    """
    missing = (exc.name or "").partition(".")[0] if isinstance(exc, ModuleNotFoundError) else ""
    if missing in EXTRA_MODULES[extra]:
        error = MissingExtraError(
            f"The [{extra}] extra is required for {feature}: "
            f"pip install 'mountainash-transport[{extra}]'",
            name=exc.name,
        )
        error.extra = extra
        error.feature = feature
        raise error from exc
    raise exc

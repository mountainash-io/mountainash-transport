"""Translate absence of an optional extra's packages into MissingExtraError."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.exceptions import MissingExtraError

HTTP_STACK: frozenset[str] = frozenset({
    "mountainash_settings", "mountainash_auth_client", "pydantic", "upath", "httpx", "fsspec",
})


def raise_for_missing_extra(feature: str, extra: str, exc: ImportError) -> t.NoReturn:
    """Raise MissingExtraError for a missing [http]-stack module; otherwise re-raise *exc*.

    Args:
        feature: User-facing name of what needed the extra.
        extra: Extra that provides the missing module.
        exc: The caught import failure.
    """
    if isinstance(exc, ModuleNotFoundError) and (exc.name or "").partition(".")[0] in HTTP_STACK:
        error = MissingExtraError(
            f"The [{extra}] extra is required for {feature}: "
            f"pip install 'mountainash-transport[{extra}]'",
            name=exc.name,
        )
        error.extra = extra
        error.feature = feature
        raise error from exc
    raise exc

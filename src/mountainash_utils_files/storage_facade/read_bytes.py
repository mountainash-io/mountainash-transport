"""Top-level read helper that dispatches by URL scheme.

All schemes — including http/https — route through StorageFacade.from_path().
"""
from __future__ import annotations

import typing

from mountainash_utils_files.path_helpers.suffixes import infer_pipeline
from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_transforms import GPG, Gzip


def read_bytes(
    path: str,
    *,
    auth_params: typing.Any = None,
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
    """Read the full contents of *path* as bytes, dispatching by URL scheme.

    All recognised schemes route through :meth:`StorageFacade.from_path`.

    Args:
        path: Path or URL.
        auth_params: Optional auth params forwarded to the storage facade.
        infer: When True, inspect *path*'s suffix chain and auto-apply a
            read-side ``Pipeline`` for known suffixes (``.gz``, ``.gzip``,
            ``.gpg``, ``.asc``, ``.pgp``). Default False preserves
            byte-for-byte current behaviour.
        gpg: Required when *infer* is True and the suffix chain contains a
            gpg-family suffix. Supplies key material. Ignored when *infer*
            is False.
        gzip: Optional; defaults to ``Gzip()`` when a gzip suffix is seen.
            Ignored when *infer* is False.

    Returns:
        The full content of *path* as ``bytes``, optionally transform-decoded.

    Raises:
        ValueError: If the scheme is unrecognised, describes a backend that
            is not registered, or *infer* is True and a gpg-family suffix
            was seen without a *gpg* instance.
    """
    facade = StorageFacade.from_path(path, auth_params)
    if not infer:
        return facade.read(path)

    pipeline, _stripped = infer_pipeline(path, gpg=gpg, gzip=gzip)
    if pipeline is None:
        return facade.read(path)
    return facade.read(path, pipeline=pipeline)

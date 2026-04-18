"""Top-level read helper that dispatches by URL scheme.

For http/https, uses urllib directly as a temporary bridge until the HTTP
backend follow-up spec ships.
"""
from __future__ import annotations

import io
import typing
import urllib.request

from mountainash_utils_files.path_helpers.storage_path import StoragePath
from mountainash_utils_files.path_helpers.suffixes import infer_pipeline
from mountainash_utils_files.storage_facade.facade import StorageFacade
from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline


def _apply_pipeline_to_bytes(pipeline: Pipeline, raw: bytes) -> bytes:
    """Run *pipeline*'s read-side over *raw* and return the decoded bytes."""
    return pipeline.apply_read(io.BytesIO(raw)).read()


def read_bytes(
    path: str,
    *,
    auth_params: typing.Any = None,
    infer: bool = False,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> bytes:
    """Read the full contents of *path* as bytes, dispatching by URL scheme.

    Local paths and recognised storage schemes route through
    :meth:`StorageFacade.from_path`. ``http://`` and ``https://`` paths use
    ``urllib.request.urlopen`` directly; this branch is removed when the
    HTTP backend follow-up spec ships.

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
    scheme = StoragePath.identify_scheme(path)

    if scheme in ("http", "https"):
        with urllib.request.urlopen(path) as response:  # noqa: S310
            raw = response.read()
        if not infer:
            return raw
        pipeline, _ = infer_pipeline(path, gpg=gpg, gzip=gzip)
        return _apply_pipeline_to_bytes(pipeline, raw) if pipeline else raw

    facade = StorageFacade.from_path(path, auth_params)
    if not infer:
        return facade.read(path)

    pipeline, _stripped = infer_pipeline(path, gpg=gpg, gzip=gzip)
    if pipeline is None:
        return facade.read(path)
    return facade.read(path, pipeline=pipeline)

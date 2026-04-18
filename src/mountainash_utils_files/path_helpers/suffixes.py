"""Suffix-aware transform inference.

Parses a path's suffix chain right-to-left into a Pipeline of stream
transforms. See docs/superpowers/specs/2026-04-18-suffix-aware-transform-inference-design.md.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Optional, Tuple

from mountainash_utils_files.storage_transforms import GPG, Gzip, Pipeline
from mountainash_utils_files.storage_transforms.base import StreamTransform

SUFFIX_TRANSFORMS: dict[str, str] = {
    ".gz":   "gzip",
    ".gzip": "gzip",
    ".gpg":  "gpg",
    ".asc":  "gpg",
    ".pgp":  "gpg",
}


def _split_final_suffix(path: str) -> Tuple[str, str]:
    """Return (stem, suffix) using posix-path rules.

    ``suffix`` is the lowercased final suffix including the dot, or the
    empty string if the final segment has no dot. ``stem`` is ``path``
    with that suffix removed.
    """
    pp = PurePosixPath(path)
    suffix = pp.suffix.lower()
    if not suffix:
        return path, ""
    # Strip only the trailing suffix length — preserves scheme, netloc,
    # and any dots in directory components because pp.suffix is defined
    # against the final name only.
    return path[: -len(suffix)], suffix


def infer_pipeline(
    path: str,
    *,
    gpg: GPG | None = None,
    gzip: Gzip | None = None,
) -> Tuple[Optional[Pipeline], str]:
    """Parse the suffix chain of *path* right-to-left into a Pipeline.

    Stops at the first suffix not in :data:`SUFFIX_TRANSFORMS`. Comparison
    on the suffix is case-insensitive.

    Args:
        path: Any path-like string (local, ``s3://...``, etc). Only the
            suffix portion of the final segment is inspected; no scheme
            validation is performed.
        gpg: Required if the suffix chain contains any of ``.gpg``,
            ``.asc``, ``.pgp``. Supplies key material.
        gzip: Optional; defaults to ``Gzip()`` when a gzip suffix is seen.

    Returns:
        ``(pipeline, stripped_path)``.
          - ``pipeline`` is ``None`` when no known suffixes were found.
          - ``stripped_path`` is *path* with every stripped suffix removed.

    Raises:
        ValueError: A gpg-family suffix was found but ``gpg`` is ``None``.
    """
    outer_to_inner: list[StreamTransform] = []
    current = path
    while True:
        stem, suffix = _split_final_suffix(current)
        if not suffix:
            break
        kind = SUFFIX_TRANSFORMS.get(suffix)
        if kind is None:
            break
        if kind == "gzip":
            outer_to_inner.append(gzip if gzip is not None else Gzip())
        elif kind == "gpg":
            if gpg is None:
                raise ValueError(
                    f"path {path!r} has a {suffix} suffix; "
                    f"pass gpg=GPG(...) to infer"
                )
            outer_to_inner.append(gpg)
        current = stem

    if not outer_to_inner:
        return None, path
    # Walking right-to-left produces outermost-first order, matching
    # Pipeline.__init__'s contract.
    return Pipeline(*outer_to_inner), current

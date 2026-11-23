"""Bulk delete for stores without a batch delete: one native delete per path."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.exceptions import BulkDeleteError, PathNotFoundError, StorageError


def delete_each(delete_file: t.Callable[[str], None], paths: t.Iterable[str]) -> None:
    """Delete every path with *delete_file*; a missing path counts as deleted.

    Every path is attempted. Raises one ``BulkDeleteError`` at the end listing,
    in input order, each path whose delete raised another ``StorageError``.
    """
    failures: list[tuple[str, StorageError]] = []
    for path in paths:
        try:
            delete_file(path)
        except PathNotFoundError:
            continue
        except StorageError as exc:
            failures.append((path, exc))
    if failures:
        raise BulkDeleteError(tuple(failures))

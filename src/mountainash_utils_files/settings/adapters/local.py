"""Local-filesystem adapter — emits handler kwargs from a profile.

Local handlers have no SDK to wrap — the "kwargs" are just
``{root_path, create_path}`` forwarded verbatim. If ``MOUNT_SPEC`` is
set and non-trivial (``mount_type`` is ``nfs`` or ``cifs``), it is
surfaced intact so the handler can issue an OS ``mount`` command
before operating on the path.
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]


_MOUNTABLE_TYPES: frozenset[str] = frozenset({"nfs", "cifs"})


def build_handler_kwargs(profile: "StorageProfile") -> dict[str, t.Any]:
    """Build LocalStorageBackend kwargs from a :class:`LocalSettings` profile.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[Profile], dict[str, Any]]``
    contract; callers always pass a :class:`LocalSettings` instance in
    practice.
    """
    kwargs: dict[str, t.Any] = {
        "root_path": getattr(profile, "ROOT_PATH", None),
        "create_path": bool(getattr(profile, "CREATE_PATH", False)),
    }

    mount_spec = getattr(profile, "MOUNT_SPEC", None)
    if mount_spec:
        mount_type = mount_spec.get("mount_type") if isinstance(mount_spec, dict) else None
        if mount_type in _MOUNTABLE_TYPES:
            kwargs["mount_spec"] = mount_spec

    return kwargs

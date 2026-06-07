"""ftplib adapter — builds ``ftplib.FTP`` / ``FTP_TLS`` constructor kwargs.

Produces a nested envelope:

.. code-block:: python

    {
        "ftp_class_path":  "ftplib.FTP" | "ftplib.FTP_TLS",
        "init_kwargs":     {"host": ..., "user": ..., "passwd": ..., ...},
        "_connect_kwargs": {"port": int},            # for ftp.connect(host, port)
        "_post_connect":   {"passive": True|False},  # for ftp.set_pasv(...)
    }

stdlib :mod:`ftplib` splits its configuration: the ``__init__`` signature
takes most fields but ``port`` flows through ``connect(host, port)`` and
PASV mode via ``set_pasv(...)`` — the envelope keeps each concern
explicit for the handler to route correctly.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import AuthMode, NoAuth, PasswordAuth

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]


# Canonical descriptor-field name → ftplib.FTP ``__init__`` kwarg name.
_INIT_DRIVER_KEYS: tuple[tuple[str, str], ...] = (
    ("HOST", "host"),
    ("USERNAME", "user"),
    ("ACCOUNT", "acct"),
    ("TIMEOUT", "timeout"),
    ("SOURCE_ADDRESS", "source_address"),
    ("ENCODING", "encoding"),
)


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _auth_kwargs(auth: AuthMode | None) -> dict[str, t.Any]:
    """Translate the discriminated auth union into ftplib kwargs.

    - :class:`PasswordAuth` → ``{"passwd": ...}`` (ftplib uses ``passwd``,
      not ``password``). If a username is present on the auth spec, it
      overrides ``USERNAME`` on the profile.
    - :class:`NoAuth`       → ``{}`` (caller relies on
      ``USERNAME="anonymous"``).
    """
    if auth is None:
        return {}
    if isinstance(auth, PasswordAuth):
        out: dict[str, t.Any] = {}
        username = auth.USERNAME
        password = _unwrap_secret(auth.PASSWORD)
        if username:
            out["user"] = username
        if password is not None:
            out["passwd"] = password
        return out
    # NoAuth / anything else: leave init kwargs alone.
    return {}


def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
    """Build an ftplib construction envelope from an :class:`FTPSettings`.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[Profile], dict[str, Any]]``
    contract; callers always pass an :class:`FTPSettings` instance in
    practice.

    Returns a dict with ``ftp_class_path`` + ``init_kwargs`` +
    ``_connect_kwargs`` + ``_post_connect`` — see module docstring.
    """
    use_tls = bool(getattr(profile, "USE_TLS", False))
    ftp_class_path = "ftplib.FTP_TLS" if use_tls else "ftplib.FTP"

    init_kwargs: dict[str, t.Any] = {}
    for field_name, driver_key in _INIT_DRIVER_KEYS:
        value = getattr(profile, field_name, None)
        if value is None:
            continue
        init_kwargs[driver_key] = value

    init_kwargs.update(_auth_kwargs(auth))

    connect_kwargs: dict[str, t.Any] = {}
    port = getattr(profile, "PORT", None)
    if port is not None:
        connect_kwargs["port"] = port

    post_connect: dict[str, t.Any] = {
        "passive": bool(getattr(profile, "PASSIVE_MODE", True)),
    }

    return {
        "ftp_class_path": ftp_class_path,
        "init_kwargs": init_kwargs,
        "_connect_kwargs": connect_kwargs,
        "_post_connect": post_connect,
    }

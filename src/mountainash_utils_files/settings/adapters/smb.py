"""smbprotocol adapter — builds session-registration kwargs from a profile.

Produces a dict suitable for
:func:`smbprotocol.session.Session.register_session` (or whichever
smbprotocol entry-point the handler wraps). Handles the ``DOMAIN\\user``
encoding that smbprotocol expects instead of a separate domain kwarg
and maps the discriminated auth union onto the smbprotocol
``auth_protocol`` string.

``smbprotocol`` is a heavy import and is only pulled in by the handler
itself; this adapter never imports it.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import AuthMode, KerberosAuth, PasswordAuth

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _encode_username(username: t.Optional[str], domain: t.Optional[str]) -> t.Optional[str]:
    """Return ``DOMAIN\\username`` when a domain is set, else plain username."""
    if not username:
        return None
    if domain:
        return f"{domain}\\{username}"
    return username


def _auth_kwargs(
    auth: AuthMode | None,
    profile_username: t.Optional[str],
    domain: t.Optional[str],
) -> dict[str, t.Any]:
    """Translate the discriminated auth union into smbprotocol kwargs.

    - :class:`PasswordAuth` → ``auth_protocol="negotiate"`` +
      ``username = DOMAIN\\user`` + ``password``. ``negotiate`` uses
      SPNEGO to auto-select NTLM or Kerberos — the broadest default in
      heterogeneous AD environments.
    - :class:`KerberosAuth` → ``auth_protocol="kerberos"``. Principal
      (if provided) flows through ``username``.
    """
    if auth is None:
        return {}

    if isinstance(auth, PasswordAuth):
        username = auth.USERNAME or profile_username
        password = _unwrap_secret(auth.PASSWORD)
        encoded_user = _encode_username(username, domain)
        out: dict[str, t.Any] = {"auth_protocol": "negotiate"}
        if encoded_user is not None:
            out["username"] = encoded_user
        if password is not None:
            out["password"] = password
        return out

    if isinstance(auth, KerberosAuth):
        principal = auth.PRINCIPAL or profile_username
        encoded_user = _encode_username(principal, domain)
        out = {"auth_protocol": "kerberos"}
        if encoded_user is not None:
            out["username"] = encoded_user
        return out

    # Unknown auth type — surface no credentials, let the handler decide.
    return {}


def build_handler_kwargs(profile: "StorageProfile", auth: AuthMode | None = None) -> dict[str, t.Any]:
    """Build smbprotocol session-registration kwargs from an :class:`SMBSettings`.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[Profile], dict[str, Any]]``
    contract; callers always pass an :class:`SMBSettings` instance in
    practice.
    """
    server = getattr(profile, "SERVER", None)
    port = getattr(profile, "PORT", 445)
    domain = getattr(profile, "DOMAIN", None)
    username = getattr(profile, "USERNAME", None)
    encrypt = bool(getattr(profile, "ENCRYPT", False))
    connection_timeout = getattr(profile, "CONNECTION_TIMEOUT", None)

    kwargs: dict[str, t.Any] = {
        "server": server,
        "port": port,
        "encrypt": encrypt,
    }
    if connection_timeout is not None:
        kwargs["connection_timeout"] = connection_timeout

    auth_kwargs = _auth_kwargs(auth, username, domain)
    kwargs.update(auth_kwargs)

    # If auth didn't set a username and the profile has one, surface it.
    if "username" not in kwargs:
        encoded_user = _encode_username(username, domain)
        if encoded_user is not None:
            kwargs["username"] = encoded_user

    return kwargs

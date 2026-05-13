"""paramiko SSH adapter — builds ``SSHClient.connect`` kwargs from a profile.

Produces a dict suitable for :meth:`paramiko.SSHClient.connect`. Some
SSH-client configuration (``known_hosts`` loading, missing-host-key
policy) is not a ``connect()`` kwarg; those settings are returned in a
``_post_connect`` sub-dict that the handler applies to the
:class:`paramiko.SSHClient` instance before invoking ``connect``.

All ``paramiko.*`` imports are lazy — the adapter itself never imports
paramiko, so pure-settings usage stays free of that dependency.
"""

from __future__ import annotations

import typing as t

if t.TYPE_CHECKING:
    from ..profile import StorageProfile


__all__ = ["build_handler_kwargs"]


# Canonical descriptor-field name → paramiko ``connect()`` kwarg name.
_DRIVER_KEYS: tuple[tuple[str, str], ...] = (
    ("HOST", "hostname"),
    ("PORT", "port"),
    ("USERNAME", "username"),
    ("TIMEOUT", "timeout"),
    ("BANNER_TIMEOUT", "banner_timeout"),
    ("AUTH_TIMEOUT", "auth_timeout"),
    ("ALLOW_AGENT", "allow_agent"),
    ("LOOK_FOR_KEYS", "look_for_keys"),
    ("COMPRESS", "compress"),
)


def _unwrap_secret(v: t.Any) -> t.Optional[str]:
    if v is None:
        return None
    if hasattr(v, "get_secret_value"):
        return v.get_secret_value()
    return str(v)


def _auth_kwargs(auth: t.Any, host: t.Optional[str]) -> dict[str, t.Any]:
    """Translate the discriminated auth union into ``connect()`` kwargs.

    - :class:`PasswordAuth`    → ``{"password": ...}``
    - :class:`CertificateAuth` → ``{"key_filename": ...}`` when a file path
      is given (paramiko auto-detects RSA/ED25519/ECDSA). If only an
      in-memory private-key blob is provided, it is forwarded as ``pkey``
      for the handler to wrap — loading the key material requires
      paramiko which the adapter avoids importing.
      ``passphrase`` is forwarded when present.
    - :class:`KerberosAuth`    → ``{"gss_auth": True, "gss_host": <host>,
      "gss_kex": True}``
    """
    if auth is None:
        return {}
    auth_type = type(auth).__name__
    out: dict[str, t.Any] = {}

    if auth_type == "PasswordAuth":
        password = _unwrap_secret(getattr(auth, "password", None))
        if password is not None:
            out["password"] = password
        return out

    if auth_type == "CertificateAuth":
        key_path = getattr(auth, "private_key_path", None)
        private_key = getattr(auth, "private_key", None)
        passphrase = _unwrap_secret(getattr(auth, "passphrase", None))
        if key_path:
            out["key_filename"] = str(key_path)
        elif private_key is not None:
            # Surface the raw key material; the handler is responsible
            # for building a ``paramiko.PKey`` subclass from it.
            out["pkey"] = _unwrap_secret(private_key)
        if passphrase is not None:
            out["passphrase"] = passphrase
        return out

    if auth_type == "KerberosAuth":
        out["gss_auth"] = True
        out["gss_kex"] = True
        if host:
            out["gss_host"] = host
        return out

    # Unknown auth type — return no credentials and let paramiko fall
    # back to agent / key discovery (subject to ``allow_agent`` /
    # ``look_for_keys``).
    return out


def build_handler_kwargs(profile: "StorageProfile") -> dict[str, t.Any]:
    """Build paramiko ``SSHClient.connect`` kwargs from an :class:`SSHSettings`.

    Signature widened to ``StorageProfile`` to satisfy the upstream
    ``__adapter__: Callable[[Profile], dict[str, Any]]``
    contract; callers always pass an :class:`SSHSettings` instance in
    practice.

    Returns a dict whose keys match :meth:`paramiko.SSHClient.connect`
    parameters. A nested ``"_post_connect"`` dict carries
    ``known_hosts_file`` / ``host_key_policy`` — these are applied to
    the :class:`SSHClient` instance *before* ``connect()``, not passed
    as kwargs.
    """
    kwargs: dict[str, t.Any] = {}

    for field_name, driver_key in _DRIVER_KEYS:
        value = getattr(profile, field_name, None)
        if value is None:
            continue
        kwargs[driver_key] = value

    host = kwargs.get("hostname") or getattr(profile, "HOST", None)

    auth = getattr(profile, "auth", None)
    kwargs.update(_auth_kwargs(auth, host))

    post_connect: dict[str, t.Any] = {}
    known_hosts = getattr(profile, "KNOWN_HOSTS_FILE", None)
    host_key_policy = getattr(profile, "HOST_KEY_POLICY", None)
    if known_hosts:
        post_connect["known_hosts_file"] = str(known_hosts)
    if host_key_policy:
        post_connect["host_key_policy"] = host_key_policy
    if post_connect:
        kwargs["_post_connect"] = post_connect

    return kwargs

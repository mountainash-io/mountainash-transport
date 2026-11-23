"""SMB / CIFS profile.

Connection-level settings for the :mod:`smbprotocol` SDK; the share and
per-file parameters belong to individual calls. The SMB dialect is
negotiated at session registration, and Kerberos is configured through the
auth profile. :meth:`SMBStorageProfile.to_handler_kwargs` returns kwargs for
``smbprotocol`` session registration. Transport has no SMB backend yet.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_PROFILES

from ...profile_spec import MISSING, ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["SMB_SPEC", "SMBStorageProfile"]


SMB_SPEC = StorageProfileSpec(
    name="smb",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.SMB,
    sdk_package="smbprotocol",
    handler_module="mountainash_transport.storage.backends.smb",
    handler_class="SMBStorageBackend",
    supports_streaming=True,
    supports_multipart=False,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="SERVER",
            type=str,
            tier="core",
            default=MISSING,
            driver_key="server",
            description="SMB server host (IP, hostname, or NetBIOS name).",
        ),
        ParameterSpec(
            name="PORT",
            type=int,
            tier="advanced",
            default=445,
            driver_key="port",
            description="SMB direct-TCP port (default 445).",
        ),
        ParameterSpec(
            name="USERNAME",
            type=t.Optional[str],
            tier="core",
            default=None,
            description=(
                "SMB username. Combined with ``DOMAIN`` by the adapter as "
                "``DOMAIN\\\\user`` before passing to smbprotocol."
            ),
        ),
        ParameterSpec(
            name="DOMAIN",
            type=t.Optional[str],
            tier="advanced",
            default=None,
            description=(
                "AD / Windows domain. Not a separate smbprotocol kwarg — "
                "encoded as ``DOMAIN\\\\username`` on the username field."
            ),
        ),
        ParameterSpec(
            name="ENCRYPT",
            type=bool,
            tier="advanced",
            default=False,
            driver_key="encrypt",
            description="Enable SMB3 session encryption.",
        ),
        ParameterSpec(
            name="CONNECTION_TIMEOUT",
            type=int,
            tier="advanced",
            default=60,
            driver_key="connection_timeout",
            description="Connection / negotiation timeout in seconds.",
        ),
    ],
    default_auth=CONST_AUTH_PROFILES.PASSWORD,
    supported_auth=frozenset({CONST_AUTH_PROFILES.PASSWORD, CONST_AUTH_PROFILES.KERBEROS}),
    implemented=False,
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
# def _adapter(profile: "SMBStorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.smb import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


@register
class SMBStorageProfile(Profile):
    """SMB / CIFS settings.

    Fields are installed from :data:`SMB_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    Auth is resolved via the discriminated ``auth`` union; see
    :meth:`to_handler_kwargs`.

    Auth maps onto smbprotocol ``register_session`` kwargs as follows:
        - :class:`PasswordAuth`  → ``auth_protocol="negotiate"`` (NTLM +
          Kerberos SPNEGO; compatible with AD environments), with
          ``username = "DOMAIN\\\\user"`` when ``DOMAIN`` is set.
        - :class:`KerberosAuth`  → ``auth_protocol="kerberos"``.
    """

    if t.TYPE_CHECKING:
        # Static view of the fields generated from __spec__ (kept in sync by tests).
        SERVER: str
        PORT: int
        USERNAME: str | None
        DOMAIN: str | None
        ENCRYPT: bool
        CONNECTION_TIMEOUT: int

    __spec__ = SMB_SPEC

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        server = getattr(self, "SERVER", "") or ""
        domain = getattr(self, "DOMAIN", None)
        if domain:
            return f"smb://{domain}/{server}"
        return f"smb://{server}"



    def _encode_username(self, username: t.Optional[str], domain: t.Optional[str]) -> t.Optional[str]:
        """Return ``DOMAIN\\username`` when a domain is set, else plain username."""
        if not username:
            return None
        if domain:
            return f"{domain}\\{username}"
        return username


    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build smbprotocol session-registration kwargs from an :class:`SMBSettings`.

        Returns SDK-level config only (server, port, encrypt, timeout,
        profile-level username). Auth credentials (password, Kerberos
        principal) are injected by the auth strategy layer.
        """
        server = getattr(self, "SERVER", None)
        port = getattr(self, "PORT", 445)
        domain = getattr(self, "DOMAIN", None)
        username = getattr(self, "USERNAME", None)
        encrypt = bool(getattr(self, "ENCRYPT", False))
        connection_timeout = getattr(self, "CONNECTION_TIMEOUT", None)

        kwargs: dict[str, t.Any] = {
            "server": server,
            "port": port,
            "encrypt": encrypt,
        }
        if connection_timeout is not None:
            kwargs["connection_timeout"] = connection_timeout

        # Surface profile-level username (with domain encoding) if set.
        encoded_user = self._encode_username(username, domain)
        if encoded_user is not None:
            kwargs["username"] = encoded_user

        return kwargs

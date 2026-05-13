"""SMB / CIFS settings.

Descriptor-driven SMB settings for the :mod:`smbprotocol` SDK. Scope is
the connection layer only — SHARE and per-file parameters are not
connection-level config and belong to call-site API.

The legacy ``SMBStorageAuthSettings`` carried a sea of protocol-version
knobs (``VERSION`` / ``MIN_VERSION`` / ``MAX_VERSION`` / ``PREFERRED_DIALECT`` /
``FALLBACK_VERSIONS``) that are not real smbprotocol params — the SMB
dialect is auto-negotiated at session registration time. All five
fake fields are dropped.

Kerberos configuration folds into :class:`KerberosAuth` (upstream);
the legacy ``USE_KERBEROS`` / ``KERBEROS_KDC`` / ``KERBEROS_REALM`` /
``KERBEROS_KEYTAB`` flat fields are retired.

Adapter
(:func:`mountainash_utils_files.settings.adapters.smb.build_handler_kwargs`)
produces kwargs for :func:`smbprotocol.session.Session.register_session`-style
client construction.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.auth import KerberosAuth, PasswordAuth

from ..base import StorageAuthBase
from ..descriptor import MISSING, ParameterSpec, StorageDescriptor
from ..profile import StorageProfile
from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["SMB_SPEC", "SMBSettings"]


SMB_SPEC = StorageDescriptor(
    name="smb",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.SMB,
    sdk_package="smbprotocol",
    handler_module="mountainash_utils_files.storage_backends.smb",
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
    auth_modes=[PasswordAuth, KerberosAuth],
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
def _adapter(profile: "SMBSettings") -> dict[str, t.Any]:
    from ..adapters.smb import build_handler_kwargs

    return build_handler_kwargs(profile)


@register
class SMBSettings(StorageProfile, StorageAuthBase):
    """SMB / CIFS settings.

    Fields are installed from :data:`SMB_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    Auth is resolved via the discriminated ``auth`` union; see
    :func:`~mountainash_utils_files.settings.adapters.smb.build_handler_kwargs`.

    Auth maps onto smbprotocol ``register_session`` kwargs as follows:
        - :class:`PasswordAuth`  → ``auth_protocol="negotiate"`` (NTLM +
          Kerberos SPNEGO; compatible with AD environments), with
          ``username = "DOMAIN\\\\user"`` when ``DOMAIN`` is set.
        - :class:`KerberosAuth`  → ``auth_protocol="kerberos"``.
    """

    __spec__ = SMB_SPEC
    __adapter__ = staticmethod(_adapter)

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        server = getattr(self, "SERVER", "") or ""
        domain = getattr(self, "DOMAIN", None)
        if domain:
            return f"smb://{domain}/{server}"
        return f"smb://{server}"

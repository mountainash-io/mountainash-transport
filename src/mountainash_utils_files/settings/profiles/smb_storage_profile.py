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

from mountainash_auth_client import CONST_AUTH_MODE
from mountainash_auth_client import AuthProfile, KerberosAuth, PasswordAuth

from ..profile_spec import MISSING, ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile
from ..profile_protocol import StorageProfileProtocol

from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE
from ..utils.secrets import _unwrap_secret

__all__ = ["SMB_SPEC", "SMBStorageProfile"]


SMB_SPEC = StorageProfileSpec(
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
    default_auth=CONST_AUTH_MODE.PASSWORD,
    supported_auth=frozenset({CONST_AUTH_MODE.PASSWORD, CONST_AUTH_MODE.KERBEROS}),
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
    :func:`~mountainash_utils_files.settings.adapters.smb.build_handler_kwargs`.

    Auth maps onto smbprotocol ``register_session`` kwargs as follows:
        - :class:`PasswordAuth`  → ``auth_protocol="negotiate"`` (NTLM +
          Kerberos SPNEGO; compatible with AD environments), with
          ``username = "DOMAIN\\\\user"`` when ``DOMAIN`` is set.
        - :class:`KerberosAuth`  → ``auth_protocol="kerberos"``.
    """

    __spec__ = SMB_SPEC

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        server = getattr(self, "SERVER", "") or ""
        domain = getattr(self, "DOMAIN", None)
        if domain:
            return f"smb://{domain}/{server}"
        return f"smb://{server}"



    def _unwrap_secret(self, v: t.Any) -> t.Optional[str]:
        if v is None:
            return None
        if hasattr(v, "get_secret_value"):
            return v.get_secret_value()
        return str(v)


    def _encode_username(self, username: t.Optional[str], domain: t.Optional[str]) -> t.Optional[str]:
        """Return ``DOMAIN\\username`` when a domain is set, else plain username."""
        if not username:
            return None
        if domain:
            return f"{domain}\\{username}"
        return username


    def _auth_kwargs(self,
        auth_profile: AuthProfile | None,
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
        if auth_profile is None:
            return {}

        if isinstance(auth_profile, PasswordAuth):
            username = auth_profile.USERNAME or profile_username
            password = _unwrap_secret(auth_profile.PASSWORD)
            encoded_user = self._encode_username(username, domain)
            out: dict[str, t.Any] = {"auth_protocol": "negotiate"}
            if encoded_user is not None:
                out["username"] = encoded_user
            if password is not None:
                out["password"] = password
            return out

        if isinstance(auth_profile, KerberosAuth):
            principal = auth_profile.PRINCIPAL or profile_username
            encoded_user = self._encode_username(principal, domain)
            out = {"auth_protocol": "kerberos"}
            if encoded_user is not None:
                out["username"] = encoded_user
            return out

        # Unknown auth type — surface no credentials, let the handler decide.
        return {}


    def to_handler_kwargs(self, auth_profile: AuthProfile | None = None) -> dict[str, t.Any]:
        """Build smbprotocol session-registration kwargs from an :class:`SMBSettings`.

        Signature widened to ``StorageProfile`` to satisfy the upstream
        ``__adapter__: Callable[[Profile], dict[str, Any]]``
        contract; callers always pass an :class:`SMBSettings` instance in
        practice.
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

        auth_kwargs = self._auth_kwargs(auth_profile, username, domain)
        kwargs.update(auth_kwargs)

        # If auth didn't set a username and the profile has one, surface it.
        if "username" not in kwargs:
            encoded_user = self._encode_username(username, domain)
            if encoded_user is not None:
                kwargs["username"] = encoded_user

        return kwargs

"""SFTP storage profile.

Provides :class:`SFTPStorageProfile` — settings for the SFTP storage backend
backed by paramiko. SSH is the connection-layer concern; this profile covers
the storage provider that performs file operations via the SFTP subsystem.

Mirrors the Phase 4 ``S3Settings`` / ``AzureStorageSettings`` pattern: the
class is a two-line shell; all parameters live on :data:`SFTP_SPEC`;
the adapter
(:func:`mountainash_transport.settings.adapters.sftp.build_handler_kwargs`)
produces kwargs for :meth:`paramiko.SSHClient.connect`.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_PROFILES
from mountainash_auth_client.targets import TargetFamily

from ...profile_spec import MISSING, ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE


__all__ = ["SFTP_SPEC", "SFTPStorageProfile"]


_VALID_HOST_KEY_POLICIES: frozenset[str] = frozenset(
    {"reject", "warn", "auto_add", "ignore"}
)



def _validate_host_key_policy(v: str) -> str:
    """Validate the SSH host-key policy."""
    if v not in _VALID_HOST_KEY_POLICIES:
        raise ValueError(
            f"Invalid HOST_KEY_POLICY: {v!r}. Must be one of "
            f"{sorted(_VALID_HOST_KEY_POLICIES)}."
        )
    return v


def _validate_username_required(v: t.Optional[str]) -> str:
    """Require USERNAME on SFTP (overrides the optional base-class default)."""
    if not v:
        raise ValueError("USERNAME is required for SFTP.")
    return v


SFTP_SPEC = StorageProfileSpec(
    name="sftp",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.SFTP,
    sdk_package="paramiko",
    handler_module="mountainash_transport.storage.backends.sftp",
    handler_class="SFTPStorageBackend",
    supports_streaming=True,
    supports_multipart=False,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="HOST",
            type=str,
            tier="core",
            default=MISSING,
            driver_key="hostname",
            description="Remote host (IP or DNS name).",
        ),
        ParameterSpec(
            name="PORT",
            type=int,
            tier="core",
            default=22,
            driver_key="port",
            description="SSH port (default 22).",
        ),
        ParameterSpec(
            name="USERNAME",
            type=str,
            tier="core",
            default=MISSING,
            driver_key="username",
            validator=_validate_username_required,
            description="SFTP username — required.",
        ),
        ParameterSpec(
            name="TIMEOUT",
            type=float,
            tier="advanced",
            default=30.0,
            driver_key="timeout",
            description="TCP-connect timeout in seconds.",
        ),
        ParameterSpec(
            name="BANNER_TIMEOUT",
            type=t.Optional[float],
            tier="advanced",
            default=None,
            driver_key="banner_timeout",
            description="Timeout for the SSH banner exchange (seconds).",
        ),
        ParameterSpec(
            name="AUTH_TIMEOUT",
            type=t.Optional[float],
            tier="advanced",
            default=None,
            driver_key="auth_timeout",
            description="Authentication timeout (seconds).",
        ),
        ParameterSpec(
            name="ALLOW_AGENT",
            type=bool,
            tier="advanced",
            default=True,
            driver_key="allow_agent",
            description="Whether paramiko may consult an SSH agent.",
        ),
        ParameterSpec(
            name="LOOK_FOR_KEYS",
            type=bool,
            tier="advanced",
            default=True,
            driver_key="look_for_keys",
            description="Whether paramiko may probe ``~/.ssh/`` for keys.",
        ),
        ParameterSpec(
            name="COMPRESS",
            type=bool,
            tier="advanced",
            default=False,
            driver_key="compress",
            description="Enable zlib compression on the SSH channel.",
        ),
        ParameterSpec(
            name="KNOWN_HOSTS_FILE",
            type=t.Optional[str],
            tier="advanced",
            default=None,
            description=(
                "Path to a ``known_hosts`` file. Applied post-connect via "
                "``SSHClient.load_host_keys(...)`` — not a ``connect()`` kwarg."
            ),
        ),
        ParameterSpec(
            name="HOST_KEY_POLICY",
            type=str,
            tier="advanced",
            default="reject",
            validator=_validate_host_key_policy,
            description=(
                "Missing-host-key policy: reject | warn | auto_add | ignore. "
                "Applied via ``SSHClient.set_missing_host_key_policy(...)``."
            ),
        ),
    ],
    default_auth=CONST_AUTH_PROFILES.PASSWORD,
    supported_auth=frozenset({CONST_AUTH_PROFILES.PASSWORD, CONST_AUTH_PROFILES.CERTIFICATE, CONST_AUTH_PROFILES.KERBEROS, CONST_AUTH_PROFILES.NONE}),
)


def _sftp_paramiko_kwargs(profile: "SFTPStorageProfile", kw: dict[str, t.Any]) -> dict[str, t.Any]:
    """Compose on the driver_key merge (kw) and append the post-connect envelope."""
    result: dict[str, t.Any] = dict(kw)
    post_connect: dict[str, t.Any] = {}
    known_hosts = getattr(profile, "KNOWN_HOSTS_FILE", None)
    host_key_policy = getattr(profile, "HOST_KEY_POLICY", None)
    if known_hosts:
        post_connect["known_hosts_file"] = str(known_hosts)
    if host_key_policy:
        post_connect["host_key_policy"] = host_key_policy
    if post_connect:
        result["_post_connect"] = post_connect
    return result


@register
class SFTPStorageProfile(Profile):
    """SFTP storage settings backed by paramiko.

    Fields are installed from :data:`SFTP_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    Auth is resolved via the discriminated ``auth`` union; see
    :func:`~mountainash_transport.settings.adapters.sftp.build_handler_kwargs`.

    Auth maps onto paramiko ``SSHClient.connect`` kwargs as follows:
        - :class:`PasswordAuth`    → ``password``
        - :class:`CertificateAuth` → ``key_filename`` (file path) or ``pkey``
          (paramiko key object), plus optional ``passphrase``
        - :class:`KerberosAuth`    → ``gss_auth=True`` + ``gss_host`` +
          ``gss_kex=True``
    """

    __spec__ = SFTP_SPEC
    __adapters__ = {TargetFamily.PARAMIKO: _sftp_paramiko_kwargs}

    def _sdk_family(self) -> TargetFamily:
        return TargetFamily.PARAMIKO

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        host = getattr(self, "HOST", "") or ""
        port = getattr(self, "PORT", 22)
        user = getattr(self, "USERNAME", None)
        root = getattr(self, "ROOT_PATH", None)
        user_part = f"{user}@" if user else ""
        url = f"sftp://{user_part}{host}:{port}"
        if root:
            url = f"{url}{root}"
        return url




    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Deprecated shim (Phase 4 D2a) → emit(TargetFamily.PARAMIKO).

        Returns SDK-level config only (hostname, port, timeout, agent/key
        discovery flags, post-connect envelope). Auth credentials (password,
        key, Kerberos) are injected by the auth strategy layer.
        """
        return self.emit(self._sdk_family())

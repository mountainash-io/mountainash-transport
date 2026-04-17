"""Unified SSH + SFTP settings.

Collapses the legacy ``SSHStorageAuthSettings`` and ``SFTPStorageAuthSettings``
into a single :class:`SSHSettings` class. Both providers wrap paramiko's
:class:`paramiko.SSHClient.connect` — the SFTP distinction is whether the
caller opens the SFTP subsystem after connecting vs issuing ``exec_command``.
There is no difference in connection kwargs, so one settings class covers
both providers.

Mirrors the Phase 4 ``S3Settings`` / ``AzureStorageSettings`` pattern: the
class is a two-line shell; all parameters live on :data:`SSH_DESCRIPTOR`;
the adapter
(:func:`mountainash_utils_files.settings.adapters.ssh.build_handler_kwargs`)
produces kwargs for :meth:`paramiko.SSHClient.connect`.
"""

from __future__ import annotations

import typing as t

from mountainash_settings.auth import CertificateAuth, KerberosAuth, PasswordAuth

from ..base import StorageAuthBase
from ..descriptor import MISSING, ParameterSpec, StorageDescriptor
from ..profile import StorageProfile
from ..registry import register
from ...constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["SSH_DESCRIPTOR", "SSHSettings"]


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
    """Require USERNAME on SSH (overrides the optional base-class default)."""
    if not v:
        raise ValueError("USERNAME is required for SSH.")
    return v


SSH_DESCRIPTOR = StorageDescriptor(
    name="ssh",
    # Canonical provider_type is SSH; SFTPStorageAuthSettings is a pure
    # alias pointing at the same class (see providers/__init__.py).
    provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH,
    sdk_package="paramiko",
    handler_module="mountainash_utils_files.storage_backends.ssh",
    handler_class="SSHStorageBackend",
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
            description="SSH username — required.",
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
    auth_modes=[PasswordAuth, CertificateAuth, KerberosAuth],
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
def _adapter(profile: "SSHSettings") -> dict[str, t.Any]:
    from ..adapters.ssh import build_handler_kwargs

    return build_handler_kwargs(profile)


@register(SSH_DESCRIPTOR)
class SSHSettings(StorageProfile, StorageAuthBase):
    """Unified SSH / SFTP settings.

    Fields are installed from :data:`SSH_DESCRIPTOR` by the
    :class:`~mountainash_settings.profiles.DescriptorProfile` metaclass.
    Auth is resolved via the discriminated ``auth`` union; see
    :func:`~mountainash_utils_files.settings.adapters.ssh.build_handler_kwargs`.

    Auth maps onto paramiko ``SSHClient.connect`` kwargs as follows:
        - :class:`PasswordAuth`    → ``password``
        - :class:`CertificateAuth` → ``key_filename`` (file path) or ``pkey``
          (paramiko key object), plus optional ``passphrase``
        - :class:`KerberosAuth`    → ``gss_auth=True`` + ``gss_host`` +
          ``gss_kex=True``
    """

    __descriptor__ = SSH_DESCRIPTOR
    __adapter__ = staticmethod(_adapter)

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        host = getattr(self, "HOST", "") or ""
        port = getattr(self, "PORT", 22)
        user = getattr(self, "USERNAME", None)
        root = getattr(self, "ROOT_PATH", None)
        user_part = f"{user}@" if user else ""
        url = f"ssh://{user_part}{host}:{port}"
        if root:
            url = f"{url}{root}"
        return url

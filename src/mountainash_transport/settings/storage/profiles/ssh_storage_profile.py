"""Unified SSH + SFTP settings.

Collapses the legacy ``SSHStorageAuthSettings`` and ``SFTPStorageAuthSettings``
into a single :class:`SSHStorageProfile` class. Both providers wrap paramiko's
:class:`paramiko.SSHClient.connect` — the SFTP distinction is whether the
caller opens the SFTP subsystem after connecting vs issuing ``exec_command``.
There is no difference in connection kwargs, so one settings class covers
both providers.

Mirrors the Phase 4 ``S3Settings`` / ``AzureStorageSettings`` pattern: the
class is a two-line shell; all parameters live on :data:`SSH_SPEC`;
the adapter
(:func:`mountainash_transport.settings.adapters.ssh.build_handler_kwargs`)
produces kwargs for :meth:`paramiko.SSHClient.connect`.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_MODE

from ...profile_spec import MISSING, ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile

from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE


__all__ = ["SSH_SPEC", "SSHStorageProfile"]


_VALID_HOST_KEY_POLICIES: frozenset[str] = frozenset(
    {"reject", "warn", "auto_add", "ignore"}
)



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


SSH_SPEC = StorageProfileSpec(
    name="ssh",
    # Canonical provider_type is SSH; SFTPStorageAuthSettings is a pure
    # alias pointing at the same class (see providers/__init__.py).
    provider_type=CONST_STORAGE_PROVIDER_TYPE.SSH,
    sdk_package="paramiko",
    handler_module="mountainash_transport.storage.backends.sftp",
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
    default_auth=CONST_AUTH_MODE.PASSWORD,
    supported_auth=frozenset({CONST_AUTH_MODE.PASSWORD, CONST_AUTH_MODE.CERTIFICATE, CONST_AUTH_MODE.KERBEROS}),
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
# def _adapter(profile: "SSHStorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.ssh import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


@register
class SSHStorageProfile(Profile):
    """Unified SSH / SFTP settings.

    Fields are installed from :data:`SSH_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    Auth is resolved via the discriminated ``auth`` union; see
    :func:`~mountainash_transport.settings.adapters.ssh.build_handler_kwargs`.

    Auth maps onto paramiko ``SSHClient.connect`` kwargs as follows:
        - :class:`PasswordAuth`    → ``password``
        - :class:`CertificateAuth` → ``key_filename`` (file path) or ``pkey``
          (paramiko key object), plus optional ``passphrase``
        - :class:`KerberosAuth`    → ``gss_auth=True`` + ``gss_host`` +
          ``gss_kex=True``
    """

    __spec__ = SSH_SPEC

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




    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build paramiko ``SSHClient.connect`` kwargs from an :class:`SSHSettings`.

        Returns SDK-level config only (hostname, port, timeout, agent/key
        discovery flags, post-connect envelope). Auth credentials (password,
        key, Kerberos) are injected by the auth strategy layer.
        """
        kwargs: dict[str, t.Any] = {}

        for field_name, driver_key in _DRIVER_KEYS:
            value = getattr(self, field_name, None)
            if value is None:
                continue
            kwargs[driver_key] = value

        post_connect: dict[str, t.Any] = {}
        known_hosts = getattr(self, "KNOWN_HOSTS_FILE", None)
        host_key_policy = getattr(self, "HOST_KEY_POLICY", None)
        if known_hosts:
            post_connect["known_hosts_file"] = str(known_hosts)
        if host_key_policy:
            post_connect["host_key_policy"] = host_key_policy
        if post_connect:
            kwargs["_post_connect"] = post_connect

        return kwargs

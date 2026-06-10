"""FTP / FTPS settings.

Descriptor-driven FTP settings class. Wraps stdlib :mod:`ftplib` —
either :class:`ftplib.FTP` (when ``USE_TLS=False``) or
:class:`ftplib.FTP_TLS`. The adapter
(:func:`mountainash_transport.settings.adapters.ftp.build_handler_kwargs`)
returns constructor kwargs plus a ``_connect_kwargs`` / ``_post_connect``
envelope for settings (``port``, ``passive`` mode) that stdlib ``ftplib``
applies after ``__init__``.
"""

from __future__ import annotations

import typing as t

from mountainash_auth_client import CONST_AUTH_MODE

from ...profile_spec import MISSING, ParameterSpec, StorageProfileSpec
from mountainash_settings.profiles import Profile
from ..registry import register
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

__all__ = ["FTP_SPEC", "FTPStorageProfile"]

    # Canonical descriptor-field name → ftplib.FTP ``__init__`` kwarg name.
_INIT_DRIVER_KEYS: tuple[tuple[str, str], ...] = (
    ("HOST", "host"),
    ("USERNAME", "user"),
    ("ACCOUNT", "acct"),
    ("TIMEOUT", "timeout"),
    ("SOURCE_ADDRESS", "source_address"),
    ("ENCODING", "encoding"),
)



FTP_SPEC = StorageProfileSpec(
    name="ftp",
    provider_type=CONST_STORAGE_PROVIDER_TYPE.FTP,
    sdk_package=None,  # stdlib ftplib
    handler_module="mountainash_transport.storage.backends.ftp",
    handler_class="FTPStorageBackend",
    supports_streaming=True,
    supports_multipart=False,
    read_only=False,
    parameters=[
        ParameterSpec(
            name="HOST",
            type=str,
            tier="core",
            default=MISSING,
            driver_key="host",
            description="FTP server host (IP or DNS name).",
        ),
        ParameterSpec(
            name="PORT",
            type=int,
            tier="core",
            default=21,
            description=(
                "FTP server port. NOT passed to the ``ftplib.FTP`` "
                "constructor — stdlib takes port via ``connect(host, port)``. "
                "Carried in the adapter's ``_connect_kwargs`` envelope."
            ),
        ),
        ParameterSpec(
            name="USERNAME",
            type=str,
            tier="advanced",
            default="anonymous",
            driver_key="user",
            description=(
                "FTP username. Defaults to ``anonymous`` — combine with "
                "``NoAuth`` to get a classic anonymous login."
            ),
        ),
        ParameterSpec(
            name="ACCOUNT",
            type=t.Optional[str],
            tier="advanced",
            default=None,
            driver_key="acct",
            description=(
                "Optional FTP account (``acct``) argument. Rare — used by "
                "a few legacy FTP servers."
            ),
        ),
        ParameterSpec(
            name="TIMEOUT",
            type=t.Optional[float],
            tier="advanced",
            default=None,
            driver_key="timeout",
            description="TCP-connect timeout in seconds.",
        ),
        ParameterSpec(
            name="SOURCE_ADDRESS",
            type=t.Optional[str],
            tier="advanced",
            default=None,
            driver_key="source_address",
            description=(
                "Local address to bind the outbound TCP connection to "
                "(``source_address`` kwarg). Accepts a hostname or IP."
            ),
        ),
        ParameterSpec(
            name="ENCODING",
            type=str,
            tier="advanced",
            default="utf-8",
            driver_key="encoding",
            description="Text encoding for control-channel messages.",
        ),
        ParameterSpec(
            name="USE_TLS",
            type=bool,
            tier="core",
            default=False,
            description=(
                "If True, use :class:`ftplib.FTP_TLS` and return ``ftps://`` "
                "URLs. Otherwise fall back to plain :class:`ftplib.FTP`."
            ),
        ),
        ParameterSpec(
            name="PASSIVE_MODE",
            type=bool,
            tier="advanced",
            default=True,
            description=(
                "Whether to request PASV mode. Applied after "
                "construction via ``FTP.set_pasv(True|False)``."
            ),
        ),
    ],
    default_auth=CONST_AUTH_MODE.PASSWORD,
    supported_auth=frozenset({CONST_AUTH_MODE.PASSWORD, CONST_AUTH_MODE.NONE}),
    implemented=False,
)


# Adapter is imported lazily to avoid a circular import with the adapters
# package which depends on StorageProfile.
# def _adapter(profile: "FTPStorageProfile", auth=None) -> dict[str, t.Any]:
#     from ..adapters.ftp import build_handler_kwargs

#     return build_handler_kwargs(profile, auth)


@register
class FTPStorageProfile(Profile):
    """FTP / FTPS settings.

    Fields are installed from :data:`FTP_SPEC` by the
    :class:`~mountainash_settings.profiles.Profile` metaclass.
    Auth is resolved via the discriminated ``auth`` union:
        - :class:`PasswordAuth` → ``{passwd: ...}`` (ftplib uses ``passwd``)
        - :class:`NoAuth`       → anonymous login (``user="anonymous"``,
          no password required)

    The adapter returns a nested envelope:

    .. code-block:: python

        {
            "ftp_class_path": "ftplib.FTP" | "ftplib.FTP_TLS",
            "init_kwargs":    {"user": ..., "passwd": ..., "acct": ..., ...},
            "_connect_kwargs": {"port": int},         # ftp.connect(host, port)
            "_post_connect":   {"passive": True|False},  # ftp.set_pasv(...)
        }

    The handler is responsible for instantiating the right ``ftplib``
    class and applying the connect/post-connect steps.
    """

    __spec__ = FTP_SPEC

    def get_connection_url(self) -> str:
        """Return a best-effort connection URL for logging/inspection."""
        scheme = "ftps" if getattr(self, "USE_TLS", False) else "ftp"
        host = getattr(self, "HOST", "") or ""
        port = getattr(self, "PORT", 21)
        user = getattr(self, "USERNAME", None) or "anonymous"
        root = getattr(self, "ROOT_PATH", None)
        url = f"{scheme}://{user}@{host}:{port}"
        if root:
            url = f"{url}{root}"
        return url






    def to_handler_kwargs(self) -> dict[str, t.Any]:
        """Build an ftplib construction envelope from an :class:`FTPSettings`.

        Returns SDK-level config only (ftp class, init kwargs from profile
        fields, connect kwargs, post-connect envelope). Auth credentials
        (user override, passwd) are injected by the auth strategy layer.
        """
        use_tls = bool(getattr(self, "USE_TLS", False))
        ftp_class_path = "ftplib.FTP_TLS" if use_tls else "ftplib.FTP"

        init_kwargs: dict[str, t.Any] = {}
        for field_name, driver_key in _INIT_DRIVER_KEYS:
            value = getattr(self, field_name, None)
            if value is None:
                continue
            init_kwargs[driver_key] = value

        connect_kwargs: dict[str, t.Any] = {}
        port = getattr(self, "PORT", None)
        if port is not None:
            connect_kwargs["port"] = port

        post_connect: dict[str, t.Any] = {
            "passive": bool(getattr(self, "PASSIVE_MODE", True)),
        }

        return {
            "ftp_class_path": ftp_class_path,
            "init_kwargs": init_kwargs,
            "_connect_kwargs": connect_kwargs,
            "_post_connect": post_connect,
        }

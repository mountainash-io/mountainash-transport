"""Auth strategies — inject credentials into SDK client kwargs."""
from __future__ import annotations

import base64
import importlib
import typing as t

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Inject auth credentials into SDK client kwargs.

    Returns a NEW dict — does not mutate the input.
    """

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]: ...


class NoAuthStrategy:
    """Passthrough — no credentials injected."""

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return {**kwargs}


class BearerTokenStrategy:
    """Inject a Bearer token into the Authorization header."""

    def __init__(self, token: str) -> None:
        self._token = token

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        existing = dict(result.get("headers", {}))
        existing["Authorization"] = f"Bearer {self._token}"
        result["headers"] = existing
        return result


class BasicAuthStrategy:
    """Inject HTTP Basic auth into the Authorization header."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        encoded = base64.b64encode(
            f"{self._username}:{self._password}".encode()
        ).decode()
        existing = dict(result.get("headers", {}))
        existing["Authorization"] = f"Basic {encoded}"
        result["headers"] = existing
        return result


class IAMCredentialStrategy:
    """Inject AWS IAM credentials into boto3 client kwargs."""

    def __init__(
        self,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
    ) -> None:
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._session_token = session_token

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        if self._access_key_id:
            result["aws_access_key_id"] = self._access_key_id
        if self._secret_access_key:
            result["aws_secret_access_key"] = self._secret_access_key
        if self._session_token:
            result["aws_session_token"] = self._session_token
        return result


class OAuth1SignedStrategy:
    """Inject authlib OAuth1Auth handler into httpx kwargs (auth= parameter)."""

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        oauth_token: str,
        oauth_token_secret: str,
    ) -> None:
        self._consumer_key = consumer_key
        self._consumer_secret = consumer_secret
        self._oauth_token = oauth_token
        self._oauth_token_secret = oauth_token_secret

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        try:
            _mod = importlib.import_module("authlib.integrations.httpx_client.oauth1_client")
            AuthlibOAuth1Auth = _mod.OAuth1Auth
        except ImportError as exc:
            raise ImportError(
                "OAuth1 requires authlib: pip install mountainash-transport[oauth1]"
            ) from exc

        result = {**kwargs}
        result["auth"] = AuthlibOAuth1Auth(
            client_id=self._consumer_key,
            client_secret=self._consumer_secret,
            token=self._oauth_token,
            token_secret=self._oauth_token_secret,
        )
        return result


# ---------------------------------------------------------------------------
# SSH strategies
# ---------------------------------------------------------------------------


def _parse_private_key(
    key_string: str,
    passphrase: str | None,
) -> t.Any:
    """Parse a PEM/OpenSSH private key string into a paramiko PKey object.

    Tries RSAKey, Ed25519Key, ECDSAKey, DSSKey in order.  Raises
    ``ValueError`` if none of the concrete classes accept the key material.
    """
    try:
        paramiko = importlib.import_module("paramiko")
    except ImportError as exc:
        raise ImportError(
            "SSH key parsing requires paramiko: pip install mountainash-transport[sftp]"
        ) from exc

    import io

    key_classes = [
        paramiko.RSAKey,
        paramiko.Ed25519Key,
        paramiko.ECDSAKey,
        paramiko.DSSKey,
    ]
    for cls in key_classes:
        try:
            return cls.from_private_key(io.StringIO(key_string), password=passphrase)
        except paramiko.SSHException:
            continue

    raise ValueError("Could not parse private key: no supported key type matched.")


class SSHPasswordStrategy:
    """Inject a plaintext password into paramiko connect kwargs."""

    def __init__(self, password: str) -> None:
        self._password = password

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        result["password"] = self._password
        return result


class SSHKeyStrategy:
    """Inject a private key (file path or raw PEM string) into paramiko connect kwargs."""

    def __init__(
        self,
        key_path: str | None = None,
        key_string: str | None = None,
        passphrase: str | None = None,
    ) -> None:
        if key_path is None and key_string is None:
            raise ValueError("SSHKeyStrategy requires either key_path or key_string.")
        self._key_path = key_path
        self._key_string = key_string
        self._passphrase = passphrase

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        if self._key_path is not None:
            result["key_filename"] = self._key_path
            if self._passphrase is not None:
                result["passphrase"] = self._passphrase
        else:
            result["pkey"] = _parse_private_key(self._key_string, self._passphrase)  # type: ignore[arg-type]
        return result


class SSHKerberosStrategy:
    """Inject GSS/Kerberos auth flags into paramiko connect kwargs."""

    def __init__(
        self,
        gss_kex: bool = False,
        gss_host: str | None = None,
    ) -> None:
        self._gss_kex = gss_kex
        self._gss_host = gss_host

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        result = {**kwargs}
        result["gss_auth"] = True
        if self._gss_kex:
            result["gss_kex"] = True
        if self._gss_host is not None:
            result["gss_host"] = self._gss_host
        return result

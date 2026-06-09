"""GPG encryption / decryption transform.

Requires the optional [encryption] extra (python-gnupg).

Note: python-gnupg does not stream — the full encoded/decoded payload is
materialized in memory inside the underlying python-gnupg call. This
transform therefore buffers the payload in io.BytesIO. For very large
files, materialize the source (or switch to disk-backed materialize())
before calling wrap/unwrap.
"""

from __future__ import annotations

import io
from typing import Any, BinaryIO

from mountainash_transport.exceptions import TransformError
from .base import StreamTransform

#TERCHDEBT: Need to use GPGHelper here!

def _import_gnupg() -> Any:
    try:
        import gnupg
    except ImportError as exc:
        raise ImportError(
            "The GPG transform requires the [encryption] extra. "
            "Install with: pip install 'mountainash-transport[encryption]'"
        ) from exc
    return gnupg


class GPG(StreamTransform):
    """GPG transform — encrypts on wrap, decrypts on unwrap.

    Args:
        recipients: List of GPG recipient identifiers. Required for wrap()
            (encryption). Not required for unwrap() (decryption).
        gnupghome: Path to the GPG home directory. None → gpg default.
        key_file: Optional path to a key file to import on first use.
        passphrase: Passphrase for the private key (if decryption requires it).
        armor: If True, produce ASCII-armored output on wrap. Default False
            (binary output — smaller).
        always_trust: If True, skip GPG's ownertrust check on wrap.
    """

    def __init__(
        self,
        recipients: list[str] | None = None,
        gnupghome: str | None = None,
        key_file: str | None = None,
        passphrase: str | None = None,
        armor: bool = False,
        always_trust: bool = False,
    ) -> None:
        self.recipients = recipients
        self.gnupghome = gnupghome
        self.key_file = key_file
        self.passphrase = passphrase
        self.armor = armor
        self.always_trust = always_trust
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            gnupg = _import_gnupg()
            self._client = (
                gnupg.GPG(gnupghome=self.gnupghome)
                if self.gnupghome
                else gnupg.GPG()
            )
            if self.key_file is not None:
                with open(self.key_file, "rb") as fh:
                    self._client.import_keys(fh.read())
        return self._client

    def wrap(self, stream: BinaryIO) -> BinaryIO:
        if not self.recipients:
            raise TransformError(
                "GPG.wrap() requires recipients. Construct GPG(recipients=[...])."
            )
        client = self._get_client()
        result = client.encrypt_file(
            stream,
            recipients=list(self.recipients),
            armor=self.armor,
            always_trust=self.always_trust,
        )
        if not getattr(result, "ok", False):
            status = getattr(result, "status", "unknown")
            raise TransformError(f"GPG encryption failed: {status}")
        return io.BytesIO(bytes(result.data))

    def unwrap(self, stream: BinaryIO) -> BinaryIO:
        client = self._get_client()
        result = client.decrypt_file(stream, passphrase=self.passphrase)
        if not getattr(result, "ok", False):
            status = getattr(result, "status", "unknown")
            raise TransformError(f"GPG decryption failed: {status}")
        return io.BytesIO(bytes(result.data))

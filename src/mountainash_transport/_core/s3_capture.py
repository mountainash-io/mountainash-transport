"""Permanent per-client botocore hooks for S3: response capture and SigV4 presigning.

boto3's managed transfers (``upload_fileobj``, ``copy``) discard the
``PutObject``/``CopyObject``/``CompleteMultipartUpload`` responses that carry a
write's ETag and VersionId, and send them from s3transfer's worker threads.
Botocore's handler registry is not safe to change while other threads emit
events on the same client, so handlers are installed once, when the client is
created, and each call registers only a collector keyed by ``(bucket, key)``.

Importing this module does not import any SDK.
"""
from __future__ import annotations

import contextlib
import itertools
import threading
import typing as t

_CAPTURED_OPERATIONS = ("PutObject", "CopyObject", "CompleteMultipartUpload")
_INSTALL_LOCK = threading.Lock()
_ATTRIBUTE = "_mountainash_capture"


class ResponseCapture:
    """One permanent ``after-call`` handler per client, feeding per-call collectors."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._collectors: dict[tuple[str, str], dict[int, list[dict[str, t.Any]]]] = {}
        self._tokens = itertools.count()

    def _on_after_call(self, parsed: dict[str, t.Any], context: dict[str, t.Any], **_: t.Any) -> None:
        params = context.get("input_params") or {}
        target = (params.get("Bucket"), params.get("Key"))
        with self._lock:
            for seen in self._collectors.get(target, {}).values():  # type: ignore[arg-type]
                seen.append(parsed)

    @contextlib.contextmanager
    def collect(self, bucket: str, key: str) -> t.Iterator[list[dict[str, t.Any]]]:
        """Collect every captured response for *bucket*/*key* while the block runs.

        Exactly one response means it is this call's: the call's own transfer
        completes inside the block. More than one means another write to the
        same key ran through this client at the same time, and is ambiguous.
        """
        seen: list[dict[str, t.Any]] = []
        target = (bucket, key)
        with self._lock:
            token = next(self._tokens)  # collectors are identified by token, never by their (equal) contents
            self._collectors.setdefault(target, {})[token] = seen
        try:
            yield seen
        finally:
            with self._lock:
                slots = self._collectors[target]
                del slots[token]
                if not slots:
                    del self._collectors[target]


def _presign_sigv4(signature_version: str, **_: t.Any) -> str | None:
    """Replace botocore's SigV2 presign default; leave Express sessions and SigV4a to botocore."""
    if signature_version.startswith(("v4a", "v4-s3express")):
        return None
    if signature_version.endswith("-query"):
        return "s3v4-query"
    return None


def install_client_hooks(client: t.Any) -> ResponseCapture:
    """Install response capture and SigV4 presigning on *client* once; return its capture.

    ``S3Connection`` calls this as soon as it creates a client, before the
    client is shared. Later calls return the installed capture unchanged.
    """
    with _INSTALL_LOCK:
        capture = vars(client).get(_ATTRIBUTE)
        if capture is None:
            capture = ResponseCapture()
            for operation in _CAPTURED_OPERATIONS:
                client.meta.events.register(f"after-call.s3.{operation}", capture._on_after_call)
            client.meta.events.register_first("choose-signer.s3", _presign_sigv4)
            setattr(client, _ATTRIBUTE, capture)
        return t.cast(ResponseCapture, capture)

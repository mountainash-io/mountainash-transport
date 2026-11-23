"""S3PresignMixin — presigned GET/PUT URLs for the S3 family."""
from __future__ import annotations

import typing as t

from mountainash_transport._core.s3_capture import install_client_hooks
from mountainash_transport.storage.protocols import StoragePresignProtocol

from ._helpers import _mapped
from .s3_path import parse_s3_path

# SigV4 query signatures are valid for at most seven days.
_MAX_EXPIRES = 604_800
# botocore drops exactly this value from the signed headers, so a URL could not enforce it.
_UNSIGNABLE_CONTENT_TYPE = "application/x-www-form-urlencoded; charset=utf-8"


class S3PresignMixin(StoragePresignProtocol):
    """Presign mixin for the S3 family.

    Signs with SigV4 against the client's own endpoint, so R2, MinIO, B2 and
    Express URLs point at their own hosts. Signing is local except on S3
    Express, which signs with a session from ``CreateSession`` (possibly a
    request; needs ``s3express:CreateSession``) and so limits the URL to the
    session's lifetime.
    """

    def presign(
        self, path: str, *, method: t.Literal["GET", "PUT"] = "GET",
        expires_in: int = 3600, content_type: str | None = None,
    ) -> str:
        if method not in ("GET", "PUT"):
            raise ValueError(f"presign method must be 'GET' or 'PUT', got {method!r}")
        if not 1 <= expires_in <= _MAX_EXPIRES:
            raise ValueError(f"expires_in must be between 1 and {_MAX_EXPIRES} seconds, got {expires_in}")
        if content_type is not None and method != "PUT":
            raise ValueError("content_type applies only to method='PUT'")
        if content_type == _UNSIGNABLE_CONTENT_TYPE:
            raise ValueError(f"content_type {content_type!r} cannot be enforced by a presigned URL")
        bucket, key = parse_s3_path(path)
        params: dict[str, str] = {"Bucket": bucket, "Key": key}
        if content_type is not None:  # "" is a value to sign, not "unset"
            params["ContentType"] = content_type
        install_client_hooks(self._client)  # type: ignore[attr-defined]  # SigV4 even where botocore would pick SigV2
        with _mapped(path):
            return t.cast(str, self._client.generate_presigned_url(  # type: ignore[attr-defined]
                "get_object" if method == "GET" else "put_object", Params=params, ExpiresIn=expires_in,
            ))

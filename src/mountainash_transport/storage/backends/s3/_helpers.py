"""Structured S3 error translation shared by the S3 operation mixins."""
from __future__ import annotations

import contextlib
import io
import typing as t

from mountainash_transport._core.exceptions import (
    AuthenticationError, ObjectChangedError, PathNotFoundError,
    PermissionDeniedError, StorageConnectionError, StorageError,
)
from mountainash_transport._core.safe_display import raise_safe, safe_detail, safe_location


def _map_error(exc: Exception, path: str) -> StorageError | None:
    if isinstance(exc, (StorageError, io.UnsupportedOperation)):
        return None
    from botocore import exceptions as errors

    shown = safe_location(path)

    if isinstance(exc, (
        errors.ParamValidationError, errors.ValidationError, errors.BaseEndpointResolverError,
        errors.EndpointResolutionError, errors.InvalidHostLabelError, errors.InvalidDNSNameError,
        errors.UnsupportedS3ConfigurationError, errors.UnsupportedS3AccesspointConfigurationError,
        errors.UnsupportedS3ArnError, errors.UnsupportedOutpostResourceError,
        errors.UnknownSignatureVersionError, errors.UnsupportedSignatureVersionError,
        errors.UnseekableStreamError,
    )):
        return None
    if isinstance(exc, errors.ClientError):
        response = exc.response
        code = response.get("Error", {}).get("Code")
        status = response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if code in ("InvalidAccessKeyId", "SignatureDoesNotMatch", "ExpiredToken",
                    "ExpiredTokenException", "InvalidToken", "TokenRefreshRequired",
                    "InvalidClientTokenId", "UnrecognizedClientException"):
            return AuthenticationError(shown)
        if code in ("NoSuchKey", "NoSuchBucket", "NotFound", "404"):
            return PathNotFoundError(shown)
        if code == "AccessDenied":
            return PermissionDeniedError(shown)
        if code in ("RequestTimeout", "RequestTimeoutException"):
            return StorageConnectionError(shown)
        if code == "PreconditionFailed" or status == 412:
            return ObjectChangedError(shown)
        if status == 401:
            return AuthenticationError(shown)
        if status == 403:
            return PermissionDeniedError(shown)
        if status == 404:
            return PathNotFoundError(shown)
        return StorageError(f"{shown}: storage error ({safe_detail(exc)})")
    if isinstance(exc, (errors.NoCredentialsError, errors.PartialCredentialsError,
                        errors.CredentialRetrievalError)):
        return AuthenticationError(shown)
    if isinstance(exc, (ConnectionError, TimeoutError, EOFError,
                        errors.ConnectionError, errors.HTTPClientError,
                        errors.IncompleteReadError)):
        return StorageConnectionError(f"{shown}: connection failed ({safe_detail(exc)})")
    if isinstance(exc, (OSError, errors.BotoCoreError)):
        return StorageError(f"{shown}: storage error ({safe_detail(exc)})")
    return None


@contextlib.contextmanager
def _mapped(path: str) -> t.Iterator[None]:
    try:
        yield
    except Exception as exc:
        mapped = _map_error(exc, path)
        if mapped is None or mapped is exc:
            raise
        raise_safe(mapped, exc)

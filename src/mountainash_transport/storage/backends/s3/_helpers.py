"""Structured S3 error translation shared by the S3 operation mixins."""
from __future__ import annotations

import contextlib
import io
import typing as t

from mountainash_transport._core.exceptions import (
    AuthenticationError, ObjectChangedError, PathNotFoundError,
    PermissionDeniedError, StorageConnectionError, StorageError,
)


def _map_error(exc: Exception, path: str) -> StorageError | None:
    if isinstance(exc, (StorageError, io.UnsupportedOperation)):
        return None
    from botocore import exceptions as errors

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
            return AuthenticationError(path)
        if code in ("NoSuchKey", "NoSuchBucket", "NotFound", "404"):
            return PathNotFoundError(path)
        if code == "AccessDenied":
            return PermissionDeniedError(path)
        if code in ("RequestTimeout", "RequestTimeoutException"):
            return StorageConnectionError(path)
        if code == "PreconditionFailed" or status == 412:
            return ObjectChangedError(path)
        if status == 401:
            return AuthenticationError(path)
        if status == 403:
            return PermissionDeniedError(path)
        if status == 404:
            return PathNotFoundError(path)
        return StorageError(f"{path}: {exc}")
    if isinstance(exc, (errors.NoCredentialsError, errors.PartialCredentialsError,
                        errors.CredentialRetrievalError)):
        return AuthenticationError(path)
    if isinstance(exc, (ConnectionError, TimeoutError, EOFError,
                        errors.ConnectionError, errors.HTTPClientError,
                        errors.IncompleteReadError)):
        return StorageConnectionError(f"{path}: {exc}")
    if isinstance(exc, (OSError, errors.BotoCoreError)):
        return StorageError(f"{path}: {exc}")
    return None


@contextlib.contextmanager
def _mapped(path: str) -> t.Iterator[None]:
    try:
        yield
    except Exception as exc:
        mapped = _map_error(exc, path)
        if mapped is None or mapped is exc:
            raise
        raise mapped from exc

"""Settings adapters — per-SDK kwargs builders.

Each module in this package exposes a ``build_handler_kwargs(profile)``
function that takes a :class:`StorageProfile` and returns a dict of kwargs
ready for the relevant SDK client constructor (boto3, google.cloud.storage,
azure-blob, paramiko, ftplib, smbprotocol, fsspec-github, etc.).

Adapters are wired to providers via ``__adapter__`` on the provider
settings class; see
:mod:`mountainash_utils_files.settings.providers.s3_settings` for the
canonical pattern.
"""

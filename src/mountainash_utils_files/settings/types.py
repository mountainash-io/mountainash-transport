from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar, Union, Protocol, Any
from typing_extensions import TypeAlias, TypeGuard

from dataclasses import dataclass

from .profiles import ( AzureStorageProfile,
FTPStorageProfile,
GCSStorageProfile,
GitHubRepoStorageProfile,
HTTPStorageProfile,
LocalStorageProfile,
S3StorageProfile,
SMBStorageProfile,
SSHStorageProfile)

if TYPE_CHECKING:

    # ========================================================================
    # Composite Type Unions
    # ========================================================================

    SupportedStorageProfiles: TypeAlias = Union[
        AzureStorageProfile,
        FTPStorageProfile,
        GCSStorageProfile,
        GitHubRepoStorageProfile,
        HTTPStorageProfile,
        LocalStorageProfile,
        S3StorageProfile,
        SMBStorageProfile,
        SSHStorageProfile,
    ]

# ============================================================================
# Generic Type Variables
# ============================================================================

StorageProfileT = TypeVar("StorageProfileT", bound="SupportedStorageProfiles")

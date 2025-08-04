# mountainash-utils-files Package Overview

## Purpose
Provides unified file operations across multiple storage systems including local filesystem, S3, SFTP, R2, GCS, and Azure Blob Storage with consistent interface for file operations, path manipulation, and data synchronization.

## Architecture
The package follows a factory pattern with abstract base classes and storage-specific implementations. Core components include FileInterface (main API), FileHelperFactory (creates storage helpers), PathHelper (path utilities), and specialized file readers/writers with sync orchestration.

## Directory + File Structure
```
src/mountainash_utils_files/
├── __init__.py                          # Main package exports
├── __version__.py                       # Version information
├── dataclasses/                         # Data structures
│   ├── __init__.py
│   └── file_metadata.py                 # File metadata structures
├── file_helpers/                        # Storage system implementations
│   ├── __init__.py
│   ├── base_file_helper.py              # Abstract base class
│   ├── file_helper_factory.py           # Factory for creating helpers
│   ├── local_file_helper.py             # Local filesystem operations
│   ├── s3_file_helper.py                # AWS S3 operations
│   ├── s3_file_helper_backup.py         # S3 backup implementation
│   ├── s3express_file_helper.py         # S3 Express operations
│   ├── s3u_file_helper.py               # S3 unified operations
│   ├── r2_file_helper.py                # Cloudflare R2 operations
│   ├── gcs_file_helper.py               # Google Cloud Storage
│   ├── az_file_helper.py                # Azure Blob Storage
│   ├── sftp_file_helper.py              # SFTP operations
│   └── ssh_file_helper.py               # SSH operations
├── file_interface/                      # Main API interface
│   ├── __init__.py
│   └── file_interface.py                # Unified file operations API
├── file_readers/                        # File reading utilities
│   └── filereader.py                    # Generic file reader
├── file_writers/                        # File writing utilities
│   └── filewriter.py                    # Generic file writer
├── file_sync/                           # File synchronization
│   ├── __init__.py
│   ├── file_sync.py                     # Core sync functionality
│   ├── file_sync_orchestrator.py       # Orchestration logic
│   └── file_syncer_tools.py            # Sync utilities
└── path_helpers/                        # Path manipulation utilities
    ├── __init__.py
    ├── path_helper.py                   # Main path utilities
    ├── base_path_helper.py              # Base path operations
    ├── local_path_helper.py             # Local path operations
    ├── s3_path_helper.py                # S3 path operations
    ├── gcs_path_helper.py               # GCS path operations
    ├── az_path_helper.py                # Azure path operations
    ├── sftp_path_helper.py              # SFTP path operations
    └── ssh_path_helper.py               # SSH path operations
```

## Key Components

### mountainash_utils_files
**Main Exports**: FileInterface, FileReader, FileWriter, PathHelper, get_file_interface

**FileInterface** - Primary API class providing unified operations (exists, copy, list, size) across all storage systems with automatic helper resolution based on path or auth parameters.

**PathHelper** - Utility class for path formatting and storage system identification, supporting local, S3, GCS, Azure, SFTP, and SSH paths with automatic format detection.

**FileReader/FileWriter** - Specialized classes for reading and writing different file formats with built-in compression and encryption support.

**FileHelperFactory** - Factory pattern implementation creating appropriate storage-specific helpers (LocalFileHelper, S3FileHelper, GCSFileHelper, etc.) based on storage system type.

**Base_FileHelper** - Abstract base class defining interface for all storage implementations with common functionality for compression, encryption, and connection management.

**File Sync Components** - Orchestration tools (file_sync.py, file_sync_orchestrator.py, file_syncer_tools.py) for synchronizing files between different storage systems.

**Storage Implementations**:
- LocalFileHelper - Native filesystem operations
- S3FileHelper/S3ExpressFileHelper - AWS S3 standard and Express
- R2FileHelper - Cloudflare R2 optimizations
- GCSFileHelper - Google Cloud Storage native operations
- AZFileHelper - Azure Blob Storage implementation
- SFTPFileHelper/SSHFileHelper - Secure transfer protocols

## Usage Patterns
**Cross-platform file operations** - Single API for file exists, copy, list operations regardless of storage backend
**Path-to-path copying** - Direct transfers between different storage systems (e.g., S3 to local, GCS to SFTP)
**Stream-based processing** - Efficient handling of large files with compression and encryption
**Authentication integration** - Works with mountainash-settings for secure credential management
**Metadata handling** - Rich file metadata support across storage systems

## Dependencies
Runtime: 12 packages

### Local Dependencies
- mountainash-settings - Configuration and authentication management
- mountainash-constants - Shared constants and enumerations
- mountainash-utils-gpg - GPG encryption utilities
- mountainash-utils-ssh - SSH connection utilities

### External Dependencies
**Core Dependencies** (12 packages):
- pandas>=2.2.0 - Data manipulation and analysis
- polars==1.16.0 - Fast DataFrame library for data processing
- pydantic==2.9.2 - Data validation and settings management
- pydantic-settings==2.6.1 - Settings management with Pydantic
- universal_pathlib==0.2.2 - Universal path library for different storage systems
- pyarrow==17.0.0 - Apache Arrow columnar data format
- boltons==24.0.0 - Collection of over 230 BSD-licensed utilities
- minio==7.2.7 - High-performance object storage SDK
- boto3==1.34.136 - AWS SDK for Python
- smart-open[all]==7.0.4 - Utils for streaming large files
- lxml>=4.5.0 - XML and HTML processing library
- xsdata[lxml]>=24.4 - XML data binding library

**Optional Dependencies**:
- S3: boto3, s3fs, minio
- GCS: google-cloud-storage, gcsfs
- Azure: azure-storage-blob, adlfs
- SFTP: paramiko, smart-open[ssh]
- Encryption: gnupg, python-gnupg

## Integration
Integrates with mountainash ecosystem through shared authentication (mountainash-settings), constants (mountainash-constants), and utility packages for GPG encryption and SSH connections. Provides unified storage abstraction for other mountainash packages requiring file operations across multiple backends.
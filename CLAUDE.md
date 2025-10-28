# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**mountainash-utils-files** is a Python package for unified file operations across multiple storage systems including local filesystem, S3, SFTP, R2, GCS, and Azure Blob Storage. It provides a consistent interface for file operations, path manipulation, and data synchronization across different storage backends.

## Architecture

### Core Components

- **FileInterface**: Main API class providing unified file operations across storage systems
- **FileHelperFactory**: Factory pattern for creating storage-specific file helpers
- **Base_FileHelper**: Abstract base class for all storage implementations
- **PathHelper**: Utility class for path formatting and storage system identification
- **File Readers/Writers**: Specialized classes for reading and writing different file formats
- **File Sync**: Orchestration tools for synchronizing files between storage systems

### Package Structure

```
src/mountainash_utils_files/
├── __init__.py                 # Main package exports
├── __version__.py              # Version information
├── dataclasses/                # Data structures
│   ├── __init__.py
│   └── file_metadata.py        # File metadata structures
├── file_helpers/               # Storage system implementations
│   ├── __init__.py
│   ├── base_file_helper.py     # Abstract base class
│   ├── file_helper_factory.py  # Factory for creating helpers
│   ├── local_file_helper.py    # Local filesystem operations
│   ├── s3_file_helper.py       # AWS S3 operations
│   ├── r2_file_helper.py       # Cloudflare R2 operations
│   ├── sftp_file_helper.py     # SFTP operations
│   ├── ssh_file_helper.py      # SSH operations
│   ├── gcs_file_helper.py      # Google Cloud Storage
│   ├── az_file_helper.py       # Azure Blob Storage
│   └── s3express_file_helper.py # S3 Express operations
├── file_interface/             # Main API interface
│   ├── __init__.py
│   └── file_interface.py       # Unified file operations API
├── file_readers/               # File reading utilities
│   └── filereader.py           # Generic file reader
├── file_writers/               # File writing utilities
│   └── filewriter.py           # Generic file writer
├── file_sync/                  # File synchronization
│   ├── __init__.py
│   ├── file_sync.py            # Core sync functionality
│   ├── file_sync_orchestrator.py # Orchestration logic
│   └── file_syncer_tools.py    # Sync utilities
└── path_helpers/               # Path manipulation utilities
    ├── __init__.py
    ├── path_helper.py          # Main path utilities
    ├── base_path_helper.py     # Base path operations
    ├── local_path_helper.py    # Local path operations
    ├── s3_path_helper.py       # S3 path operations
    ├── sftp_path_helper.py     # SFTP path operations
    ├── ssh_path_helper.py      # SSH path operations
    ├── gcs_path_helper.py      # GCS path operations
    └── az_path_helper.py       # Azure path operations
```

### Test Structure

```
tests/
├── test_data_storage.py        # FileInterface functionality tests
└── test_path_utils.py          # PathHelper functionality tests
```


## Build/Test/Lint Commands
- Build: `hatch build`
- Lint: `hatch run ruff:check` or `hatch run ruff:fix` to auto-fix
- Tests: `hatch run test:test` or `hatch run test:cov` for coverage
- Single test: `pytest tests/path/to/test_file.py::TestClass::test_function -v`
- Type check: `hatch run mypy:check`

## Dependencies

### Core Dependencies
- **pandas>=2.2.0**: Data manipulation and analysis
- **polars==1.16.0**: Fast DataFrame library for data processing
- **pydantic==2.9.2**: Data validation and settings management
- **pydantic-settings==2.6.1**: Settings management with Pydantic
- **universal_pathlib==0.2.2**: Universal path library for different storage systems
- **pyarrow==17.0.0**: Apache Arrow columnar data format
- **boltons==24.0.0**: Collection of over 230 BSD-licensed utilities
- **minio==7.2.7**: High-performance object storage SDK
- **boto3==1.34.136**: AWS SDK for Python
- **smart-open[all]==7.0.4**: Utils for streaming large files
- **lxml>=4.5.0**: XML and HTML processing library
- **xsdata[lxml]>=24.4**: XML data binding library

### Optional Dependencies
- **S3**: boto3, s3fs, minio
- **GCS**: google-cloud-storage, gcsfs
- **Azure**: azure-storage-blob, adlfs
- **SFTP**: paramiko, smart-open[ssh]
- **Encryption**: gnupg, python-gnupg

### Internal Mountain Ash Dependencies
- **mountainash-settings**: Configuration and authentication management
- **mountainash-constants**: Shared constants and enumerations
- **mountainash-utils-gpg**: GPG encryption utilities
- **mountainash-utils-ssh**: SSH connection utilities

### Development Dependencies
- pytest==8.3.5
- pytest-check, pytest-cov, pytest-mock
- ruff==0.3.7
- mypy==1.10.1
- radon==6.0.1

## GitHub Actions Workflows

### Testing
- **python-run-pytest.yml**: Runs unit tests on pull requests, supports Python 3.12
- **python-run-ruff.yml**: Code linting and formatting checks
- **python-run-radon.yml**: Complexity analysis and code quality metrics
- **main-release-branch-validation.yml**: Validates release branch requirements

### Release Process
- **build-and-release-package.yml**: Automated release workflow
- **main-release-build-dependencies.yml**: Builds and validates dependencies
- Supports production, RC, and beta releases
- Generates SBOMs (Software Bill of Materials)
- Creates releases in GitHub and mountainash-wheels repository

### Branch Strategy
- `main`: Production releases (only release/* and hotfix/* branches)
- `develop`: Development and RC releases
- `feature/*`, `bugfix/*`, `hotfix/*`: Feature branches
- Protected branches require code owner approval (@discreteds)

## Code Style Guidelines
- Formatting: Uses ruff for formatting and linting
- Imports: Standard lib first, third-party next, project imports last
- Types: Use typing annotations (e.g., `import typing as t`) for all functions
- Naming: CamelCase for classes, snake_case for functions/variables, UPPER_CASE for constants
- Error handling: Use ValueError for validation errors, custom exceptions for specific cases
- Documentation: Use Google-style docstrings for classes and methods
- Organization: Follow modular design with clear separation of concerns
- Testing: Create unit tests with appropriate markers (unit, integration, performance)

## Development Environments

### Hatch Environments
- `default`: Local development
- `test`: Local testing with extended pytest plugins
- `test_github`: GitHub Actions testing
- `build_github`: GitHub Actions building
- `ruff`: Linting and formatting
- `radon`: Complexity analysis
- `mypy`: Type checking

## Key Features

### Unified File Operations
- **Cross-platform compatibility**: Works with local, cloud, and remote storage
- **Consistent API**: Same interface regardless of storage backend
- **Stream-based operations**: Efficient handling of large files
- **Path-to-path copying**: Direct transfers between different storage systems
- **Compression and encryption**: Built-in support for gzip compression and GPG encryption

### Storage System Support
- **Local filesystem**: Native file operations
- **AWS S3**: Standard and S3 Express support
- **Cloudflare R2**: R2-specific optimizations
- **Google Cloud Storage**: Native GCS operations
- **Azure Blob Storage**: Azure-specific implementations
- **SFTP/SSH**: Secure file transfer protocols

### Advanced Capabilities
- **File synchronization**: Orchestrated sync between storage systems
- **Metadata handling**: Rich file metadata support
- **Connection management**: Automatic connection pooling and management
- **Error handling**: Comprehensive error handling and retries
- **Authentication**: Integration with mountainash-settings for secure auth

## Usage Examples

### Basic File Operations
```python
from mountainash_utils_files import FileInterface, get_file_interface
from mountainash_settings import SettingsParameters
from mountainash_settings.settings.auth.storage.providers import LocalStorageAuthSettings

# Create auth parameters
auth_params = SettingsParameters.create("local", LocalStorageAuthSettings)

# Check if file exists
exists = FileInterface.path_exists("/path/to/file.txt", auth_params)

# Get file size
size = FileInterface.get_size("/path/to/file.txt", auth_params)

# List directory contents
files = FileInterface.list_sources("/path/to/directory/", auth_params)
```

### Cross-Storage File Copy
```python
# Copy from S3 to local
FileInterface.copy_path_to_path(
    source_path="s3://bucket/file.txt",
    destination_path="/local/path/file.txt",
    source_auth_settings_parameters=s3_auth_params,
    destination_auth_settings_parameters=local_auth_params
)
```

## Versioning Strategy

Uses CalVer (Calendar Versioning) with semantic versioning:
- Format: `YYYY.MM.MICRO`
- Release candidate: `YYYY.MM.0`
- Production: `YYYY.MM.1`
- Patches: `YYYY.MM.X`

## License
MIT License

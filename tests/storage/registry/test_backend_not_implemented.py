# tests/storage/registry/test_backend_not_implemented.py

import pytest
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.exceptions import BackendNotImplementedError
from mountainash_transport.storage.registry import get_storage_backend
import mountainash_transport.storage.backends  # trigger registrations


class TestBackendNotImplementedError:
    def test_profiled_unimplemented_raises(self):
        """GCS has a profile but no backend — should raise BackendNotImplementedError."""
        with pytest.raises(BackendNotImplementedError, match="not yet implemented"):
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS, None)

    def test_enum_only_unimplemented_raises(self):
        """SSH has an enum value but no profile and no backend — should raise BackendNotImplementedError."""
        with pytest.raises(BackendNotImplementedError):
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SSH, None)

    def test_implemented_provider_works(self):
        """LOCAL has a backend — should return an instance."""
        backend = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.LOCAL, None)
        assert backend is not None

    def test_sftp_provider_works(self):
        """SFTP has a backend — should return SFTPStorageBackend."""
        backend = get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.SFTP, None)
        assert type(backend).__name__ == "SFTPStorageBackend"

    def test_error_message_lists_implemented_providers(self):
        """The error message should list implemented providers."""
        with pytest.raises(BackendNotImplementedError) as exc_info:
            get_storage_backend(CONST_STORAGE_PROVIDER_TYPE.GCS, None)
        msg = str(exc_info.value)
        assert "local" in msg.lower() or "LOCAL" in msg

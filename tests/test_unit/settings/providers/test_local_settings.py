"""Tests for LocalSettings — local filesystem + NFS/CIFS fold-in."""

from __future__ import annotations

import pytest

from mountainash_settings.auth import NoAuth

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.providers.local_settings import (
    LOCAL_DESCRIPTOR,
    LocalSettings,
)
from mountainash_utils_files.settings.providers import NFSStorageAuthSettings


def _make(**extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.LOCAL,
        "auth": NoAuth(),
    }
    kwargs.update(extra)
    return LocalSettings(**kwargs)


@pytest.mark.unit
class TestLocalBasic:
    def test_construct_with_just_root_path(self):
        s = _make(ROOT_PATH="/tmp/files")
        assert s.ROOT_PATH == "/tmp/files"

    def test_no_root_path_allowed(self):
        s = _make()
        assert s.ROOT_PATH is None

    def test_to_handler_kwargs_shape(self):
        s = _make(ROOT_PATH="/tmp/files")
        kw = s.to_handler_kwargs()
        assert kw == {"root_path": "/tmp/files", "create_path": False}

    def test_create_path_flag_surfaced(self):
        s = _make(ROOT_PATH="/tmp/new", CREATE_PATH=True)
        kw = s.to_handler_kwargs()
        assert kw["create_path"] is True


@pytest.mark.unit
class TestLocalMountSpecNone:
    def test_no_mount_spec_means_no_mount_kwargs(self):
        s = _make(ROOT_PATH="/tmp/files")
        kw = s.to_handler_kwargs()
        assert "mount_spec" not in kw

    def test_mount_spec_none_mount_type_also_omitted(self):
        s = _make(
            ROOT_PATH="/tmp",
            MOUNT_SPEC={"mount_type": "none"},
        )
        kw = s.to_handler_kwargs()
        # 'none' is not a real mount type — should not surface in kwargs.
        assert "mount_spec" not in kw


@pytest.mark.unit
class TestLocalMountSpecNFS:
    def test_nfs_mount_spec_surfaces_in_handler_kwargs(self):
        spec = {
            "mount_type": "nfs",
            "server": "nfs.example",
            "export_path": "/srv/shared",
            "options": {"vers": "4.2", "sec": "sys"},
        }
        s = _make(ROOT_PATH="/mnt/share", MOUNT_SPEC=spec)
        kw = s.to_handler_kwargs()
        assert kw["mount_spec"] == spec


@pytest.mark.unit
class TestLocalMountSpecCIFS:
    def test_cifs_mount_spec_surfaces_in_handler_kwargs(self):
        spec = {
            "mount_type": "cifs",
            "server": "file.corp",
            "export_path": "/shared",
            "options": {"vers": "3.0"},
        }
        s = _make(ROOT_PATH="/mnt/cifs", MOUNT_SPEC=spec)
        kw = s.to_handler_kwargs()
        assert kw["mount_spec"] == spec


@pytest.mark.unit
class TestNFSAliasBackcompat:
    def test_nfs_alias_is_local_settings(self):
        assert NFSStorageAuthSettings is LocalSettings

    def test_nfs_alias_instance_works_with_mount_spec(self):
        spec = {
            "mount_type": "nfs",
            "server": "nfs.example",
            "export_path": "/srv/shared",
        }
        s = NFSStorageAuthSettings(
            PROVIDER_TYPE=CONST_STORAGE_PROVIDER_TYPE.LOCAL,
            ROOT_PATH="/mnt/share",
            MOUNT_SPEC=spec,
            auth=NoAuth(),
        )
        assert isinstance(s, LocalSettings)
        kw = s.to_handler_kwargs()
        assert kw["mount_spec"] == spec


@pytest.mark.unit
class TestLocalDescriptor:
    def test_descriptor_name(self):
        assert LOCAL_DESCRIPTOR.name == "local"

    def test_descriptor_sdk_package_is_none(self):
        """Stdlib only — no SDK."""
        assert LOCAL_DESCRIPTOR.sdk_package is None

    def test_descriptor_not_read_only(self):
        assert LOCAL_DESCRIPTOR.read_only is False

    def test_descriptor_no_multipart(self):
        assert LOCAL_DESCRIPTOR.supports_multipart is False

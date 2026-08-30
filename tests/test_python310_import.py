from __future__ import annotations

import mountainash_transport
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._core.dataclasses.storage_entry import EntryType


def test_base_package_and_enum_import_on_python310() -> None:
    assert mountainash_transport is not None
    assert CONST_STORAGE_PROVIDER_TYPE.LOCAL == "local"
    assert EntryType.FILE == "file"

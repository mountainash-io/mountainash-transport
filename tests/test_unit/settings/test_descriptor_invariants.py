"""Parametric descriptor invariants for all registered storage providers.

Generated from the shared ``descriptor_invariants_for`` helper in
``mountainash-settings``. Every descriptor in ``STORAGE_REGISTRY`` gets
checked against the invariants for free — no per-provider test additions
required.

No extra handler-module-importability test is included here: storage
backends beyond ``local`` and ``s3`` are not yet migrated to the
descriptor-targeted module paths (``storage_backends.{azure,ftp,gcs,
github,smb,ssh}``); enforcing importability at this stage of Phase 4
would force premature backend work. The handler_module / handler_class
pointers are stored declaratively on each descriptor and will be
exercised by whichever phase fully wires each backend.
"""

from __future__ import annotations

# Trigger provider registration so STORAGE_REGISTRY is populated.
import mountainash_utils_files.settings.providers  # noqa: F401

from mountainash_settings.profiles import descriptor_invariants_for
from mountainash_utils_files.settings.registry import STORAGE_REGISTRY


# Instantiating this at module import time generates one parametric test
# class per invariant — pytest picks them up via the module-level name.
TestStorageInvariants = descriptor_invariants_for(STORAGE_REGISTRY)

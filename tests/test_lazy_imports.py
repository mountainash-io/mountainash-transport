"""Packaging invariant: importing the package must not import heavy SDKs."""
import subprocess
import sys


def test_top_level_import_stays_light():
    code = (
        "import sys; import mountainash_transport; "
        "heavy = {'boto3', 'botocore', 'paramiko', 'gnupg', 's3fs', 'minio'} "
        "& set(sys.modules); "
        "assert not heavy, f'heavy imports at top level: {heavy}'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def _run(code):
    subprocess.run([sys.executable, "-c", code], check=True)


def test_location_module_import_is_stdlib_only():
    _run("import sys; before=set(sys.modules); import mountainash_transport.location; "
         "new={m.split('.')[0] for m in set(sys.modules)-before}; "
         "bad=new-set(sys.stdlib_module_names)-{'mountainash_transport'}; assert not bad, bad")


def test_backends_register_on_first_lookup_after_lazy_import():
    _run("from mountainash_transport.storage.facade.facade import StorageFacade; "
         "StorageFacade.for_local()")


def test_storage_factory_survives_submodule_import_order():
    _run("from mountainash_transport import StorageFacade; import mountainash_transport.storage.facade; "
         "from mountainash_transport import storage; f = storage(); assert f.__class__.__name__ == 'StorageFacade'")


def test_lazy_exports_are_real_objects():
    _run("import mountainash_transport as t; from mountainash_transport.storage.protocols import StorageReadProtocol; "
         "assert t.StorageReadProtocol is StorageReadProtocol; assert isinstance(t.StorageFacade.for_local(), t.StorageFacade)")

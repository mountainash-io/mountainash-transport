"""Base-install contract: no module outside the base install is imported on the local path.

The blocker is derived from the base install (stdlib + typing_extensions +
mountainash_transport), so a future backend that imports its SDK at module
level fails here without a hand-maintained list.
"""
import subprocess
import sys
import textwrap

BLOCKER = textwrap.dedent('''
    import importlib.abc, sys
    ALLOWED = set(sys.stdlib_module_names) | {"typing_extensions", "mountainash_transport"}
    class _BaseInstallOnly(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            top = name.partition(".")[0]
            if top not in ALLOWED and top not in sys.modules:
                raise ModuleNotFoundError(f"No module named {top!r}", name=top)
            return None
    sys.meta_path.insert(0, _BaseInstallOnly())
    try:
        import httpx  # positive control
    except ModuleNotFoundError:
        pass
    else:
        raise AssertionError("blocker inactive")
''')


def _run_base(code: str) -> None:
    subprocess.run([sys.executable, "-c", BLOCKER + textwrap.dedent(code)], check=True)


def test_local_facade_round_trip_on_base_install(tmp_path):
    _run_base(f'''
        import os
        import mountainash_transport.location
        from mountainash_transport import Gzip, StorageFacade, infer_pipeline, resolve_native_read
        from mountainash_transport.location import LocationPolicy, LocationNotAllowed
        root = {str(tmp_path)!r}
        pipe, stripped = infer_pipeline("a.csv.gz")
        assert stripped == "a.csv" and pipe is not None and not pipe.is_empty()
        f = StorageFacade.from_path(root)
        p = os.path.join(root, "a.txt")
        f.write(p, b"hello")
        assert f.read(p) == b"hello"
        access = resolve_native_read(p)
        assert f.read(access.location) == b"hello"
        access = resolve_native_read(p, policy=LocationPolicy(root=root))
        assert f.read(access.location) == b"hello"
        try:
            resolve_native_read(os.path.join(root, "..", "outside"), policy=LocationPolicy(root=root))
        except LocationNotAllowed:
            pass
        else:
            raise AssertionError("handoff bypassed explicit confinement")
        s = f.read_stream(p, access="random"); s.seek(1); assert s.read() == b"ello"; s.close()
        g = os.path.join(root, "b.txt.gz")
        f.write(g, b"zip", pipeline=Gzip())
        assert f.read(g, infer=True) == b"zip"
        assert sorted(e.name for e in f.list_dir(root)) == ["a.txt", "b.txt.gz"]
        assert f.get_size(p) == 5
        f.close()
    ''')


def test_every_backend_imports_on_base_install():
    _run_base('''
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as C
        from mountainash_transport.storage.registry import get_registered_backends
        from mountainash_transport.storage.registry.registry import ensure_backends_loaded
        ensure_backends_loaded()
        assert {C.LOCAL, C.S3, C.HTTP, C.SFTP} <= set(get_registered_backends())
    ''')


def test_unimplemented_provider_keeps_typed_refusal_on_base_install():
    _run_base('''
        from mountainash_transport import BackendNotImplementedError, StorageFacade
        for url in ("gs://b/k", "ftp://h/k", "smb://h/k", "ssh://h/k"):
            try:
                StorageFacade.from_path(url)
            except BackendNotImplementedError:
                continue
            raise AssertionError(url)
    ''')


def test_caller_registration_wins_on_base_install():
    _run_base('''
        from mountainash_transport.storage.registry.registry import register_storage_backend, get_storage_backend
        from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as C
        @register_storage_backend(C.LOCAL)
        class Custom:
            def __init__(self, profile, connection=None): pass
        assert type(get_storage_backend(C.LOCAL, None)) is Custom
    ''')


def test_remote_surfaces_name_the_http_extra_on_base_install():
    _run_base('''
        from mountainash_transport import MissingExtraError, StorageFacade

        def expect(fn):
            try:
                fn()
            except MissingExtraError as err:
                assert err.extra == "http", err
                assert "pip install 'mountainash-transport[http]'" in str(err), err
                return
            raise AssertionError("no MissingExtraError")

        expect(lambda: StorageFacade.from_path("https://example.com/a.csv"))
        expect(lambda: StorageFacade.from_path("s3://bucket/key").read("s3://bucket/key"))
        expect(lambda: __import__("mountainash_transport.settings.storage.profiles", fromlist=["S3StorageProfile"]))
        expect(lambda: __import__("mountainash_transport.connections", fromlist=["create_connection"]))
        import mountainash_transport as root
        for name in ("StoragePath", "HttpRequestEngine", "resolve_storage", "create_connection"):
            expect(lambda name=name: getattr(root, name))
        from mountainash_transport import HttpNotFoundError, RetryPolicy  # stdlib-only HTTP names stay importable
    ''')

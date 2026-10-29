# test_facade_remote_policy.py
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import pytest
from mountainash_transport import StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_auth_client import NoAuthProfile
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE

_S3_MINIMAL = {
    "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.S3,
    "FLAVOR": "aws",
    "REGION": "us-east-1",
    "auth": NoAuthProfile(),
}
_SFTP_MINIMAL = {
    "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.SFTP,
    "USERNAME": "alice",
}


@pytest.fixture
def servers(tmp_path):
    (tmp_path / "s.csv").write_bytes(b"v\n1\n")
    target = ThreadingHTTPServer(("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=str(tmp_path)))
    hits = {"target": 0}
    class H(SimpleHTTPRequestHandler):
        def do_GET(self):
            hits["target"] += 1; super().do_GET()
    target.RequestHandlerClass = partial(H, directory=str(tmp_path))
    tport = target.server_address[1]
    class R(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302); self.send_header("Location", f"http://127.0.0.1:{tport}/s.csv"); self.end_headers()
        def log_message(self, *a): pass
    redirector = ThreadingHTTPServer(("localhost", 0), R)
    for s in (target, redirector): threading.Thread(target=s.serve_forever, daemon=True).start()
    yield tport, redirector.server_address[1], hits
    target.shutdown(); redirector.shutdown()

def test_http_rejected_without_allow_list(servers):
    tport, _, hits = servers
    url = f"http://127.0.0.1:{tport}/s.csv"
    with pytest.raises(LocationNotAllowed): StorageFacade.from_path(url, policy=LocationPolicy()).read(url)
    assert hits["target"] == 0

def test_http_allowed_by_allow_list(servers):
    tport, _, _ = servers
    url = f"http://127.0.0.1:{tport}/s.csv"
    pol = LocationPolicy(allowed_remote={"http": frozenset({"127.0.0.1"})})
    assert StorageFacade.from_path(url, policy=pol).read(url) == b"v\n1\n"

def test_redirect_to_disallowed_host_rejected_before_second_send(servers):
    _, rport, hits = servers
    url = f"http://localhost:{rport}/x"
    pol = LocationPolicy(allowed_remote={"http": frozenset({"localhost"})})
    with pytest.raises(LocationNotAllowed): StorageFacade.from_path(url, policy=pol).read(url)
    assert hits["target"] == 0

def test_http_no_policy_is_today(servers):
    tport, _, _ = servers
    url = f"http://127.0.0.1:{tport}/s.csv"
    assert StorageFacade.from_path(url).read(url) == b"v\n1\n"

@pytest.fixture
def fake_backend(monkeypatch):
    """Record backend calls; no SDK or network. Patches the two seams the facade constructor uses."""
    import io
    from mountainash_transport.storage.facade import facade as facade_mod
    calls = []
    class Conn:
        def connect(self): pass
        def close(self): pass
    class Backend:
        storage_profile = None
        def read_to_bytes(self, path): calls.append(("read", path)); return b"x"
        def read_to_stream(self, path): calls.append(("read", path)); return io.BytesIO(b"x")
        def write_from_bytes(self, path, data, create_parents=True): calls.append(("write", path))
        def write_from_stream(self, path, stream, create_parents=True): calls.append(("write", path))
        def copy(self, src, dst): calls.append(("copy", src, dst))
    monkeypatch.setattr("mountainash_transport.connections.create_connection", lambda *a, **k: Conn())
    monkeypatch.setattr(facade_mod, "get_storage_backend", lambda *a, **k: Backend())
    return calls

def _s3(bucket):
    from mountainash_transport.settings.storage.profiles import S3StorageProfile
    # Construct with the minimal required fields used in tests/settings/storage/profiles (REGION etc.), plus BUCKET.
    extra = {} if bucket is None else {"BUCKET": bucket}
    return S3StorageProfile(**_S3_MINIMAL, **extra)

def _sftp(host):
    from mountainash_transport.settings.storage.profiles import SFTPStorageProfile
    return SFTPStorageProfile(**_SFTP_MINIMAL, HOST=host)

def test_s3_profile_bucket_permits_own_bucket_only(fake_backend):
    fac = StorageFacade.from_path("s3://bucket-a/k", _s3("bucket-a"), policy=LocationPolicy())
    fac.read("s3://bucket-a/k"); fac.read("bucket-a/k")
    with pytest.raises(LocationNotAllowed): fac.read("s3://bucket-b/k")
    assert [c[1] for c in fake_backend] == ["s3://bucket-a/k", "bucket-a/k"]

def test_s3_profile_without_bucket_permits_any_bucket(fake_backend):
    fac = StorageFacade.from_path("s3://x/k", _s3(None), policy=LocationPolicy())
    fac.read("s3://any-bucket/k")
    assert fake_backend == [("read", "s3://any-bucket/k")]

def test_s3_without_profile_needs_allow_list(fake_backend):
    with pytest.raises(LocationNotAllowed):
        StorageFacade.from_path("s3://b/k", policy=LocationPolicy()).read("s3://b/k")
    assert fake_backend == []

def test_sftp_url_host_must_match_profile(fake_backend):
    fac = StorageFacade.from_path("sftp://host-a/p", _sftp("host-a"), policy=LocationPolicy())
    fac.read("/remote/p")
    with pytest.raises(LocationNotAllowed): fac.read("sftp://host-b/p")

def test_equal_policies_different_s3_profiles_use_stream_branch(fake_backend):
    from mountainash_transport import copy_between
    pol = LocationPolicy()
    src = StorageFacade.from_path("s3://a/k", _s3("a"), policy=pol)
    dst = StorageFacade.from_path("s3://b/k", _s3("b"), policy=pol)
    copy_between("s3://a/k", "s3://b/k", src, dst)
    assert ("copy", "s3://a/k", "s3://b/k") not in fake_backend
    assert ("write", "s3://b/k") in fake_backend

def test_unknown_scheme_rejected_before_provider_detection():
    with pytest.raises(LocationNotAllowed) as e:
        StorageFacade.from_path("hf://user:secret@host/x", policy=LocationPolicy())
    assert "secret" not in str(e.value)

@pytest.mark.parametrize("bucket", ["bucket-a", None])
def test_unknown_scheme_rejected_at_operation_time(fake_backend, bucket):
    fac = StorageFacade.from_path("s3://bucket-a/k", _s3(bucket), policy=LocationPolicy())
    with pytest.raises(LocationNotAllowed) as e: fac.read("hf://user:secret@host/x")
    assert "secret" not in str(e.value) and fake_backend == []


@pytest.mark.parametrize("policy", [None, LocationPolicy(allow_unconfined=True)])
def test_invalid_s3_path_keeps_value_error_when_policy_inactive(fake_backend, policy):
    from mountainash_transport.storage.backends.s3.s3_path import parse_s3_path
    fac = StorageFacade.from_path("s3://b/k", policy=policy)
    fac._backend.read_to_bytes = fac._backend.read_to_stream = lambda path: parse_s3_path(path)
    with pytest.raises(ValueError) as e:
        fac.read("s3://")
    assert not isinstance(e.value, LocationNotAllowed)


def test_http_backend_rejects_location_check_with_injected_engine():
    import httpx
    from mountainash_transport._core.http.engine import HttpRequestEngine
    from mountainash_transport.storage.backends.http import HTTPStorageBackend
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as c:
        with pytest.raises(ValueError, match="location_check cannot be combined"):
            HTTPStorageBackend(engine=HttpRequestEngine(c), location_check=lambda u: None)

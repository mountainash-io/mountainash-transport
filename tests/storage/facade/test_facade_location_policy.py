import pytest
from mountainash_auth_client import NoAuthProfile

from mountainash_transport import StorageFacade, copy_between
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport.location import LocationNotAllowed, LocationPolicy
from mountainash_transport.settings.storage.profiles import LOCAL_SPEC, LocalStorageProfile

LOCAL = CONST_STORAGE_PROVIDER_TYPE.LOCAL


def local_profile(**kw):
    return LocalStorageProfile(PROVIDER_TYPE=LOCAL, auth=NoAuthProfile(), **kw)


@pytest.fixture
def dirs(tmp_path):
    a = tmp_path / "a"; b = tmp_path / "b"; out = tmp_path / "out"
    for d in (a, b, out):
        d.mkdir()
    (a / "f.csv").write_bytes(b"1"); (out / "victim").write_bytes(b"keep")
    return a, b, out


def local(root):
    return StorageFacade.for_local(policy=LocationPolicy(root=str(root)))


def test_root_path_profile_confines(dirs):
    a, _, out = dirs
    fac = StorageFacade(LOCAL, local_profile(ROOT_PATH=str(a)))
    assert fac.read("f.csv") == b"1"
    for call in (lambda: fac.read(str(out / "victim")), lambda: fac.write("../out/x", b"z"),
                 lambda: fac.mkdir("../out/d"), lambda: fac.delete(str(out / "victim")),
                 lambda: fac.exists(str(out / "victim")), lambda: fac.list_dir(str(out))):
        with pytest.raises(LocationNotAllowed):
            call()


def test_root_path_kept_when_caller_adds_only_allow_list(dirs):
    a, _, out = dirs
    fac = StorageFacade(LOCAL, local_profile(ROOT_PATH=str(a)),
                        policy=LocationPolicy(allowed_remote={"https": frozenset()}))
    with pytest.raises(LocationNotAllowed):
        fac.read(str(out / "victim"))


def test_no_policy_is_today(dirs):
    _, _, out = dirs
    assert StorageFacade.for_local().read(str(out / "victim")) == b"keep"


def test_copy_into_dir_with_outbound_symlink_rejected(dirs):
    a, _, out = dirs
    (a / "dst").mkdir(); (a / "dst" / "f.csv").symlink_to(out / "victim")
    with pytest.raises(LocationNotAllowed):
        local(a).copy("f.csv", "dst")
    assert (out / "victim").read_bytes() == b"keep"


def test_copy_into_dir_where_derived_name_is_dir_rejected(dirs):
    a, _, out = dirs
    (a / "dst" / "f.csv").mkdir(parents=True); (a / "dst" / "f.csv" / "f.csv").symlink_to(out / "victim")
    with pytest.raises(LocationNotAllowed):
        local(a).copy("f.csv", "dst")
    assert (out / "victim").read_bytes() == b"keep"


def test_copy_between_two_roots_relative_endpoints(dirs):
    a, b, _ = dirs
    copy_between("f.csv", "g.csv", local(a), local(b))
    assert (b / "g.csv").read_bytes() == b"1"


@pytest.mark.parametrize("layout", ["symlink_at_derived_name", "dir_at_derived_name"])
def test_copy_between_shortcut_applies_final_destination_rule(dirs, layout):
    a, _, out = dirs
    if layout == "symlink_at_derived_name":
        (a / "dst").mkdir(); (a / "dst" / "f.csv").symlink_to(out / "victim")
    else:
        (a / "dst" / "f.csv").mkdir(parents=True); (a / "dst" / "f.csv" / "f.csv").symlink_to(out / "victim")
    same = LocationPolicy(root=str(a))
    with pytest.raises(LocationNotAllowed):
        copy_between("f.csv", "dst", StorageFacade.for_local(policy=same), StorageFacade.for_local(policy=same))
    assert (out / "victim").read_bytes() == b"keep"


def test_mount_spec_removed():
    assert "MOUNT_SPEC" not in {p.name for p in LOCAL_SPEC.parameters}
    assert "mount_spec" not in local_profile(ROOT_PATH="/tmp/x").to_handler_kwargs()


def test_create_path_creates_root(tmp_path):
    root = tmp_path / "new-root"
    StorageFacade(LOCAL, local_profile(ROOT_PATH=str(root), CREATE_PATH=True))
    assert root.is_dir()


def test_create_path_not_created_outside_caller_root(tmp_path):
    safe = tmp_path / "safe"; safe.mkdir()
    outside = tmp_path / "outside" / "new"
    StorageFacade(LOCAL, local_profile(ROOT_PATH=str(outside), CREATE_PATH=True),
                  policy=LocationPolicy(root=str(safe)))
    assert not outside.exists()


def test_create_path_created_inside_caller_root(tmp_path):
    safe = tmp_path / "safe"; safe.mkdir()
    inside = safe / "new"
    StorageFacade(LOCAL, local_profile(ROOT_PATH=str(inside), CREATE_PATH=True),
                  policy=LocationPolicy(root=str(safe)))
    assert inside.is_dir()


_INACTIVE = [None, LocationPolicy(allow_unconfined=True)]


@pytest.mark.parametrize("pol", _INACTIVE)
def test_copy_into_dir_derived_dir_not_policy_error_when_inactive(dirs, pol):
    a, _, _ = dirs
    (a / "dst" / "f.csv").mkdir(parents=True)
    fac = StorageFacade.for_local(policy=pol)
    try:
        fac.copy(str(a / "f.csv"), str(a / "dst"))
    except LocationNotAllowed:
        pytest.fail("policy error with no active policy")
    except Exception:
        pass


@pytest.mark.parametrize("pol", _INACTIVE)
def test_malformed_url_not_policy_error_when_inactive(pol):
    fac = StorageFacade.from_path("https://example.com/x", policy=pol)
    try:
        fac.exists("https://[bad")
    except LocationNotAllowed:
        pytest.fail("policy error with no active policy")
    except Exception:
        pass


def test_denied_credential_url_with_gpg_suffix_does_not_leak():
    url = "https://user:secret@denied.example/data.csv.gpg"
    fac = StorageFacade.from_path(url, policy=LocationPolicy())
    with pytest.raises(LocationNotAllowed) as ei:
        fac.read_stream(url, infer=True)
    assert "secret" not in str(ei.value)


def test_create_path_relative_root_created_nowhere_outside_caller_root(tmp_path, monkeypatch):
    safe = tmp_path / "safe"; safe.mkdir()
    work = tmp_path / "work"; work.mkdir()
    monkeypatch.chdir(work)
    StorageFacade(LOCAL, local_profile(ROOT_PATH="outside/new", CREATE_PATH=True),
                  policy=LocationPolicy(root=str(safe)))
    assert not (work / "outside").exists()
    assert not (safe / "outside").exists()


@pytest.mark.parametrize("pol", _INACTIVE)
def test_inactive_policy_check_is_identity_for_local(pol):
    fac = StorageFacade.for_local(policy=pol)
    for p in ("file:///x", "file://otherhost/x", "rel/x"):
        assert fac._check(p) == p


@pytest.mark.parametrize("pol", _INACTIVE)
def test_inactive_policy_from_path_malformed_url_not_policy_error(pol):
    with pytest.raises(ValueError) as ei:
        StorageFacade.from_path("https://[bad", policy=pol)
    assert not isinstance(ei.value, LocationNotAllowed)


def test_policy_free_classification_propagates_value_error():
    from mountainash_transport.storage.path_helpers import StoragePath
    from mountainash_transport.storage.registry.backend_detection import detect_provider_from_path

    for fn in (StoragePath.identify_scheme, detect_provider_from_path):
        with pytest.raises(ValueError) as ei:
            fn("https://[bad")
        assert not isinstance(ei.value, LocationNotAllowed)


def test_active_policy_malformed_url_sanitized_no_secret():
    from mountainash_transport.location import require_known_scheme

    with pytest.raises(LocationNotAllowed) as ei:
        require_known_scheme("https://user:s3cret@[bad", LocationPolicy())
    assert "s3cret" not in str(ei.value)


def _infer(path):
    from mountainash_transport import infer_pipeline
    infer_pipeline(path)


def _parse_s3(path):
    from mountainash_transport.storage.backends.s3.s3_path import parse_s3_path
    parse_s3_path(path)


def _normalize(path):
    from mountainash_transport.storage.path_helpers import StoragePath
    StoragePath.normalize(path)


@pytest.mark.parametrize("pol", _INACTIVE)
@pytest.mark.parametrize(("fn", "path", "kept"), [
    ("from_path", "ftp2://alice:s3cr3t@host/x", "ftp2://host/x"),
    ("parse_s3", "s3://alice:s3cr3t@", "s3://"),
    ("infer", "https://alice:s3cr3t@h/x.gpg", "https://h/x.gpg"),
    ("normalize", "ftp2://alice:s3cr3t@host/x", "ftp2://host/x"),
    ("normalize", "s3:alice:s3cr3t@bucket/k", "'s3'"),
])
def test_dispatch_errors_redact_userinfo_without_policy(pol, fn, path, kept):
    call = {"from_path": lambda p: StorageFacade.from_path(p, policy=pol),
            "parse_s3": _parse_s3, "infer": _infer, "normalize": _normalize}[fn]
    with pytest.raises(ValueError) as ei:
        call(path)
    assert "s3cr3t" not in str(ei.value) and "alice" not in str(ei.value)
    assert kept in str(ei.value)


def _chain(exc):
    pending, seen = [exc], set()
    while pending:
        current = pending.pop()
        if id(current) not in seen:
            seen.add(id(current))
            yield current
            pending.extend(e for e in (current.__cause__, current.__context__) if e is not None)


@pytest.mark.parametrize("pol", [None, LocationPolicy(allow_unconfined=True), LocationPolicy()])
@pytest.mark.parametrize(("fn", "path"), [
    ("from_path", "ftp2://host/x?sig=s3cr3t"),                # unknown scheme, query token (#62)
    ("from_path", "alice:s3cr3t@host/x.csv"),                 # scheme-less userinfo (#64)
    ("from_path", "alice:pa@s3cr3t@host/x.csv"),               # scheme-less, "@" in password (#64)
    ("normalize", "ftp2://host/x?X-Amz-Signature=s3cr3t"),     # (#62)
    ("normalize", "alice:s3cr3t@host/x.csv"),                 # (#64)
    ("parse_s3", "s3://?X-Amz-Signature=s3cr3t"),              # invalid S3 path with query (#62)
])
def test_dispatch_errors_hide_query_values_and_schemeless_userinfo(pol, fn, path):
    call = {"from_path": lambda p: StorageFacade.from_path(p, policy=pol),
            "parse_s3": _parse_s3, "normalize": _normalize}[fn]
    with pytest.raises((ValueError, LocationNotAllowed)) as ei:
        call(path)
    for link in _chain(ei.value):
        for text in (str(link), repr(link), repr(link.args), repr(vars(link))):
            assert "s3cr3t" not in text, f"{type(link).__name__}: {text}"


@pytest.mark.parametrize(("location", "expected"), [
    ("s3://bucket/x.zip?X-Amz-Signature=s3cr3t&X-Amz-Expires=60",
     "s3://bucket/x.zip?X-Amz-Signature=***&X-Amz-Expires=***"),
    ("https://alice:pa@s3cr3t@h/x?t=s3cr3t#frag", "https://h/x?t=***#frag"),
    ("alice:s3cr3t@host/x.csv", "***@host/x.csv"),
    ("s3:alice:s3cr3t@bucket/k", "***@bucket/k"),
    ("/data/report@2026.csv", "/data/report@2026.csv"),     # "@" after the first "/" is a path
    ("relative/file.csv", "relative/file.csv"),
])
def test_location_not_allowed_redacts(location, expected):
    err = LocationNotAllowed(location, "remote not allowed")
    assert err.location == expected
    assert "s3cr3t" not in str(err) and "s3cr3t" not in repr(err)

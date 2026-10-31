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


def test_explicit_profile_policy_confines(dirs):
    a, _, out = dirs
    fac = StorageFacade(LOCAL, local_profile(ROOT_PATH=str(a), LOCATION_POLICY={}))
    assert fac.read("f.csv") == b"1"
    for call in (lambda: fac.read(str(out / "victim")), lambda: fac.write("../out/x", b"z"),
                 lambda: fac.mkdir("../out/d"), lambda: fac.delete(str(out / "victim")),
                 lambda: fac.exists(str(out / "victim")), lambda: fac.list_dir(str(out))):
        with pytest.raises(LocationNotAllowed):
            call()


def test_root_path_resolves_without_enabling_confinement(dirs):
    a, _, out = dirs
    with StorageFacade(LOCAL, local_profile(ROOT_PATH=str(a))) as facade:
        assert facade.read("f.csv") == b"1"
        assert facade.read("../out/victim") == b"keep"
        facade.write("../out/written", b"outside")
    assert (out / "written").read_bytes() == b"outside"


def test_explicit_none_disables_profile_policy(dirs):
    a, _, out = dirs
    profile = local_profile(ROOT_PATH=str(a), LOCATION_POLICY={})
    with StorageFacade.from_path("../out/victim", profile, policy=None) as facade:
        assert facade.read("../out/victim") == b"keep"


def test_replacement_policy_does_not_retarget_profile_base(dirs):
    a, _, out = dirs
    profile = local_profile(ROOT_PATH=str(a), LOCATION_POLICY={})
    with StorageFacade.from_path("f.csv", profile,
                                 policy=LocationPolicy(root=str(a.parent))) as facade:
        assert facade.read("f.csv") == b"1"
        assert facade.read("../out/victim") == b"keep"


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


def test_active_local_profile_redacts_malformed_authority(dirs):
    import traceback

    root, _, _ = dirs
    secret = "userinfo-redaction-sentinel"
    malformed = f"file://user:{secret}@exam\uff0fple.com/x"
    with StorageFacade(LOCAL, local_profile(ROOT_PATH=str(root), LOCATION_POLICY={})) as facade:
        with pytest.raises(LocationNotAllowed) as caught:
            facade.read(malformed)
    assert secret not in "".join(traceback.format_exception(caught.value))


def test_copy_between_same_profile_preserves_independently_anchored_bases(tmp_path, monkeypatch):
    first, second = tmp_path / "first", tmp_path / "second"
    for directory in (first, second):
        (directory / "data").mkdir(parents=True)
    (first / "data" / "in").write_bytes(b"source")
    (first / "data" / "out").write_bytes(b"keep-source-output")
    (second / "data" / "out").write_bytes(b"old-destination")
    profile = local_profile(ROOT_PATH="data")
    monkeypatch.chdir(first)
    with StorageFacade(LOCAL, profile) as source:
        monkeypatch.chdir(second)
        with StorageFacade(LOCAL, profile) as destination:
            copy_between("in", "out", source, destination)
    assert (second / "data" / "out").read_bytes() == b"source"
    assert (first / "data" / "out").read_bytes() == b"keep-source-output"

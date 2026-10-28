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

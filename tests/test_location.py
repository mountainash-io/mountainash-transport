import os, subprocess, sys
import pytest
from mountainash_transport.location import (
    LocationNotAllowed, LocationPolicy, allow_remote, confine_local, identify_scheme, local_path, require_known_scheme, url_host,
)

@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "root"; (root / "d").mkdir(parents=True); (root / "d" / "a.csv").write_text("v\n1\n")
    out = tmp_path / "out"; out.mkdir(); (out / "s.csv").write_text("v\n9\n")
    (root / "link.csv").symlink_to(out / "s.csv")
    (root / "dlink").symlink_to(root / "d")
    return root, out

def P(root, **kw): return LocationPolicy(root=str(root), **kw)

def test_in_root_relative_returns_effective_absolute(tree):
    root, _ = tree
    assert confine_local("d/a.csv", P(root)) == os.path.realpath(root / "d" / "a.csv")

@pytest.mark.parametrize("loc", ["../out/s.csv", "d/../../out/s.csv"])
def test_dotdot_escape_rejected(tree, loc):
    root, _ = tree
    with pytest.raises(LocationNotAllowed) as e: confine_local(loc, P(root))
    assert e.value.reason == "outside root"

def test_absolute_outside_rejected(tree):
    root, out = tree
    with pytest.raises(LocationNotAllowed): confine_local(str(out / "s.csv"), P(root))

def test_symlink_escape_rejected(tree):
    root, _ = tree
    with pytest.raises(LocationNotAllowed): confine_local("link.csv", P(root))

def test_link_dotdot_resolving_inside_allowed(tree):
    root, _ = tree
    assert confine_local("dlink/../d/a.csv", P(root)).endswith(os.path.join("d", "a.csv"))

def test_missing_write_target_under_root_allowed_and_escape_rejected(tree):
    root, _ = tree
    assert confine_local("new/x.csv", P(root)) == os.path.join(os.path.realpath(root), "new", "x.csv")
    with pytest.raises(LocationNotAllowed): confine_local("new/../../x.csv", P(root))

def test_file_uri_decoded_once(tree):
    root, _ = tree
    good = (root / "d" / "a.csv").as_uri()
    assert confine_local(good, P(root)) == os.path.realpath(root / "d" / "a.csv")
    with pytest.raises(LocationNotAllowed): confine_local(f"file://evilhost{root}/d/a.csv", P(root))
    with pytest.raises(LocationNotAllowed): confine_local(f"{root.as_uri()}/%2e%2e/out/s.csv", P(root))

def test_bare_percent_is_literal(tree):
    root, _ = tree
    assert confine_local("%2e%2e/x.csv", P(root)).endswith("%2e%2e/x.csv")

def test_root_with_glob_characters(tmp_path):
    root = tmp_path / "pkg[12]"; root.mkdir(); (root / "a.csv").write_text("x")
    assert confine_local("a.csv", P(root)) == os.path.realpath(root / "a.csv")

def test_tree_check_rejects_escaping_entry(tree):
    root, out = tree
    (root / "d" / "bad.csv").symlink_to(out / "s.csv")
    with pytest.raises(LocationNotAllowed) as e: confine_local("d", P(root), tree=True)
    assert e.value.reason == "directory entry outside root"
    assert confine_local("d", P(root)) == os.path.realpath(root / "d")   # tree=False: directory checked as itself

def test_tree_check_survives_symlink_loop(tree):
    root, _ = tree
    (root / "d" / "loop").symlink_to(root / "d")
    assert confine_local("d", P(root), tree=True)

def test_unknown_scheme():
    assert identify_scheme("hf://x/y") is None
    assert identify_scheme("S3://b/k") == "s3" and identify_scheme("/a") == "" and identify_scheme("file:///a") == "file"
    with pytest.raises(LocationNotAllowed) as e: require_known_scheme("hf://user:secret@h/x", LocationPolicy())
    assert e.value.reason == "unknown scheme" and "secret" not in str(e.value)
    assert require_known_scheme("hf://x/y", None) is None          # no policy: caller's existing handling applies

def test_dot_in_missing_remainder_is_harmless(tree):
    root, _ = tree
    assert confine_local("new/.", P(root)) == os.path.join(os.path.realpath(root), "new")

def test_allow_remote_rules():
    pol = LocationPolicy(allowed_remote={"https": frozenset({"data.example.com"}), "s3": frozenset()})
    allow_remote("https", "data.example.com", pol)
    allow_remote("s3", "any-bucket", pol)
    with pytest.raises(LocationNotAllowed) as e: allow_remote("https", "evil.example", pol)
    assert e.value.reason == "remote not allowed"
    allow_remote("sftp", "host-a", LocationPolicy(), profile_host="HOST-A")
    with pytest.raises(LocationNotAllowed) as e: allow_remote("sftp", "host-b", LocationPolicy(), profile_host="host-a")
    assert e.value.reason == "profile host mismatch"

def test_url_host_parsing():
    assert url_host("http://allowed@evil.example/x") == "evil.example"
    assert url_host("https://DATA.Example.COM/x") == "data.example.com"
    assert url_host("https://bücher.example/x") == "xn--bcher-kva.example"

@pytest.mark.parametrize("pol", [None, LocationPolicy(root="/nonexistent", allow_unconfined=True)])
def test_inactive_policy_is_today(pol, tree):
    _, out = tree
    assert confine_local(str(out / "s.csv"), pol) == str(out / "s.csv")
    assert confine_local("rel.csv", pol) == "rel.csv"
    allow_remote("https", "anything", pol)

def test_with_declared_root_composition():
    assert LocationPolicy().with_declared_root("/r").root == "/r"
    assert LocationPolicy(root="/x").with_declared_root("/r").root == "/x"
    p = LocationPolicy(allowed_remote={"https": frozenset()}).with_declared_root("/r")
    assert p.root == "/r" and p.allowed_remote

def test_error_redacts_userinfo_and_names_location():
    e = LocationNotAllowed("https://user:secret@h.example/p", "remote not allowed")
    assert "secret" not in str(e) and "h.example/p" in str(e) and e.reason == "remote not allowed"



BAD = "https://user:secret@exam\uff0fple.com/x"

@pytest.mark.parametrize("call", [
    lambda: identify_scheme(BAD),
    lambda: url_host(BAD),
    lambda: local_path(BAD),
    lambda: require_known_scheme(BAD, LocationPolicy()),
    lambda: confine_local(BAD, LocationPolicy(root="/r")),
])
def test_malformed_credential_authority_is_redacted_and_uncaused(call):
    with pytest.raises(LocationNotAllowed) as e: call()
    assert e.value.reason == "invalid location" and "secret" not in str(e.value) and "secret" not in e.value.location
    assert e.value.__cause__ is None and e.value.__suppress_context__

def test_error_constructor_never_raises_on_malformed_authority():
    assert "secret" not in str(LocationNotAllowed(BAD, "x"))

def test_host_normalization_both_sides():
    pol = LocationPolicy(allowed_remote={"https": frozenset({"DATA.Example.COM", "bücher.example"})})
    allow_remote("https", url_host("https://data.example.com/x"), pol)
    allow_remote("https", url_host("https://xn--bcher-kva.example/x"), pol)
    allow_remote("https", url_host("https://BÜCHER.example/x"), pol)
    allow_remote("sftp", url_host("sftp://xn--bcher-kva.example/p"), LocationPolicy(), profile_host="bücher.example")
    allow_remote("sftp", url_host("sftp://bücher.example/p"), LocationPolicy(), profile_host="XN--BCHER-KVA.example")
    with pytest.raises(LocationNotAllowed) as e:
        allow_remote("sftp", "other.example", LocationPolicy(), profile_host="bücher.example")
    assert e.value.reason == "profile host mismatch"

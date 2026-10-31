"""Storage-location confinement policy (stdlib only)."""
from __future__ import annotations
import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from urllib.parse import SplitResult, unquote, urlsplit
from mountainash_transport._core.exceptions import StorageError
from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_transport._schemes import SCHEMES, _ALIAS_TO_CANONICAL

@dataclass(frozen=True)
class LocationPolicy:
    root: str | os.PathLike[str] | None = None
    allowed_remote: Mapping[str, frozenset[str]] = field(default_factory=dict)
    allow_unconfined: bool = False
    @property
    def active(self) -> bool:
        return not self.allow_unconfined
    def with_declared_root(self, declared: str | os.PathLike[str] | None) -> "LocationPolicy":
        return self if self.root is not None or declared is None else replace(self, root=declared)


class _PolicyUnset(Enum):
    UNSET = 0


POLICY_UNSET = _PolicyUnset.UNSET
PolicyOverride = LocationPolicy | None | _PolicyUnset


def resolve_policy(
    policy: PolicyOverride = POLICY_UNSET, storage_profile=None, *, declared_root=None,
) -> LocationPolicy | None:
    """Select an override without confusing omission with explicit off."""
    selected = getattr(storage_profile, "LOCATION_POLICY", None) if policy is POLICY_UNSET else policy
    return selected.with_declared_root(declared_root) if selected is not None else None


_S3_FAMILY = frozenset({
    CONST_STORAGE_PROVIDER_TYPE.S3, CONST_STORAGE_PROVIDER_TYPE.S3EXPRESS,
    CONST_STORAGE_PROVIDER_TYPE.MINIO, CONST_STORAGE_PROVIDER_TYPE.R2,
    CONST_STORAGE_PROVIDER_TYPE.B2,
})
_PROVIDER_SCHEME = {s.provider: s.scheme for s in SCHEMES.values() if s.provider in _S3_FAMILY}


def check_location(path: str, provider, storage_profile, policy: LocationPolicy | None, *, base=None) -> str:
    """Resolve a declared local base, then apply the shared confinement boundary."""
    if policy is not None and policy.active:
        require_known_scheme(path, policy)
    if provider == CONST_STORAGE_PROVIDER_TYPE.LOCAL and base is not None:
        path = os.path.join(base, local_path(path))
    if policy is None or not policy.active:
        return path
    scheme = require_known_scheme(path, policy)
    if provider == CONST_STORAGE_PROVIDER_TYPE.LOCAL:
        return confine_local(path, policy)
    if provider in _S3_FAMILY:
        profile_bucket = getattr(storage_profile, "BUCKET", None)
        if storage_profile is None or profile_bucket:
            from mountainash_transport.storage.backends.s3.s3_path import parse_s3_path

            try:
                bucket, _ = parse_s3_path(path)
            except ValueError:
                raise LocationNotAllowed(path, "invalid location") from None
            allow_remote(_PROVIDER_SCHEME[provider], bucket.lower(), policy,
                         profile_host=profile_bucket)
    elif provider == CONST_STORAGE_PROVIDER_TYPE.SFTP:
        if scheme == "sftp":
            allow_remote("sftp", url_host(path), policy,
                         profile_host=getattr(storage_profile, "HOST", None))
    elif provider == CONST_STORAGE_PROVIDER_TYPE.HTTP and scheme is not None:
        allow_remote(scheme, url_host(path), policy)
    return path

class LocationNotAllowed(StorageError):
    def __init__(self, location: str, reason: str) -> None:
        self.location = _redact(location)
        self.reason = reason
        super().__init__(f"location not allowed: {self.location} ({reason})")

_C0_OR_SPACE = "".join(chr(c) for c in range(0x21)) 

def _redact(location: str) -> str:
    """Strip userinfo without urllib, mirroring what urllib sees; never raises."""
    text = location.strip(_C0_OR_SPACE)
    for ch in "\t\r\n":
        text = text.replace(ch, "")
    start = text.find("//")
    if start < 0:
        return text
    start += 2
    end = len(text)
    for ch in "/?#":
        i = text.find(ch, start)
        if i != -1:
            end = min(end, i)
    at = text.rfind("@", start, end)
    return text if at < 0 else text[:start] + text[at + 1:]

def _split(location: str) -> SplitResult:
    return urlsplit(location)  # ValueError propagates; enforcement boundaries sanitize it

def _sanitized(fn, location: str):
    """Run *fn* for an active-policy boundary, mapping parse ValueError to a sanitized error."""
    try:
        return fn()
    except ValueError as exc:
        if isinstance(exc, LocationNotAllowed):
            raise
        failed = True
    if failed:
        raise LocationNotAllowed(location, "invalid location") from None

def _norm_host(host: str) -> str | None:
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None

def identify_scheme(location: str) -> str | None:
    if os.name == "nt" and len(location) > 2 and location[1] == ":" and location[2] in "\\/":
        return ""                                   # drive path (spec §1 rule 3; not CI-verified)
    if os.name == "nt" and location.startswith("\\\\"):
        return ""                                   # UNC
    scheme = _split(location).scheme.lower()
    if not scheme:
        return ""
    if scheme == "file":
        return "file"
    canonical = _ALIAS_TO_CANONICAL.get(scheme, scheme)
    return canonical if canonical in SCHEMES else None

def local_path(location: str) -> str:
    if identify_scheme(location) != "file":
        return location
    parts = _split(location)
    if parts.netloc not in ("", "localhost") or parts.query or parts.fragment:
        raise LocationNotAllowed(location, "invalid file URI")
    path = unquote(parts.path)
    if not os.path.isabs(path):
        raise LocationNotAllowed(location, "invalid file URI")
    return path

def url_host(location: str) -> str:
    try:
        host = urlsplit(location).hostname or ""
    except ValueError:
        host = None
    normalized = _norm_host(host) if host else ""
    if host is None or normalized is None:
        raise LocationNotAllowed(location, "invalid location") from None
    return normalized

def require_known_scheme(location: str, policy: LocationPolicy | None) -> str | None:
    if policy is not None and policy.active:
        scheme = _sanitized(lambda: identify_scheme(location), location)
    else:
        scheme = identify_scheme(location)
    if scheme is None and policy is not None and policy.active:
        raise LocationNotAllowed(location, "unknown scheme")
    return scheme

def _resolve(path: str) -> str:
    if os.path.lexists(path):
        return os.path.realpath(path)
    head, tail = os.path.split(path)
    if head == path:
        return path
    if tail == ".":
        return _resolve(head)
    if tail == "..":
        raise LocationNotAllowed(path, "outside root")
    return os.path.join(_resolve(head), tail)

def confine_local(location: str, policy: LocationPolicy | None, *, tree: bool = False) -> str:
    if policy is None or not policy.active or policy.root is None:
        return local_path(location)
    path = _sanitized(lambda: local_path(location), location)
    root = os.path.realpath(policy.root)
    effective = _resolve(os.path.join(root, path))
    if not Path(effective).is_relative_to(root):
        raise LocationNotAllowed(location, "outside root")
    if tree and os.path.isdir(effective):
        _check_tree(effective, root)
    return effective

def _check_tree(top: str, root: str) -> None:
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(top, followlinks=True):
        real = os.path.realpath(dirpath)
        if real in seen:
            dirnames[:] = []
            continue
        seen.add(real)
        for name in (*dirnames, *filenames):
            entry = os.path.join(dirpath, name)
            if not Path(os.path.realpath(entry)).is_relative_to(root):
                raise LocationNotAllowed(entry, "directory entry outside root")

def allow_remote(scheme: str, host: str, policy: LocationPolicy | None, *, profile_host: str | None = None) -> None:
    if policy is None or not policy.active:
        return
    want = _norm_host(host)
    prof = _norm_host(profile_host) if profile_host is not None else None
    allowed = policy.allowed_remote.get(scheme)
    entries = None if allowed is None else {_norm_host(h) for h in allowed}
    if want is None or (profile_host is not None and prof is None) or (entries is not None and None in entries):
        raise LocationNotAllowed(f"{scheme}://{host}", "invalid location")
    if profile_host is not None:
        if want == prof:
            return
        reason = "profile host mismatch"
    else:
        reason = "remote not allowed"
    if entries is not None and (not entries or want in entries):
        return
    raise LocationNotAllowed(f"{scheme}://{host}", reason)

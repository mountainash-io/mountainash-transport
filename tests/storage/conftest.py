"""Fixtures shared by storage tests."""
from __future__ import annotations

import typing as t
from pathlib import Path

import pytest


@pytest.fixture(params=["local", "sftp"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> t.Iterator[tuple[str, t.Any, Path, str]]:
    """A directory store: backend name, a facade, the real directory behind it, and the facade's prefix for it.

    The SFTP facade talks to the in-process loopback server in ``connections.tunnel_rig``,
    which serves the same directory, so tests can inspect results on disk.
    """
    from mountainash_auth_client import PasswordAuthProfile

    from mountainash_transport import StorageFacade
    from mountainash_transport._core.constants import CONST_STORAGE_PROVIDER_TYPE as P
    from mountainash_transport.settings.storage.profiles import SFTPStorageProfile

    root = tmp_path / "root"
    root.mkdir()
    if request.param == "local":
        with StorageFacade.for_local() as facade:
            yield "local", facade, root, str(root)
        return
    from connections.tunnel_rig import DirectorySFTPTarget

    server = DirectorySFTPTarget(root)
    known = tmp_path / "known_hosts"
    known.write_text(server.known_hosts_line("127.0.0.1"))
    profile = SFTPStorageProfile(HOST="127.0.0.1", PORT=server.port, USERNAME="u", KNOWN_HOSTS_FILE=str(known),
                                 LOOK_FOR_KEYS=False, ALLOW_AGENT=False)
    try:
        with StorageFacade(P.SFTP, profile, auth_profile=PasswordAuthProfile(USERNAME="u", PASSWORD="p")) as facade:
            yield "sftp", facade, root, ""
    finally:
        server.close()

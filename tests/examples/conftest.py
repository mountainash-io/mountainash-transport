"""Isolate example subprocesses from host configuration; provide the SSH servers some recipes name."""

import os
import typing as t
from pathlib import Path

import pytest

from connections.tunnel_rig import TARGET, Bastion, DirectorySFTPTarget, HTTPTarget


@pytest.fixture(scope="session")
def example_servers(tmp_path_factory: pytest.TempPathFactory) -> t.Iterator[dict[str, str]]:
    """In-process SFTP server, SSH bastion and HTTP target for the SFTP and tunnel recipes."""
    base = tmp_path_factory.mktemp("example-servers")
    sftp_root = base / "sftp-root"
    (sftp_root / "home").mkdir(parents=True)
    sftp, bastion, target = DirectorySFTPTarget(sftp_root), Bastion(), HTTPTarget()
    known_hosts = {}
    for name, server in (("sftp", sftp), ("bastion", bastion)):
        known_hosts[name] = base / f"{name}_known_hosts"
        known_hosts[name].write_text(server.known_hosts_line("127.0.0.1"))
    yield {
        "TRANSPORT_EXAMPLE_SFTP_HOST": "127.0.0.1",
        "TRANSPORT_EXAMPLE_SFTP_PORT": str(sftp.port),
        "TRANSPORT_EXAMPLE_SFTP_USER": "u",
        "TRANSPORT_EXAMPLE_SFTP_PASSWORD": "p",
        "TRANSPORT_EXAMPLE_SFTP_KNOWN_HOSTS": str(known_hosts["sftp"]),
        "TRANSPORT_EXAMPLE_SFTP_DIR": "/home",
        "TRANSPORT_EXAMPLE_BASTION_HOST": "127.0.0.1",
        "TRANSPORT_EXAMPLE_BASTION_PORT": str(bastion.port),
        "TRANSPORT_EXAMPLE_BASTION_USER": "u",
        "TRANSPORT_EXAMPLE_BASTION_PASSWORD": "p",
        "TRANSPORT_EXAMPLE_BASTION_KNOWN_HOSTS": str(known_hosts["bastion"]),
        "TRANSPORT_EXAMPLE_TARGET_HOST": TARGET,  # only the bastion resolves this name
        "TRANSPORT_EXAMPLE_TARGET_PORT": str(target.port),
    }
    for close in (sftp.close, bastion.close, target.close):
        close()
    assert not any((sftp_root / "home").iterdir()), "the SFTP recipe must clean up after itself"


@pytest.fixture
def example_environment(example_servers: dict[str, str]) -> dict[str, str]:
    """Drop inputs that could change example output; keep subprocess coverage settings."""
    environment = {
        key: value for key, value in os.environ.items()
        if key.upper() not in {
            "MOUNTAINASH_PROFILES_CONFIG", "PYTHONPATH", "PYTHONHOME",
            "PYTHONOPTIMIZE", "PYTEST_ADDOPTS", "PYTEST_PLUGINS",
        }
        and not key.upper().startswith(("AWS_", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"))
    }
    environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    environment.update(example_servers)
    return environment

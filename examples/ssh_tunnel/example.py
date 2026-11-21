"""Reach an internal HTTP service through an SSH bastion."""

import os
import sys

from mountainash_auth_client import PasswordAuthProfile
from mountainash_transport import create_tunnelled_connection
from mountainash_transport.settings.storage.profiles import HTTPStorageProfile, SFTPStorageProfile

SETTINGS = ("BASTION_HOST", "BASTION_PORT", "BASTION_USER", "BASTION_PASSWORD",
            "BASTION_KNOWN_HOSTS", "TARGET_HOST", "TARGET_PORT")


def main() -> None:
    env = {name: os.environ.get(f"TRANSPORT_EXAMPLE_{name}") for name in SETTINGS}
    if None in env.values():
        sys.exit("Set TRANSPORT_EXAMPLE_" + ", _".join(SETTINGS) + " to name a bastion and target (see README)")

    bastion = SFTPStorageProfile(
        HOST=env["BASTION_HOST"], PORT=int(env["BASTION_PORT"]), USERNAME=env["BASTION_USER"],
        KNOWN_HOSTS_FILE=env["BASTION_KNOWN_HOSTS"], ALLOW_AGENT=False, LOOK_FOR_KEYS=False,
    )
    bastion_auth = PasswordAuthProfile(USERNAME=env["BASTION_USER"], PASSWORD=env["BASTION_PASSWORD"])
    target_host, target_port = env["TARGET_HOST"], int(env["TARGET_PORT"])

    tunnel = create_tunnelled_connection(
        bastion, bastion_auth, HTTPStorageProfile(), None, target_host, target_port,
    )
    with tunnel.connect() as connection:
        # The URL names the real target; the tunnel carries it through the bastion.
        response = connection.client.get(f"http://{target_host}:{target_port}/reports/status")
        tunnel_open = connection.local_port is not None
    assert tunnel.local_port is None  # closing the tunnel releases its listener

    print(f"tunnel open: {tunnel_open}; GET /reports/status -> {response.status_code} {response.text}")


if __name__ == "__main__":
    main()

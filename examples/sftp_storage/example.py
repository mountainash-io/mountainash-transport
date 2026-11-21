"""Write, read, list and delete files on an SFTP server, with host-key checking."""

import os
import sys

from mountainash_auth_client import PasswordAuthProfile
from mountainash_transport import StorageFacade
from mountainash_transport.settings.storage.profiles import SFTPStorageProfile

SALES = b"region,total\nnorth,120\nsouth,95\n"
SETTINGS = ("HOST", "PORT", "USER", "PASSWORD", "KNOWN_HOSTS", "DIR")


def main() -> None:
    env = {name: os.environ.get(f"TRANSPORT_EXAMPLE_SFTP_{name}") for name in SETTINGS}
    if None in env.values():
        sys.exit("Set TRANSPORT_EXAMPLE_SFTP_" + ", _".join(SETTINGS) + " to name an SFTP server (see README)")

    profile = SFTPStorageProfile(
        HOST=env["HOST"], PORT=int(env["PORT"]), USERNAME=env["USER"],
        KNOWN_HOSTS_FILE=env["KNOWN_HOSTS"],  # unknown host keys are refused by default
        ALLOW_AGENT=False, LOOK_FOR_KEYS=False,
    )
    auth = PasswordAuthProfile(USERNAME=env["USER"], PASSWORD=env["PASSWORD"])
    folder = f"{env['DIR'].rstrip('/')}/reports"
    path = f"{folder}/sales.csv"

    with StorageFacade.from_path(f"sftp://{env['HOST']}{path}", profile, auth_profile=auth) as storage:
        storage.write(path, SALES)  # missing parent folders are created
        assert storage.read(path) == SALES
        listing = [entry.name for entry in storage.list_dir(folder)]
        size = storage.get_size(path)
        storage.delete(path)
        storage.rmdir(folder)
        assert not storage.exists(folder)

    print(f"listed {listing}; sales.csv: {size} bytes written, read back and deleted")


if __name__ == "__main__":
    main()

"""Resolve named storage profiles from a YAML file and use one."""

import tempfile
from pathlib import Path

from mountainash_settings import SettingsParameters

from mountainash_transport import ProfileNotFoundError, StorageFacade, resolve_storage

SALES = b"region,total\nnorth,120\nsouth,95\n"
HERE = Path(__file__).resolve().parent


def main() -> None:
    params = SettingsParameters.create(config_files=[str(HERE / "profiles.yaml")])

    lake, lake_auth = resolve_storage("lake", settings_parameters=params)
    archive, archive_auth = resolve_storage("archive", settings_parameters=params)
    assert type(lake).__name__ == "S3StorageProfile" and lake.BUCKET == "reports"
    assert type(lake_auth).__name__ == "IAMAuthProfile"
    assert type(archive_auth).__name__ == "NoAuthProfile"

    try:
        resolve_storage("warehouse", settings_parameters=params)
    except ProfileNotFoundError:
        missing = True
    else:
        missing = False
    assert missing

    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv")
        storage = StorageFacade.from_path(path, archive, auth_profile=archive_auth)
        storage.write(path, SALES)
        assert storage.read(path) == SALES

    print(f"lake: {lake.get_connection_url()} with {type(lake_auth).__name__}")
    print(f"archive: local with {type(archive_auth).__name__}; wrote and read sales.csv")


if __name__ == "__main__":
    main()

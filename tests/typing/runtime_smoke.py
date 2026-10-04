"""Installed runtime smoke; executed by tools/qualify_typing.py outside the checkout."""
from __future__ import annotations

import tempfile
from pathlib import Path

from mountainash_transport import Gzip, StorageFacade
from mountainash_transport.settings.storage.profiles.s3_storage_profile import S3StorageProfile


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv.gz")
        storage = StorageFacade.from_path(path)
        storage.write(path, b"region,total\nnorth,120\n", pipeline=Gzip())
        assert storage.read(path, infer=True) == b"region,total\nnorth,120\n"
    profile = S3StorageProfile(FLAVOR="r2", ACCOUNT_ID="abc123", BUCKET="reports")
    assert profile.FLAVOR == "r2" and profile.BUCKET == "reports"
    assert profile.get_connection_url() == "https://abc123.r2.cloudflarestorage.com"
    print("Installed runtime smoke passed")


if __name__ == "__main__":
    main()

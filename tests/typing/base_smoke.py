"""Base-install smoke; executed by tools/qualify_typing.py in a venv with only the wheel."""
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

from mountainash_transport import Gzip, MissingExtraError, StorageFacade

STACK = ("mountainash_settings", "mountainash_auth_client", "pydantic", "upath", "httpx", "fsspec")


def main() -> None:
    present = [name for name in STACK if importlib.util.find_spec(name) is not None]
    assert not present, present
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv.gz")
        with StorageFacade.from_path(path) as storage:
            storage.write(path, b"region,total\nnorth,120\n", pipeline=Gzip())
            assert storage.read(path, infer=True) == b"region,total\nnorth,120\n"
    try:
        StorageFacade.from_path("https://example.com/a.csv")
    except MissingExtraError as err:
        assert err.extra == "http"
    else:
        raise AssertionError("https on base must raise MissingExtraError")
    print("Base install smoke passed")


if __name__ == "__main__":
    main()

"""Write, read, inspect and delete one local file through the facade."""

import tempfile
from pathlib import Path

from mountainash_transport import EntryType, StorageFacade

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv")
        storage = StorageFacade.from_path(path)

        storage.write(path, SALES)
        entry = storage.metadata(path)
        assert storage.read(path) == SALES
        assert storage.exists(path)
        assert storage.get_size(path) == len(SALES) == entry.size
        assert entry.name == "sales.csv" and entry.entry_type is EntryType.FILE

        storage.delete(path)
        assert not storage.exists(path)
        print(f"{entry.name}: {entry.size} bytes written, read back and deleted")


if __name__ == "__main__":
    main()

"""Create a directory, copy a file within it, list it and remove it."""

import tempfile
from pathlib import Path

from mountainash_transport import StorageFacade

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        reports = str(Path(root) / "reports" / "2026")
        storage = StorageFacade.for_local()

        storage.mkdir(reports)  # parents=True by default
        storage.write(f"{reports}/sales.csv", SALES)
        storage.copy(f"{reports}/sales.csv", f"{reports}/sales-backup.csv")

        names = sorted(entry.name for entry in storage.list_dir(reports))
        assert names == ["sales-backup.csv", "sales.csv"]

        for name in names:
            storage.delete(f"{reports}/{name}")
        storage.rmdir(reports)
        assert not storage.exists(reports)
        print(f"listed {', '.join(names)}; directory removed")


if __name__ == "__main__":
    main()

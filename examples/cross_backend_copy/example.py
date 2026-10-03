"""Copy between two facades, compressing only on the destination side."""

import tempfile
from pathlib import Path

from mountainash_transport import Gzip, StorageFacade, copy_between

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    with tempfile.TemporaryDirectory() as landing, tempfile.TemporaryDirectory() as archive:
        source_path = str(Path(landing) / "sales.csv")
        archived_path = str(Path(archive) / "sales.csv.gz")
        source = StorageFacade.from_path(source_path)
        destination = StorageFacade.from_path(archived_path)
        source.write(source_path, SALES)

        copy_between(
            source_path, archived_path, source, destination,
            destination_pipeline=Gzip(),
        )

        assert destination.read(archived_path) != SALES
        assert destination.read(archived_path, infer=True) == SALES
        print(f"copied {len(SALES)} bytes; archived {destination.get_size(archived_path)} gzip bytes")


if __name__ == "__main__":
    main()

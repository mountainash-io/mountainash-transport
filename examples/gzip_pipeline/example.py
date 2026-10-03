"""Store a gzip-compressed file and read it back through the same pipeline."""

import gzip
import tempfile
from pathlib import Path

from mountainash_transport import Gzip, Pipeline, StorageFacade

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        first, second = (str(Path(root) / name) for name in ("a.csv.gz", "b.csv.gz"))
        storage = StorageFacade.for_local()
        pipeline = Pipeline(Gzip())

        storage.write(first, SALES, pipeline=pipeline)
        storage.write(second, SALES, pipeline=pipeline)
        stored = storage.read(first)

        assert gzip.decompress(stored) == SALES
        assert storage.read(first, pipeline=pipeline) == SALES
        assert stored == storage.read(second)  # mtime=0: reproducible bytes
        print(f"stored {len(stored)} gzip bytes; decoded {len(SALES)} bytes; output reproducible")


if __name__ == "__main__":
    main()

"""Stream a compressed file line by line, and write from a stream."""

import io
import tempfile
from pathlib import Path

from mountainash_transport import Gzip, StorageFacade

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv.gz")
        storage = StorageFacade.for_local()
        storage.write_stream(path, io.BytesIO(SALES), pipeline=Gzip())

        total = 0
        with storage.read_stream(path, infer=True) as stream:
            lines = io.TextIOWrapper(io.BufferedReader(stream), encoding="utf-8")
            next(lines)  # header
            for line in lines:
                total += int(line.rstrip().split(",")[1])

        assert total == 215
        print(f"streamed total: {total}")


if __name__ == "__main__":
    main()

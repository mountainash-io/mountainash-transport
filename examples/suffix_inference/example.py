"""Infer read-side transforms from a path's suffixes."""

import tempfile
from pathlib import Path

from mountainash_transport import Gzip, StorageFacade, infer_pipeline

SALES = b"region,total\nnorth,120\nsouth,95\n"


def main() -> None:
    pipeline, stripped = infer_pipeline("exports/sales.csv.gz")
    assert pipeline is not None and stripped == "exports/sales.csv"
    assert infer_pipeline("exports/sales.csv") == (None, "exports/sales.csv")

    try:
        infer_pipeline("exports/sales.csv.gz.gpg")
    except ValueError:
        needs_key = True
    else:
        needs_key = False
    assert needs_key  # .gpg needs gpg=GPG(...); key material is never guessed

    with tempfile.TemporaryDirectory() as root:
        path = str(Path(root) / "sales.csv.gz")
        storage = StorageFacade.from_path(path)
        storage.write(path, SALES, pipeline=Gzip())
        assert storage.read(path, infer=True) == SALES

    print(f"sales.csv.gz -> {stripped.rsplit('/', 1)[-1]}; .gpg requires key material")


if __name__ == "__main__":
    main()

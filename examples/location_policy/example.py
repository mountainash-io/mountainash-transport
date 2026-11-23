"""Confine a facade to one directory and allow-list remote buckets."""

import tempfile
from pathlib import Path

from mountainash_transport import StorageFacade
from mountainash_transport.location import LocationNotAllowed, LocationPolicy

SALES = b"region,total\nnorth,120\nsouth,95\n"


def refused(call) -> str:
    try:
        call()
    except LocationNotAllowed as error:
        return str(error)
    raise AssertionError("the policy must refuse this location")


def main() -> None:
    with tempfile.TemporaryDirectory() as root:
        inside = str(Path(root) / "reports" / "sales.csv")
        with StorageFacade.for_local(policy=LocationPolicy(root=root)) as storage:
            storage.write(inside, SALES)  # parents are created inside the root
            assert storage.read(inside) == SALES
            escape = refused(lambda: storage.read(str(Path(root) / ".." / "secrets.txt")))
            outside = refused(lambda: storage.read("/etc/hostname"))
        print("inside root: written and read back")
        print(escape.replace(root, "<root>"))
        print(outside)

    # Remote locations are checked before any connection is made.
    buckets = LocationPolicy(allowed_remote={"s3": frozenset({"reports"})})
    print(refused(lambda: StorageFacade.from_path("s3://archive/sales.csv", policy=buckets)
                  .read("s3://archive/sales.csv")))


if __name__ == "__main__":
    main()

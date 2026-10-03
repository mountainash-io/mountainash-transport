"""Check backend capabilities, and see the error for an unsupported call."""

from mountainash_transport import (
    StorageDirectoryProtocol,
    StorageEnumerateProtocol,
    StorageFacade,
    StorageMetadataProtocol,
    StorageReadProtocol,
    StorageWriteProtocol,
    UnsupportedOperationError,
)

CAPABILITIES = {
    "read": StorageReadProtocol,
    "write": StorageWriteProtocol,
    "metadata": StorageMetadataProtocol,
    "directory": StorageDirectoryProtocol,
    "enumerate": StorageEnumerateProtocol,
}


def supported(storage: StorageFacade) -> list[str]:
    return [name for name, protocol in CAPABILITIES.items() if storage.supports(protocol)]


def main() -> None:
    local = StorageFacade.from_path("/srv/reports/sales.csv")
    web = StorageFacade.from_path("https://files.example.com/reports/sales.csv")
    assert supported(local) == ["read", "write", "metadata", "directory"]
    assert supported(web) == ["read", "write", "metadata"]

    try:
        web.list_dir("https://files.example.com/reports/")
    except UnsupportedOperationError:
        refused = True
    else:
        refused = False
    assert refused

    print(f"local: {', '.join(supported(local))}")
    print(f"https: {', '.join(supported(web))}; list_dir refused")


if __name__ == "__main__":
    main()

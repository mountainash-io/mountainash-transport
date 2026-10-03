"""Detect providers from URL schemes and normalise storage paths."""

from mountainash_transport import StoragePath, detect_provider_from_path

PATHS = [
    "/srv/reports/sales.csv",
    "s3://reports/2026/sales.csv",
    "r2://reports/2026/sales.csv",
    "gs://reports/2026/sales.csv",
    "sftp://files.example.com/reports/sales.csv",
    "https://files.example.com/reports/sales.csv",
]


def main() -> None:
    providers = {path.split(":", 1)[0] if "://" in path else "(bare)": detect_provider_from_path(path).value for path in PATHS}
    assert providers == {"(bare)": "local", "s3": "s3", "r2": "r2", "gs": "gcs", "sftp": "sftp", "https": "http"}

    assert str(StoragePath.normalize("s3://reports/2026/")) == "s3://reports/2026"
    assert str(StoragePath.join("s3://reports/2026", "sales.csv")) == "s3://reports/2026/sales.csv"
    assert StoragePath.identify_scheme("gcs://reports/x") == "gs"  # alias resolved
    assert StoragePath.matches("*.csv", "sales.csv")

    try:
        StoragePath.normalize("S3://reports/2026")
    except ValueError:
        strict = True
    else:
        strict = False
    assert strict  # mixed-case schemes are rejected, not guessed

    for scheme, provider in providers.items():
        print(f"{scheme} -> {provider}")


if __name__ == "__main__":
    main()

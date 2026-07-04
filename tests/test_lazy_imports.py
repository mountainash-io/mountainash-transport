"""Packaging invariant: importing the package must not import heavy SDKs."""
import subprocess
import sys


def test_top_level_import_stays_light():
    code = (
        "import sys; import mountainash_transport; "
        "heavy = {'boto3', 'botocore', 'paramiko', 'gnupg', 's3fs', 'minio'} "
        "& set(sys.modules); "
        "assert not heavy, f'heavy imports at top level: {heavy}'"
    )
    subprocess.run([sys.executable, "-c", code], check=True)

# SFTP storage

How do I read and write files on an SFTP server, with the server's host key checked?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup)
plus the `[sftp]` extra (`python -m pip install -e ".[s3,sftp]"`). It needs an SSH server
with SFTP, named by environment variables:

| Variable | Meaning |
|---|---|
| `TRANSPORT_EXAMPLE_SFTP_HOST`, `TRANSPORT_EXAMPLE_SFTP_PORT` | Server address |
| `TRANSPORT_EXAMPLE_SFTP_USER`, `TRANSPORT_EXAMPLE_SFTP_PASSWORD` | Password login |
| `TRANSPORT_EXAMPLE_SFTP_KNOWN_HOSTS` | A `known_hosts` file holding the server's key |
| `TRANSPORT_EXAMPLE_SFTP_DIR` | A writable folder on the server; the recipe leaves it as it found it |

```bash
python examples/sftp_storage/example.py
```

Expected output:

```text
listed ['sales.csv']; sales.csv: 32 bytes written, read back and deleted
```

The storage profile describes the server and its host-key checking; the
password comes from an auth profile and is never part of the profile or the
path. An unknown host key is refused by default (`HOST_KEY_POLICY="reject"`).
`write` creates missing folders, and `rmdir` removes only an empty folder.

The test suite runs this recipe against an in-process paramiko server.

Next: [SSH tunnel](../ssh_tunnel/).

# SSH tunnel

How do I reach a service that only a bastion host can see?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup)
plus the `[sftp]` extra (`python -m pip install -e ".[s3,sftp]"`). It needs an SSH
bastion and an HTTP service behind it, named by environment variables:

| Variable | Meaning |
|---|---|
| `TRANSPORT_EXAMPLE_BASTION_HOST`, `TRANSPORT_EXAMPLE_BASTION_PORT` | Bastion address |
| `TRANSPORT_EXAMPLE_BASTION_USER`, `TRANSPORT_EXAMPLE_BASTION_PASSWORD` | Bastion password login |
| `TRANSPORT_EXAMPLE_BASTION_KNOWN_HOSTS` | A `known_hosts` file holding the bastion's key |
| `TRANSPORT_EXAMPLE_TARGET_HOST`, `TRANSPORT_EXAMPLE_TARGET_PORT` | The HTTP service, as the bastion sees it |

```bash
python examples/ssh_tunnel/example.py
```

Expected output:

```text
tunnel open: True; GET /reports/status -> 200 payload
```

`create_tunnelled_connection` opens an SSH session to the bastion and a local
listener. The HTTP client keeps the target's real URL, so the request names the
target host, and TLS (for `https://`) is checked against that host; the bastion
forwards the connection. Closing the tunnel stops the listener and the SSH
session.

The test suite runs this recipe against an in-process bastion that alone
resolves the target's name, so a successful request proves it went through the
tunnel.

Next: [HTTP engine](../http_engine/).

# Location policy

How do I keep a facade inside one directory, or limit which buckets it may reach?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/location_policy/example.py
```

Expected output:

```text
inside root: written and read back
location not allowed: <root>/../secrets.txt (outside root)
location not allowed: /etc/hostname (outside root)
location not allowed: s3://archive (remote not allowed)
```

`LocationPolicy(root=...)` confines local paths: anything that resolves outside
the root, including `..` escapes and symlinks, raises `LocationNotAllowed`.
`allowed_remote` maps a scheme to the hosts or S3 buckets a facade may reach; the
check runs before any connection, so the refused bucket above is never contacted.
Errors show only the safe parts of a location.

Next: [path dispatch](../path_dispatch/).

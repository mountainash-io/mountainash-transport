# Auth compatibility

Which auth profiles can a store use, and what is rejected early?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/auth_compatibility/example.py
```

Expected output:

```text
aws + access keys: accepted
aws + assume role: accepted
aws + password: unsupported auth mode
r2 + assume role: invalid for flavor
```

`create_connection()` checks the auth mode against the profile's
`supported_auth` and asks the auth profile to emit credentials for the store's SDK
family. Accepted pairings return an unconnected connection: nothing is contacted
until `connect()` (which `StorageFacade` calls). Assume-role only reaches AWS STS,
so non-AWS flavors reject `ROLE_ARN`. Auth profiles come from
`mountainash-auth-client`; passwords are never printed.

Next: [named profiles](../named_profiles/).

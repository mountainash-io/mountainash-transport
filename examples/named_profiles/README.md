# Named profiles

How do I select a store and its credentials by name from configuration?

[example.py](example.py) and [profiles.yaml](profiles.yaml) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/named_profiles/example.py
```

Expected output:

```text
lake: https://s3.ap-southeast-2.amazonaws.com with IAMAuthProfile
archive: local with NoAuthProfile; wrote and read sales.csv
```

[profiles.yaml](profiles.yaml) declares each store's provider, parameters and
auth block. `resolve_storage()` validates both halves and the pairing, returning
`(storage_profile, auth_profile)`. Without `settings_parameters=`, it reads the
file named by `MOUNTAINASH_PROFILES_CONFIG`. In real deployments put credentials
behind `secret:` references resolved by a selected secret store (see the root
README); the literal values here are synthetic. Resolving `lake` contacts nothing.

Next: [http engine](../http_engine/).

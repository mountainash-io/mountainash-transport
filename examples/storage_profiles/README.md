# Storage profiles

How does a profile describe a store without holding credentials?

[example.py](example.py) — run from the repository root, after the [shared setup](../README.md#setup):

```bash
python examples/storage_profiles/example.py
```

Expected output:

```text
aws: https://s3.ap-southeast-2.amazonaws.com
r2: https://abc123.r2.cloudflarestorage.com
s3 auth modes: iam, none
```

One `S3StorageProfile` covers AWS, S3 Express, R2, MinIO and B2 through
`FLAVOR`; R2 derives its endpoint from `ACCOUNT_ID`. `to_handler_kwargs()`
returns SDK configuration only — credentials are supplied separately as an auth
profile (see [auth compatibility](../auth_compatibility/)). The registry maps
provider names to profile classes and their `StorageProfileSpec`, which declares
parameters and supported auth modes. Requires the `[s3]` extra (botocore).

Next: [auth compatibility](../auth_compatibility/).

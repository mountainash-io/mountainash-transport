# Storage recipes

Focused, independently runnable examples of file operations, stream transforms,
path dispatch, storage profiles, authentication pairing and the HTTP engine. The
examples share one small dataset so you can compare approaches.

Read in the order below or go straight to the feature you need. Each recipe
declares what it uses and runs independently; none imports another recipe.

## Setup

Use Python 3.12+ and install this checkout, with the S3 extra, from the
repository root:

```bash
python -m pip install -e ".[s3]"
```

Only the profile recipes need the `[s3]` extra (they build botocore client
configuration); nothing connects to S3. All commands run from the repository
root. Input paths are relative to each script, so an absolute script path also
works from another working directory.

Each script prints a small result and checks it with assertions. Run without
Python's `-O` flag. To reproduce the documented output, unset
`MOUNTAINASH_PROFILES_CONFIG`.

No recipe contacts a network service. File recipes work in temporary
directories that they remove. The HTTP recipe answers requests in-process with
`httpx.MockTransport`.

## Shared example data

The examples store a small sales report, `sales.csv`:

```text
region,total
north,120
south,95
```

Remote examples name the bucket `reports` in AWS region `ap-southeast-2`, an R2
account `abc123`, and the web host `files.example.com`. Credentials are
synthetic and never printed.

## Files

| Recipe | Question |
|---|---|
| [Local files](local_files/) | How do I write, read, inspect and delete a file? |
| [Directories](directories/) | How do I create, list, copy within and remove a directory? |
| [Capability checks](capability_checks/) | How do I find out what a backend supports before calling it? |

## Stream transforms

| Recipe | Question |
|---|---|
| [Gzip pipeline](gzip_pipeline/) | How do I compress on write and decompress on read? |
| [Suffix inference](suffix_inference/) | How do I let the file name choose the decoding? |
| [Streaming](streaming/) | How do I process a file without holding it in memory? |
| [Cross-backend copy](cross_backend_copy/) | How do I copy between two storages and re-encode on the way? |

## Paths

| Recipe | Question |
|---|---|
| [Path dispatch](path_dispatch/) | Which backend does a path select, and how are paths normalised? |

## Profiles and authentication

| Recipe | Question |
|---|---|
| [Storage profiles](storage_profiles/) | How does a profile describe a store without holding credentials? |
| [Auth compatibility](auth_compatibility/) | Which auth profiles can a store use, and what is rejected early? |
| [Named profiles](named_profiles/) | How do I select a store and its credentials by name from configuration? |

## HTTP

| Recipe | Question |
|---|---|
| [HTTP engine](http_engine/) | How do HTTP retries and typed errors behave? |

## Not covered offline

S3, SFTP and authenticated HTTP operations need a live service, and GPG needs a
GnuPG keyring. They use the same facade calls shown above, with a storage
profile and auth profile; see [named profiles](named_profiles/) and the root
[README](../README.md#connecting-to-remote-stores).

## Verification

Each recipe runs in a temporary copy of this directory, with ambient
configuration removed. Its output must match the **Expected output** block in
its README:

```bash
hatch run test:test-target-quick tests/examples -q
```

The root README's quick start runs separately. When adding a recipe, update this
index, document its expected output and assert the concept it demonstrates.

Analysis: path_helpers

  How it's using standards (mixed — partially right, partially string-hacking)

  What it does right:
  - Built on universal-pathlib.UPath — the right primitive for scheme-aware paths.
  - Uses urllib.parse.urlparse for scheme extraction (in the newer identify_storage_system).

  What's string-hacking:
  - BasePathHelper.strip_all_slashes/strip_trailing_slashes — manual .strip("\\").strip("/") rather than relying on UPath normalization.
  - wildcard_match — reimplements fnmatch.fnmatch from scratch via regex.
  - _normalize_path_schema slices by string length (path_str[:scheme_length]) and concatenates strings rather than rebuilding via urlunparse.

  Actual bugs I found:
  1. base_path_helper.py:178: path_str.replace(f"{provided_scheme_str}:", f"{scheme_prefix}:", __count=1) — __count=1 isn't a valid kwarg for str.replace (signature is positional count), and the result isn't reassigned. This branch
  is dead on arrival.
  2. _normalize_path_schema has no return in the "all good, uppercase" branch after the .replace() — falls through to None.
  3. S3PathHelper.format_namespace returns "s3://" (empty) when bucket_name is falsy even if path was provided and a bucket was extracted from it — the if bucket_name: on the final return ignores str_bucket_name.
  4. combine_path_and_filename is duplicated verbatim across GCSPathHelper, SSHPathHelper (and the base) — the subclass overrides don't differ from the base.
  5. PathHelper.path_util_classes uses string keys ("S3", "GCS") not CONST_STORAGE_PROVIDER_TYPE enum members, inconsistent with the rest of the package.
  6. _SCHEME_PREFIX_MAP includes B2/FTP/GITHUB/etc. but no helpers exist for them — identify_storage_system can return "B2" and _get_util_class will then raise ValueError.

  Integration surface

  Into storage backends: Currently zero coupling. The facade receives raw strings and backends don't consult path_helpers. There's an obvious seam at storage_registry.get_storage_backend(provider_type, ...) — today the caller must
  know the provider; PathHelper.identify_storage_system(path) could drive this automatically (once it returns the enum, not a string).

  Into mountainash/pydata readers: Also currently zero. relations/dag/readers/{parquet,csv,json}.py each reimplement the same scheme→provider dispatch:
  if path.startswith("s3://"): provider = S3
  elif path.startswith("r2://"): provider = R2
  ...
  This is a copy of what PathHelper.identify_storage_system should do, but duplicated because the helper isn't trustworthy enough to lean on.

  Encrypted parquet ingestion angle: The new storage_transforms work gives us Pipeline(GPG(...), Gzip()) — but nothing today infers that pipeline from a suffix chain like data.parquet.gz.gpg. A path-aware layer could: inspect
  suffixes, build the inverse Pipeline, hand it to facade.read_stream(pipeline=...), then pass the decoded stream to pl.read_parquet.

  Scope observation

  What you're asking about overlaps three distinct concerns:

  1. Hygiene refactor — fix bugs 1–6, drop string-hacking, replace wildcard_match with fnmatch, use CONST_STORAGE_PROVIDER_TYPE enums as keys.
  2. Elevate PathHelper to canonical path-dispatcher — make it the single source of truth for "path → provider enum" and wire the facade + pydata readers through it (removes the duplicated startswith("s3://") ladders).
  3. Suffix-aware transform inference — data.parquet.gz.gpg → auto-construct Pipeline(GPG, Gzip) → feed decoded stream to parquet reader. This is the bridge to mountainash dataframe ingestion.

  Each is useful alone. Done together they form a coherent story ("path_helpers becomes the routing layer between paths, backends, transforms, and readers"), but that's a large single spec.

  Question 1 of the brainstorm: Which scope do you want to tackle first?

  - A. All three as one spec (biggest blast radius but tells the whole story)
  - B. Concerns 1 + 2 only — clean up and wire PathHelper into the facade & pydata dispatch; leave transform inference for a follow-up spec
  - C. Concern 3 only — the "encrypted parquet → dataframe" user story — assuming current path_helpers is "good enough" and only touching what's needed for suffix-driven pipelines
  - D. Concern 1 only — pure hygiene pass, no new integration

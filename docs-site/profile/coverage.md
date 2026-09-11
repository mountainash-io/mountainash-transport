# Coverage Report — mountainash-transport

**Generated:** 2026-06-02  
**Source hash:** 65bc90f901403a1454ba5d3d608660a95d64b163  
**Mode:** initial-profile

## Summary

| Metric | Count |
|--------|-------|
| Modules discovered | 25 |
| Modules profiled | 25 |
| Missing profiles | 0 |
| Stale profiles | 0 |
| Orphan profiles | 0 |
| Facets written | 4 |

## Coverage Gaps

### 1. Missing backend implementations (HIGH)

Settings classes exist for 9 providers, but only 3 have backend implementations in `storage_backends/`:

| Provider | Settings class | Backend exists? |
|----------|---------------|-----------------|
| Local | LocalSettings | Yes |
| S3 (aws/express/r2/minio/b2) | S3Settings | Yes |
| HTTP | HTTPSettings | Yes |
| GCS | GCSSettings | **No** |
| Azure (blob/files) | AzureStorageSettings | **No** |
| SSH/SFTP | SSHSettings | **No** |
| FTP/FTPS | FTPSettings | **No** |
| SMB | SMBSettings | **No** |
| GitHub | GitHubRepoSettings | **No** |

Six providers have full settings + adapters but no `storage_backends/` implementation. This is likely intentional (phased rollout), but undocumented.

### 2. HTTP backend limited protocol coverage (MEDIUM)

HTTPStorageBackend implements only 3 of 8 protocols:
- Read, Write, Metadata
- **Missing:** List, Delete, Copy, Directory, Connection

### 3. Dead/placeholder code in settings.utils (LOW)

- `settings/utils/connection.py` — 100% commented out
- `settings/utils/validation.py` — 100% commented out
- `settings/utils/security.py` — ~80% commented out, only `ConnectionValidator` active

### 4. Overspecified settings.exceptions hierarchy (LOW)

17 exception classes defined; unclear how many are actually raised in practice. May confuse users and maintainers.

### 5. No examples/ directory (LOW)

No usage examples in the source tree. Tests serve as implicit examples but are not structured for documentation purposes.

### 6. settings.templates possibly obsolete (LOW)

Legacy URL templates module — Phase 4 notes say most templates were inlined as `ParameterSpec.template`. May be removable.

## Open Questions

1. What is the roadmap for the 6 missing backend implementations (GCS, Azure, SSH, FTP, SMB, GitHub)?
2. Should placeholder schemes (dbfs, hdfs, spark, gdrive, dropbox, onedrive, sharepoint) be documented or removed from the scheme registry?
3. S3 `read_to_stream` wraps bytes in BytesIO rather than streaming from S3 body — is this a known limitation?
4. HTTP `read_to_stream` similarly buffers entire response — acceptable for the HTTP use case?

## Module-Level Confidence

| Module | Confidence | Reason |
|--------|-----------|--------|
| All profiled modules | high | Clear exports, tests, and evidence |
| settings.utils | high | Clearly placeholder/dead code |
| settings.templates | medium | Unclear if still referenced at runtime |

## Next Recommended Documentation Work

1. **User guide:** Quickstart with `read_bytes()` and `StorageFacade` examples
2. **Provider reference:** Per-provider configuration with auth modes and required fields
3. **Architecture guide:** Protocol -> backend -> facade dispatch diagram
4. **Backend status matrix:** Which providers are fully implemented vs settings-only
5. **Transform guide:** Pipeline ordering, Gzip/GPG setup, suffix inference

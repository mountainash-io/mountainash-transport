# Chapter plan: mountainash-transport

Status: proposed — awaiting user approval. No chapter prose or site outlines exist yet.
Implements: `docs-site/editorial-brief.md` (confirmed 2026-10-29).
Source: `8f0a49e` (develop). Profile: `docs-site/profile` (src `8a979e2`, unchanged in `src/`). Graph: `docs-site/learning-graph/learning-graph.json` (124 concepts, IDs 101–224, validated). Book-wide `cis_max` = 357 (Byte Storage Endpoints).

Replacement book: fresh structure. Nothing is reused from the old 9-chapter book (brief: no reuse).

## Shape

Three parts follow the depth progression concepts → use → internals:
- **Concepts** (chapters 1–2) give everyone the shared vocabulary and the ecosystem boundary.
- **Using the package** (chapters 3–12) is the user path. Each chapter opens with use and ends with internals sections where they exist.
- **Internals** (chapters 13–15) is for architecture readers and maintainers.

Readers can enter at the level they need: each chapter states its assumed starting point and links to shared explanations instead of repeating them.

## Audience coverage

- **users**: chapters 1, 3–12 are the core path; chapter 14's support matrix is linked from 6 and 7.
- **backend-architecture**: chapters 2, 4–6, 11 (connection layer), 13 and 14. All concepts in the facet's six concept groups have primary sections: protocols and support matrix (13, 14), registry dispatch (4, 13), S3 flavours (5, 11, 14), connection layer (6, 11), read plumbing (9, 14), HTTP engine (12).
- **maintainers**: internals sections in 3, 9, 10 and 12, plus chapters 13–15. Lifecycle invariants (6, 11), conformance (15), extras and base install (3, 15), stream internals (9, 10, 14), engine policy and redaction (12), scheme identification (4, 8) and the settings pipeline (5).
- **broader-hype**: no chapter (brief). Feeds the home and About pages only, from "same call, any store" (6, 7, 14), location guard rails (8) and bastion access (11). Every claim is backed by an example or test; the tunnel claim carries the HTTPS limitation.
- **Ecosystem context**: chapter 2 (brief decision), linked at each boundary: credentials (5, 11, 12), configuration (5), formats and access modes (9).

## Chapters

### Part I — Concepts

#### 01-what-transport-does — What transport does

- **Audiences:** users, all
- **Why a chapter:** Defines the problem transport solves and the vocabulary every later page uses.
- **Prerequisite chapters:** none
- **Sources:** `README.md`; `AGENTS.md`; `docs/read-access-modes.md`
- **Visual:** Mermaid: path → scheme → backend → endpoint flow.
- **Sections:**
  - Storage endpoints and paths — 101 Byte Storage Endpoints, 102 URL Schemes and Paths, 103 Object Storage Model
  - Bytes and streams — 104 Binary Streams
  - What transport owns — 105 Transport Responsibility Boundary

#### 02-mountainash-ecosystem — Transport in the Mountainash ecosystem

- **Audiences:** users, maintainers, backend-architecture, broader-hype
- **Why a chapter:** Ecosystem context (brief decision): what transport owns versus delegates, with a dependency map; later pages link here at each boundary.
- **Prerequisite chapters:** 01-what-transport-does
- **Sources:** `pyproject.toml (extras, dependencies)`; `mountainash-central 01.principles/{mountainash-files,mountainash-auth-client,mountainash-settings}`; `mountainash-central 01.principles/mountainash-transport/a.architecture/format-agnostic-storage.md`; `mountainash-files and mountainash pyproject.toml (transport dependency)`; `src/mountainash_transport/connections/auth_strategy.py`
- **Visual:** Mermaid: package dependency map (mountainash, files → transport → auth-client, settings).
- **Sections:**
  - The Mountainash packages — 106 Mountainash Ecosystem
  - Credentials come from auth-client — 107 mountainash-auth-client, 111 Credential Delegation
  - Configuration comes from settings — 108 mountainash-settings
  - Formats belong to consumers — 109 mountainash-files, 110 mountainash Relations Readers, 112 Format-Agnostic Storage

### Part II — Using the package

#### 03-installation — Installation and the package surface

- **Audiences:** users, maintainers
- **Why a chapter:** Base install versus extras and the error base class are prerequisites for every usage page.
- **Prerequisite chapters:** 01-what-transport-does
- **Sources:** `pyproject.toml`; `src/mountainash_transport/__init__.py`; `src/mountainash_transport/_core/extras.py`; `src/mountainash_transport/_core/exceptions.py`; `tests/test_slim_install.py`
- **Sections:**
  - Base install and extras — 113 Base Install, 114 Optional Extras, 116 Lazy Package Root
  - Errors — 218 TransportError Hierarchy, 115 MissingExtraError

#### 04-paths-and-schemes — Paths and scheme dispatch

- **Audiences:** users, backend-architecture
- **Why a chapter:** Scheme dispatch is the entry point for every operation (high CIS); path utilities are used directly.
- **Prerequisite chapters:** 01-what-transport-does
- **Sources:** `src/mountainash_transport/_schemes.py`; `src/mountainash_transport/storage/path_helpers/`; `src/mountainash_transport/storage/registry/backend_detection.py`; `examples/path_dispatch`
- **Visual:** Mermaid: scheme dispatch flow.
- **Sections:**
  - How a path picks a backend — 118 SchemeSpec Registry, 119 Scheme Dispatch
  - StoragePath — 120 StoragePath, 121 S3 Bucket and Key Parsing, 122 Suffix Chains

#### 05-storage-profiles — Storage profiles and credentials

- **Audiences:** users, maintainers, backend-architecture
- **Why a chapter:** Profiles (CIS 114) gate the facade, connections and location policy; settings-only providers and their error are stated here.
- **Prerequisite chapters:** 01-what-transport-does, 02-mountainash-ecosystem, 03-installation
- **Sources:** `src/mountainash_transport/settings/`; `src/mountainash_transport/settings/storage/profiles/`; `src/mountainash_transport/settings/storage/registry.py`; `src/mountainash_transport/settings/storage/loader.py`; `examples/storage_profiles`; `examples/named_profiles`; `examples/auth_compatibility`
- **Visual:** Mermaid: profile + auth profile → emission → SDK kwargs.
- **Sections:**
  - What a storage profile is — 129 Storage Profiles, 131 Provider Types, 130 Auth Profiles
  - Provider profiles — 136 S3 Flavours, 137 SFTP Profile, 138 HTTP Profile
  - Specs, the registry and settings-only providers — 132 StorageProfileSpec, 133 Implemented Flag, 134 Settings-Only Providers, 220 BackendNotImplementedError, 135 STORAGE_REGISTRY
  - Named profiles — 141 Named Profiles, 142 resolve_storage
  - How profiles become SDK arguments — 140 Profile Emission

#### 06-storage-facade — Opening storage with StorageFacade

- **Audiences:** users, backend-architecture
- **Why a chapter:** Construction, capability checks and lifecycle are separate from the operations themselves.
- **Prerequisite chapters:** 01-what-transport-does, 03-installation, 04-paths-and-schemes, 05-storage-profiles
- **Sources:** `src/mountainash_transport/storage/facade/facade.py`; `src/mountainash_transport/_core/protocols.py`; `examples/capability_checks`; `examples/local_files`
- **Visual:** Mermaid: facade lifecycle state diagram.
- **Sections:**
  - Creating a facade — 143 StorageFacade, 144 from_path, 145 for_local, 117 storage() Factory
  - Capabilities and supports() — 196 Storage Protocols, 147 Capability Checks
  - Opening and closing — 179 ConnectionProtocol, 146 Facade Lifecycle

#### 07-file-operations — File operations

- **Audiences:** users
- **Why a chapter:** The operation reference users return to; one section per operation family.
- **Prerequisite chapters:** 01-what-transport-does, 06-storage-facade
- **Sources:** `src/mountainash_transport/storage/facade/facade.py`; `src/mountainash_transport/_core/dataclasses/storage_entry.py`; `examples/local_files`; `examples/directories`; `examples/streaming`
- **Sections:**
  - Reading and writing — 148 Read and Write, 149 Streaming Reads and Writes
  - Listing and metadata — 150 Enumerate and List, 151 StorageEntry, 152 Metadata Queries
  - Deleting, directories and parent creation — 153 Delete, 154 Directory Operations, 155 Parent Creation
  - Copying — 156 Copy Within a Backend

#### 08-location-policy — Location policy

- **Audiences:** users, maintainers, broader-hype
- **Why a chapter:** A guard-rail feature with its own semantics and footguns (empty allow-list).
- **Prerequisite chapters:** 01-what-transport-does, 03-installation, 05-storage-profiles, 06-storage-facade
- **Sources:** `src/mountainash_transport/location.py`; `README.md (Location policy)`; `tests/test_location.py`; `tests/storage/facade/test_facade_location_policy.py`
- **Visual:** Mermaid: policy decision flow (local root / remote allow-list / profile host).
- **Sections:**
  - LocationPolicy — 123 LocationPolicy, 127 LocationNotAllowed
  - Confining local paths — 124 Local Root Confinement, 139 Local Profile
  - Allowing remote hosts — 125 Remote Allow-List, 126 Profile-Granted Hosts
  - Policy on the facade — 158 Location Policy on the Facade, 128 Credential Redaction

#### 09-read-access-modes — Read access modes

- **Audiences:** users, maintainers
- **Why a chapter:** Access-mode choice is the consumer's decision (format-agnostic boundary) and needs its own explanation.
- **Prerequisite chapters:** 02-mountainash-ecosystem, 03-installation, 07-file-operations
- **Sources:** `docs/read-access-modes.md`; `src/mountainash_transport/_core/ranged_io.py`; `src/mountainash_transport/_core/stream_errors.py`; `src/mountainash_transport/_core/transforms/util.py (materialize)`; `examples/streaming`
- **Visual:** Table: modes versus memory, seekability and backend support.
- **Sections:**
  - Choosing an access mode — 159 Read Access Modes, 160 Sequential Access, 161 Random Access, 162 Buffered Access
  - Range tuning — 163 RangePolicy
  - Errors and ownership — 166 Deferred Read Errors, 167 Stream Ownership, 168 materialize

#### 10-stream-transforms — Stream transforms and cross-backend copy

- **Audiences:** users, maintainers
- **Why a chapter:** Transforms compose with reads, writes and copies; copy_between needs them.
- **Prerequisite chapters:** 01-what-transport-does, 03-installation, 04-paths-and-schemes, 07-file-operations, 09-read-access-modes
- **Sources:** `src/mountainash_transport/_core/transforms/`; `src/mountainash_transport/storage/path_helpers/suffixes.py`; `src/mountainash_transport/storage/facade/cross_backend.py`; `examples/gzip_pipeline`; `examples/suffix_inference`; `examples/cross_backend_copy`
- **Visual:** Mermaid: transform direction on read versus write.
- **Sections:**
  - Transforms and pipelines — 170 Stream Transform, 171 Transform Pipeline, 172 Transform Direction
  - Gzip and GPG — 173 Gzip Transform, 174 GPG Transform
  - Suffix inference — 175 Suffix Inference
  - Limits and ownership — 176 Transforms and Random Access, 178 Transform Layer Ownership
  - Copying between backends — 157 copy_between
  - Internals: the streaming gzip encoder — 177 Streaming Gzip Encoder

#### 11-connections — Connections, SSH and tunnels

- **Audiences:** users, maintainers, backend-architecture
- **Why a chapter:** Direct connection use (SSH, SFTP, bastions) is a distinct user task and the connection layer is an architecture topic.
- **Prerequisite chapters:** 03-installation, 05-storage-profiles, 06-storage-facade
- **Sources:** `src/mountainash_transport/connections/`; `AGENTS.md (Connections)`; `tests/connections`
- **Visual:** Mermaid: leaf and decorator connection composition (SFTP over SSH; tunnel over SSH).
- **Sections:**
  - create_connection — 180 create_connection, 181 Target Families
  - Leaf connections — 182 Leaf Connections, 184 HTTPConnection, 185 S3Connection, 186 SSHConnection, 188 NullConnection
  - Decorator connections — 183 Decorator Connections, 187 SFTPConnection, 189 Bastion Tunnels
  - Connection errors — 190 Connection Errors

#### 12-http-engine — The HTTP request engine

- **Audiences:** users, maintainers
- **Why a chapter:** Usable on its own (examples/http_engine) and large enough to stand alone.
- **Prerequisite chapters:** 02-mountainash-ecosystem, 08-location-policy, 11-connections
- **Sources:** `src/mountainash_transport/_core/http/`; `src/mountainash_transport/connections/auth_strategy.py`; `examples/http_engine`; `tests/_core/http`
- **Sections:**
  - Making requests — 191 HTTP Request Engine, 193 HTTP Response Handling
  - Retries — 192 HTTP Retry Policy
  - Authentication strategies — 194 Refreshable Auth Strategy
  - Error redaction — 195 HTTP Error Redaction

### Part III — Internals

#### 13-architecture — Architecture: protocols and dispatch

- **Audiences:** backend-architecture, maintainers
- **Why a chapter:** The protocol contracts and registry dispatch behind every usage chapter.
- **Prerequisite chapters:** 05-storage-profiles, 06-storage-facade, 07-file-operations, 09-read-access-modes
- **Sources:** `src/mountainash_transport/storage/protocols/`; `src/mountainash_transport/storage/registry/`; `src/mountainash_transport/storage/backends/__init__.py`; `mountainash-central 01.principles/mountainash-transport (a, b, c)`
- **Visual:** Mermaid: protocols → mixins → backend class → registry → facade.
- **Sections:**
  - Protocols as contracts — 197 Runtime-Checkable Protocols
  - The storage protocols — 198 Read Protocol, 199 Write Protocol, 200 Enumerate Protocol, 201 Delete Protocol, 202 Metadata Protocol, 203 Copy Protocol, 204 Directory Protocol, 205 Ranged Read Protocol
  - The backend registry — 206 Backend Registry, 207 register_storage_backend, 208 Backend Lookup
  - How the facade dispatches — 209 Facade Dispatch
  - Composing backends from mixins — 210 Mixin Composition

#### 14-backends — Backends

- **Audiences:** backend-architecture, maintainers, users
- **Why a chapter:** One home for the support matrix and per-backend behaviour and divergence.
- **Prerequisite chapters:** 03-installation, 04-paths-and-schemes, 05-storage-profiles, 06-storage-facade, 08-location-policy, 09-read-access-modes, 11-connections, 12-http-engine, 13-architecture
- **Sources:** `src/mountainash_transport/storage/backends/`; `src/mountainash_transport/_core/ranged_io.py`; `src/mountainash_transport/_core/sequential_io.py`; `tests/storage/protocols/test_backend_conformance.py`; `tests/storage/backends`
- **Visual:** Table: support matrix including RangedRead.
- **Sections:**
  - Support matrix — 211 Support Matrix
  - Local — 212 Local Backend, 169 Native Local Handles
  - S3 family — 213 S3 Backend, 214 S3 Family Registration
  - SFTP — 215 SFTP Backend
  - HTTP — 216 HTTP Backend
  - Read plumbing — 164 RangedReader, 165 Sequential Stream Adapters
  - Where backends differ — 217 Backend Divergences, 219 Backend Error Mapping

#### 15-maintaining — Maintaining and extending transport

- **Audiences:** maintainers, backend-architecture
- **Why a chapter:** Contributor workflow: the tests that guard the invariants and the steps to add a backend.
- **Prerequisite chapters:** 03-installation, 05-storage-profiles, 11-connections, 13-architecture, 14-backends
- **Sources:** `tests/storage/protocols/`; `tests/test_slim_install.py`; `CONTRIBUTING.md`; `TESTING.md`; `AGENTS.md`
- **Sections:**
  - Tests that guard the contracts — 221 Conformance Tests, 222 Registry Completeness Tests, 223 Slim Install Test
  - Adding a backend — 224 Adding a Backend

## Reference pages and appendices

- **Support matrix and known limits** (reference page, brief decision). It collects the matrix including RangedRead, the settings-only providers and the documented limits:
  - empty `allowed_remote` set allows any host;
  - HTTPS targets fail through tunnels;
  - `rmdir` divergence;
  - SFTP write buffering;
  - S3 single-request copy;
  - `MissingExtraError` scope;
  - gzip writer closing the caller's stream.
  Each limit is also an inline admonition at its point of use. No backlog IDs appear.
- **FAQ** and **Glossary** (confirmed) link to the primary section of each concept.
- **References:** verified external links (boto3, paramiko, httpx, fsspec, python-gnupg) and the sibling packages.
- Home and About pages are written after the chapters (step 8).

## Elaboration guidance (internal, CIS)

CIS is normalised against the book-wide maximum. It guides depth within the planned structure; it does not set the structure.

| Concept | ID | CIS | CIS/max | Chapter |
|---|---|---|---|---|
| Byte Storage Endpoints | 101 | 357 | 1.00 | 01-what-transport-does |
| Mountainash Ecosystem | 106 | 161 | 0.45 | 02-mountainash-ecosystem |
| mountainash-settings | 108 | 115 | 0.32 | 02-mountainash-ecosystem |
| Binary Streams | 104 | 114 | 0.32 | 01-what-transport-does |
| Storage Profiles | 129 | 114 | 0.32 | 05-storage-profiles |
| URL Schemes and Paths | 102 | 96 | 0.27 | 01-what-transport-does |
| SchemeSpec Registry | 118 | 76 | 0.21 | 04-paths-and-schemes |
| Scheme Dispatch | 119 | 75 | 0.21 | 04-paths-and-schemes |
| StorageFacade | 143 | 73 | 0.20 | 06-storage-facade |
| Transport Responsibility Boundary | 105 | 71 | 0.20 | 01-what-transport-does |
| Storage Protocols | 196 | 67 | 0.19 | 06-storage-facade |
| Read and Write | 148 | 32 | 0.09 | 07-file-operations |
| ConnectionProtocol | 179 | 27 | 0.08 | 06-storage-facade |
| Leaf Connections | 182 | 22 | 0.06 | 11-connections |
| Streaming Reads and Writes | 149 | 20 | 0.06 | 07-file-operations |
| mountainash-files | 109 | 18 | 0.05 | 02-mountainash-ecosystem |
| mountainash Relations Readers | 110 | 18 | 0.05 | 02-mountainash-ecosystem |
| Format-Agnostic Storage | 112 | 17 | 0.05 | 02-mountainash-ecosystem |
| Read Access Modes | 159 | 16 | 0.04 | 09-read-access-modes |
| StorageProfileSpec | 132 | 14 | 0.04 | 05-storage-profiles |

Concepts at or above 0.05 of the maximum get full explanations with examples. Concepts below it get concise sections or definitions, linked from the glossary.

## Open questions

- None blocking. Chapter 14 is the longest internals chapter (seven sections); splitting "Read plumbing" into its own chapter is an alternative if it runs long.

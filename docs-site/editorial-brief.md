# Editorial brief: mountainash-transport

Status: confirmed — 2026-10-29 by the user, who confirmed the complete brief as recorded below (scope, all four facets, early ecosystem chapter, limitations policy, no reuse, FAQ + glossary, Mermaid, old course pages dropped).
Source revision: `8f0a49e98e2b899827ff0c2f8c7114beb71a5d8c` (develop, merge of PR #130); clean working tree. Profile source revision `8a979e2`; `src/` is unchanged between the two.
Profile basis: `docs-site/profile/manifest.json` (36 modules, 7 ignored markers, validated). Facets: `users`, `maintainers`, `backend-architecture`, `broader-hype`. Coverage: `docs-site/profile/coverage.md`.
Operation: replacement rebuild from scratch. The existing 9-chapter book (baseline `65bc90f`, pre-rename `mountainash_utils_files`) remains the accepted book until the replacement is accepted.

## Purpose and reader outcomes

Package documentation for `mountainash-transport`: one file API across local disk, the S3 family (AWS, R2, MinIO, B2, S3 Express), SFTP and HTTP(S). The path's scheme selects the backend, storage profiles describe stores, auth profiles from `mountainash-auth-client` supply credentials, and stream transforms (gzip, GPG) compose on reads, writes and copies.

Readers should be able to:

- explain where transport sits in the Mountainash ecosystem: what it owns (connections, byte movement, stream transforms, location policy) and what it delegates (credentials and OAuth lifecycle to `mountainash-auth-client`, configuration resolution to `mountainash-settings`, formats and access-mode choice to consumers such as `mountainash-files` and `mountainash`);
- install the right extras, read, write, stream, list, copy and delete across supported backends, and check capabilities before calling;
- configure stores with storage profiles and named-profile resolution (`resolve_storage`), and keep credentials separate;
- choose read access modes (sequential, random, buffered) and apply transforms correctly in each direction;
- constrain where code may reach with `LocationPolicy`;
- use connections directly: SSH, SFTP, bastion tunnels and the HTTP request engine;
- extend or maintain the package: protocols, mixin-composed backends, registry dispatch, conformance tests and the base-install/extras boundary.

## Audience coverage

All four profile facets are served. They become reading paths through shared explanations, not one track or chapter per facet.

- **users** (core path). Covers the root API, `StorageFacade`, storage profiles and the loader, transforms, `copy_between`, location policy, the HTTP engine, connections and errors.
- **backend-architecture.** Covers the protocols and support matrix, registry dispatch, S3 flavours on one backend, the connection layer and decorators, and ranged and sequential read plumbing. This forms the internals depth of the same chapters plus an architecture part.
- **maintainers.** Covers lifecycle invariants, conformance testing, extras and base install, stream internals, HTTP engine policy and redaction, scheme identification and the settings pipeline. It is served by internals sections and a contributor-facing part. Private modules (`_stream_encoder`, `stream_errors`, `_schemes`) are explained there, not in user pages.
- **broader-hype.** Covers "same call, any store", location guard rails and bastion access. It feeds the home page and About page only, and every claim must be backed by a runnable example or test. It gets no chapter.

**Ecosystem context.** This is a first-class concern. It is explained once, early, and linked from wherever a boundary matters: credentials (`mountainash-auth-client`), configuration (`mountainash-settings`), formats and access-mode choice (`mountainash-files`, `mountainash` relations readers). Statements about sibling packages are limited to what their public principles and dependency declarations establish.

## Scope and exclusions

**In scope:**
- Every public capability in the profile.
- The backend support matrix, including RangedRead.
- The settings-only providers (GCS, Azure, FTP, SMB, GitHub), stated as profiles without backends that raise `BackendNotImplementedError`.
- Optional extras and the base install.
- Documented behavioural limits, where they affect correct use. The coverage report and backlog #37–#51 list them, for example:
  - empty `allowed_remote` set semantics;
  - HTTPS through tunnels;
  - `rmdir` divergence;
  - SFTP write buffering;
  - S3 single-request copy;
  - `MissingExtraError` scope.

**Excluded:**
- Unimplemented roadmap work (messaging family, async, new backends). A clearly labelled status note may mention it.
- The "15+ providers" claim in the ecosystem vision, which the source does not support.
- Internal backlog IDs and private repository links.
- Format handling (owned by consumers).
- OAuth flow internals (owned by auth-client).

**Prerequisites:** Python 3.12+, context managers and basic I/O streams. Cloud and SSH concepts are introduced where first needed.

## Depth and reading paths

Concepts, then package use, then internals. Chapter and section organisation is proposed fresh in the chapter plan. Users can stop after the use sections; architecture and maintainer readers continue into internals. Shared explanations (for example the protocol model and connection lifecycle) are written once and linked, not repeated. Each page states its assumed starting point.

## Register

Package documentation: self-describing pages with no course preamble, learning objectives or recap sections.

## Reuse

None. This is a rebuild from scratch. Old chapters, course description and learning graph are not reused as structure or prose. Facts come from the current source, profile, tests and examples.

## Appendices

- **FAQ:** included (decided 2026-10-29).
- **Glossary:** included (decided 2026-10-29).

Both link to the relevant chapter or section explanations.

## Visual policy

Mermaid first: architecture layering, dispatch flow, connection decorators, transform direction and the support matrix as a table. MicroSims only when interaction adds explanatory value; none are proposed initially. No quizzes in the Mountainash workflow.

## Decisions recorded 2026-10-29 (user answers)

- **Ecosystem context.** One early chapter covers what transport owns and what it delegates (auth-client credentials and OAuth lifecycle, settings resolution, files/mountainash formats and access-mode choice), with a Mermaid dependency map. Later pages link to it at each boundary.
- **Limitations.**
  - An admonition appears at the point of use in each relevant section.
  - One "Support matrix and known limits" reference page collects them.
  - No internal backlog IDs appear.
- **Old reader pages.** `course-description.md`, the learning-graph pages and `sims/` are dropped from the replacement site. The replacement consists of the chapters, home page, About page, FAQ, glossary and references. The canonical graph stays internal. The old pages leave with the old book on acceptance.
- **Appendices.** FAQ and glossary are both included and link to the relevant sections.
- **Branch.** `docs/textbook-rebuild` from `develop` `8f0a49e`, reviewed via PR.

## Approval and open questions

No open editorial questions. Confirmed 2026-10-29. The chapter plan requires separate approval before any prose.

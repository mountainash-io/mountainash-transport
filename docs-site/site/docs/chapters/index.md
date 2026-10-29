# Chapters


## Concepts

1. [What transport does](01-what-transport-does/index.md): The problem transport solves: one way to reach bytes on local disk, object stores, SFTP servers and HTTP endpoints.
2. [Transport in the Mountainash ecosystem](02-mountainash-ecosystem/index.md): How transport fits with auth-client, settings, files and mountainash, and which package owns what.

## Using the package

3. [Installation and the package surface](03-installation/index.md): Installing the base package and the extras each backend needs, and the errors you will see when one is missing.
4. [Paths and scheme dispatch](04-paths-and-schemes/index.md): How a path's scheme chooses a backend, and the helpers for building and splitting storage paths.
5. [Storage profiles and credentials](05-storage-profiles/index.md): Describing a store with a storage profile, supplying credentials separately, and loading named profiles.
6. [Opening storage with StorageFacade](06-storage-facade/index.md): Creating a StorageFacade, checking what a store supports, and opening and closing it.
7. [File operations](07-file-operations/index.md): Reading, writing, streaming, listing, inspecting, deleting and copying files.
8. [Location policy](08-location-policy/index.md): Limiting which local directories and remote hosts your code is allowed to reach.
9. [Read access modes](09-read-access-modes/index.md): Choosing sequential, random or buffered reads, and who owns the streams you get back.
10. [Stream transforms and cross-backend copy](10-stream-transforms/index.md): Compressing and encrypting streams on read, write and copy, including copies between different stores.
11. [Connections, SSH and tunnels](11-connections/index.md): Using connections directly: HTTP, S3, SSH, SFTP and SSH bastion tunnels.
12. [The HTTP request engine](12-http-engine/index.md): Making HTTP requests with retries, authentication and safe error messages.

## Internals

13. [Architecture: protocols and dispatch](13-architecture/index.md): The protocols, registry and dispatch that sit behind the facade.
14. [Backends](14-backends/index.md): What each backend supports, how it is built, and where backends behave differently.
15. [Maintaining and extending transport](15-maintaining/index.md): The tests that protect the package's contracts and the steps for adding a backend.

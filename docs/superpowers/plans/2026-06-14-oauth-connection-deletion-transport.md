# Transport OAuth Connection Deletion Implementation Plan (PR 2/3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete transport's theatrical, now-broken OAuth connection classes (they pass a *storage* profile's `__spec__` to auth-client's `OAuthFlow`, which since auth-client 26.6.1 reads OAuth coordinates off a `ProviderProfile` that storage specs do not have) and make `create_connection` raise a clear error for OAuth auth profiles.

**Architecture:** Transport's `connections/oauth1/` + `connections/oauth2/` packages are removed entirely. `create_connection` no longer special-cases OAuth auth profiles; instead it raises a new `UnsupportedAuthProfileError` pointing callers to auth-client's parameterised `OAuth2Connection`/`OAuth1Connection` + an `OAuth2ProviderProfile`/`OAuth1ProviderProfile` (the proper home for OAuth-server coordinates). No behavioural OAuth path is left in transport.

**Tech Stack:** Python 3.12, `mountainash-auth-client` (≥26.6.1, editable in the shared dev env), pytest.

**Scope boundary:** PR 2 of 3. PR 1 (auth-client ProviderProfile) is merged. PR 3 (wearables migration) is separate. This PR touches only `mountainash-utils-files` (transport).

**Why deletion, not rewiring:** transport's storage profiles carry storage-endpoint config, not OAuth-server URLs. There is nothing in a storage profile to populate a `ProviderProfile` from, so the OAuth connections cannot be rewired in transport — OAuth-authenticated access is an auth-client/wearables concern. This obsoletes BACKLOG **A3** (OAuth→emit cleanup) and **B3** (callback-server threading), which both assumed the connections stay. (Confirmed with the user: delete + raise.)

**Spec:** `mountainash-auth-client/docs/superpowers/specs/2026-06-13-oauth-provider-profile-design.md` (§ "Compatibility & version boundary", § "Scope & sequencing" step 2).

**Repo / branch:** `mountainash-utils-files`, branch `bugfix/delete-oauth-connections` (seed from `develop`; auth-client PR #8 already merged).

**Test runner:** the shared dev venv python:
```
PY=/home/nathanielramm/git/mountainash-ide/mountainash-dev-local/.venv/bin/python
```
Run tests with `$PY -m pytest …`; lint with `$PY -m ruff check …`. The env has auth-client editable-installed at the live source, so it already reflects 26.6.1 (verified: `OAuthFlow.__init__` takes `provider`, and `mountainash_auth_client.providers` imports). No pyproject pin to bump — the auth-client dependency line is commented out (`pyproject.toml:32`); CI supplies auth-client via its configured test env.

**Baseline (verified before planning):** `tests/connections/oauth2/test_connection.py` + `tests/connections/oauth1/test_connection.py` → **12 failed, 5 passed** (already RED — the live auth-client flow signature changed under them). This deletion turns the suite green by removing the dead surface.

---

## File Structure

**Deleted (whole directories):**
- `src/mountainash_transport/connections/oauth1/` (`__init__.py`, `connection.py`, `__pycache__/`)
- `src/mountainash_transport/connections/oauth2/` (`__init__.py`, `connection.py`, `__pycache__/`)
- `tests/connections/oauth1/` (`__init__.py`, `test_connection.py`)
- `tests/connections/oauth2/` (`__init__.py`, `test_connection.py`)

**Modified:**
- `src/mountainash_transport/connections/errors.py` — add `UnsupportedAuthProfileError`.
- `src/mountainash_transport/connections/__init__.py` — drop OAuth connection imports + `__all__` entries; replace the OAuth dispatch in `create_connection` with a raise.
- `tests/connections/test_factory.py` — replace `test_oauth2_returns_oauth2_connection` with a raises-test.
- `tests/connections/test_protocol_shapes.py` — remove the two OAuth conformance tests + their now-unused fake spec classes.
- `docs/BACKLOG.md` — mark A3 + B3 obsoleted by this deletion.

**Unchanged (deliberate):** the `OAuthFlow`/`OAuth1Flow` re-exports in `connections/__init__.py` stay — they are auth-client's flows (still valid public API), and dropping them is a separate, wider cleanup not required by this PR.

---

## Task 1: Add `UnsupportedAuthProfileError`

**Files:**
- Modify: `src/mountainash_transport/connections/errors.py`
- Test: `tests/connections/test_errors.py` (create if absent)

- [ ] **Step 1: Write the failing test**

Create/append `tests/connections/test_errors.py`:

```python
"""Connection error hierarchy."""
from __future__ import annotations

import pytest

from mountainash_transport.connections.errors import (
    TransportConnectionError,
    UnsupportedAuthProfileError,
)


def test_unsupported_auth_profile_is_transport_connection_error():
    assert issubclass(UnsupportedAuthProfileError, TransportConnectionError)


def test_unsupported_auth_profile_message_names_the_profile():
    err = UnsupportedAuthProfileError("OAuth2AuthCodeAuthProfile")
    assert "OAuth2AuthCodeAuthProfile" in str(err)
    # Points callers at the right home for OAuth-authenticated connections.
    assert "auth-client" in str(err) or "ProviderProfile" in str(err)


def test_unsupported_auth_profile_raisable():
    with pytest.raises(TransportConnectionError):
        raise UnsupportedAuthProfileError("X")
```

- [ ] **Step 2: Run to verify it fails**

Run: `$PY -m pytest tests/connections/test_errors.py -q`
Expected: ImportError — `UnsupportedAuthProfileError` doesn't exist yet.

- [ ] **Step 3: Implement**

Append to `src/mountainash_transport/connections/errors.py`:

```python
class UnsupportedAuthProfileError(TransportConnectionError):
    """The connection factory was given an auth profile it does not handle.

    Transport's ``create_connection`` builds storage connections; OAuth
    *authorization* flows are not a transport concern. Construct
    ``mountainash_auth_client``'s ``OAuth2Connection``/``OAuth1Connection`` with
    an ``OAuth2ProviderProfile``/``OAuth1ProviderProfile`` (which carry the
    OAuth-server coordinates) instead.
    """

    def __init__(self, profile_name: str) -> None:
        self.profile_name = profile_name
        super().__init__(
            f"{profile_name} is not supported by transport's create_connection; "
            "use mountainash-auth-client's OAuth2Connection/OAuth1Connection with "
            "an OAuth2ProviderProfile/OAuth1ProviderProfile instead."
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `$PY -m pytest tests/connections/test_errors.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/mountainash_transport/connections/errors.py tests/connections/test_errors.py
git commit -m "feat: add UnsupportedAuthProfileError for the connection factory

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Strip OAuth from `create_connection` and delete the source packages

**Files:**
- Modify: `src/mountainash_transport/connections/__init__.py`
- Delete: `src/mountainash_transport/connections/oauth1/`, `src/mountainash_transport/connections/oauth2/`
- Test: `tests/connections/test_factory.py`

- [ ] **Step 1: Update the factory test first**

In `tests/connections/test_factory.py`, REPLACE the method `test_oauth2_returns_oauth2_connection` (it imports `from mountainash_transport.connections.oauth2.connection import OAuth2Connection` and asserts the factory returns it) with:

```python
    def test_oauth2_auth_raises_unsupported(self):
        from mountainash_auth_client import OAuth2AuthCodeAuthProfile
        from mountainash_transport.connections.errors import UnsupportedAuthProfileError
        auth = OAuth2AuthCodeAuthProfile(
            CLIENT_ID="cid",
            CLIENT_SECRET="csec",
            SCOPE="read",
            SETTINGS_SOURCE_SECRETS_PROVIDER="test",
        )
        with pytest.raises(UnsupportedAuthProfileError):
            create_connection(FakeHTTPProfile(), auth_profile=auth)
```

(`pytest` is already imported at the top of the file.)

- [ ] **Step 2: Run to verify it fails**

Run: `$PY -m pytest tests/connections/test_factory.py -q`
Expected: FAIL — the factory still constructs an `OAuth2Connection` (no raise). It may fail with an error from inside `OAuth2Connection`/`OAuthFlow` rather than a clean assertion; either way it is not `UnsupportedAuthProfileError`, so the test is red.

- [ ] **Step 3: Edit `connections/__init__.py`**

(a) Remove these two imports (the leaf-connection import block, ~lines 27-28):
```python
from .oauth2.connection import OAuth2Connection
from .oauth1.connection import OAuth1Connection
```

(b) Replace the OAuth dispatch in `create_connection` — the block currently reading:
```python
    from mountainash_auth_client import OAuth2AuthProfile, OAuth2AuthCodeAuthProfile

    if isinstance(auth_profile, (OAuth2AuthProfile, OAuth2AuthCodeAuthProfile)):
        return OAuth2Connection(profile, auth_profile, auto_authorize=auto_authorize)

    try:
        from mountainash_auth_client.schemas.oauth1 import OAuth1AuthProfile
        if isinstance(auth_profile, OAuth1AuthProfile):
            return OAuth1Connection(profile, auth_profile, auto_authorize=auto_authorize)
    except ImportError:
        pass
```
with:
```python
    from mountainash_auth_client import (
        OAuth1AuthProfile,
        OAuth2AuthCodeAuthProfile,
        OAuth2AuthProfile,
    )
    from .errors import UnsupportedAuthProfileError

    if isinstance(
        auth_profile,
        (OAuth2AuthProfile, OAuth2AuthCodeAuthProfile, OAuth1AuthProfile),
    ):
        # OAuth authorization flows are not a transport concern — they need a
        # ProviderProfile (OAuth-server coordinates), which storage profiles
        # don't carry. See auth-client's parameterised OAuth connections.
        raise UnsupportedAuthProfileError(type(auth_profile).__name__)
```
(Note: `auto_authorize` is still a `create_connection` parameter; it is now unused for OAuth since OAuth raises. Leave the parameter — it is part of the public signature and harmless. If ruff flags it as unused it is a *parameter*, not a local, so it will not.)

(c) Remove `"OAuth2Connection"` and `"OAuth1Connection"` from the `__all__` list at the bottom of the file. Leave `"OAuthFlow"` and `"OAuth1Flow"` in place (auth-client re-exports — still valid). Also remove the now-dead `from .oauth1.connection import OAuth1Connection` / `OAuth2Connection` names from the "New connection classes" comment block if listed.

- [ ] **Step 4: Delete the source packages**

```bash
git rm -r src/mountainash_transport/connections/oauth1 src/mountainash_transport/connections/oauth2
```

- [ ] **Step 5: Verify the factory test + import health**

Run: `$PY -m pytest tests/connections/test_factory.py -q`
Expected: PASS.

Run: `$PY -c "import mountainash_transport.connections as c; print('import OK'); print('OAuth2Connection' not in c.__all__)"`
Expected: prints `import OK` then `True`.

- [ ] **Step 6: Commit**

```bash
git add src/mountainash_transport/connections/__init__.py tests/connections/test_factory.py
git rm -r --cached src/mountainash_transport/connections/oauth1 src/mountainash_transport/connections/oauth2 2>/dev/null || true
git commit -m "refactor: remove transport OAuth connections; factory raises on OAuth auth

The OAuth2/OAuth1 connection classes passed a storage profile's __spec__ to
auth-client's OAuthFlow, which since 26.6.1 reads coordinates off a
ProviderProfile storage specs don't have. They were theatrical and broke at
that boundary. create_connection now raises UnsupportedAuthProfileError for
OAuth auth profiles; OAuth-authenticated access belongs to auth-client's
ProviderProfile-based connections.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Delete the OAuth test packages and fix protocol-shapes

**Files:**
- Delete: `tests/connections/oauth1/`, `tests/connections/oauth2/`
- Modify: `tests/connections/test_protocol_shapes.py`

- [ ] **Step 1: Delete the OAuth connection test packages**

```bash
git rm -r tests/connections/oauth1 tests/connections/oauth2
```

- [ ] **Step 2: Remove the OAuth conformance tests from `test_protocol_shapes.py`**

In `tests/connections/test_protocol_shapes.py`:
- DELETE the methods `test_oauth2_connection_conforms` and `test_oauth1_connection_conforms` (they import the deleted `connections.oauth2.connection`/`connections.oauth1.connection`).
- DELETE the now-unused module-level classes `FakeOAuth2Spec` and `FakeOAuth1Spec`.
- Keep `FakeProfile` ONLY if still referenced after the deletions; if it becomes unused, delete it too. (Verify with `grep -n "FakeProfile\|FakeOAuth" tests/connections/test_protocol_shapes.py` after editing — there should be no dangling references.)

The remaining conformance tests (`test_http_connection_conforms`, `test_null_connection_conforms`, `test_s3_connection_conforms`, `test_object_does_not_conform`) stay unchanged.

- [ ] **Step 3: Verify the connections test suite is green**

Run: `$PY -m pytest tests/connections/ -q`
Expected: PASS (no collection errors from deleted modules; no remaining import of `connections.oauth1`/`connections.oauth2`).

Run: `grep -rn "connections.oauth1\|connections.oauth2\|OAuth2Connection\|OAuth1Connection" tests src`
Expected: NO matches (every reference removed).

- [ ] **Step 4: Commit**

```bash
git add tests/connections/test_protocol_shapes.py
git commit -m "test: drop OAuth connection conformance tests (classes deleted)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Obsolete the backlog items, full-suite gate, and PR

**Files:**
- Modify: `docs/BACKLOG.md`

- [ ] **Step 1: Mark A3 + B3 obsoleted**

In `docs/BACKLOG.md`, prepend a one-line obsolete marker to item **A3** ("Migrate the OAuth connections off the `to_handler_kwargs` shim") and item **B3** ("callback-server threading"):

For A3, add immediately under its heading:
```markdown
> ⛔ **Obsoleted (2026-06-14):** the transport OAuth connections were deleted in PR 2 of the ProviderProfile cycle — there is nothing left to migrate. See `docs/superpowers/plans/2026-06-14-oauth-connection-deletion-transport.md`.
```

For B3, add immediately under its heading:
```markdown
> ⛔ **Obsoleted (2026-06-14):** transport no longer owns OAuth connections — callback-server threading is auth-client's concern (`resolve_access_token(..., callback_server=...)`). See the PR-2 deletion plan.
```

(Do NOT delete the items — keep them with the obsolete marker so the history is legible. If the triage table at the bottom lists A3/B3 under "High value, scoped", strike them there too or note them obsoleted.)

- [ ] **Step 2: Full suite + lint**

Run: `$PY -m pytest tests/ -q`
Expected: PASS. Record the summary line. If anything OUTSIDE the connections area fails, STOP — investigate before proceeding (do not mask).

Run: `$PY -m ruff check src/mountainash_transport/connections tests/connections`
Expected: clean (fix any lint in the files this PR touched; ignore pre-existing lint elsewhere).

- [ ] **Step 3: Commit the backlog update**

```bash
git add docs/BACKLOG.md
git commit -m "docs: obsolete BACKLOG A3/B3 (transport OAuth connections deleted)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Fresh-eyes Codex review (pre-PR)**

Run a fresh-eyes review of the branch diff via `codex:codex-rescue`. Focus: "Review the transport OAuth-connection deletion (PR 2/3 of the ProviderProfile cycle) — confirm no dangling import of the deleted `connections.oauth1`/`connections.oauth2` remains anywhere in src/tests, that `create_connection`'s OAuth raise covers OAuth1+OAuth2+OAuth2AuthCode, that no non-OAuth dispatch path regressed, and that the public `connections` API surface change (dropped OAuth2Connection/OAuth1Connection) doesn't break other in-repo importers. This IS implemented; review the code." Address any DO-NOT-SHIP findings.

- [ ] **Step 5: Open the PR (targets `develop`)**

```bash
git push -u origin bugfix/delete-oauth-connections
gh pr create --base develop \
  --title "refactor: delete transport's unwired OAuth connections (PR 2/3)" \
  --body "$(cat <<'EOF'
## Summary
PR 2 of the OAuth ProviderProfile cycle. Deletes transport's `connections/oauth1` + `connections/oauth2` packages — they passed a *storage* profile's `__spec__` to auth-client's `OAuthFlow`, which since 26.6.1 reads coordinates off a `ProviderProfile` that storage specs don't carry. They were theatrical and went RED at that boundary.

- `create_connection` now raises `UnsupportedAuthProfileError` for OAuth auth profiles (OAuth2 / OAuth2AuthCode / OAuth1), pointing callers to auth-client's parameterised `OAuth2Connection`/`OAuth1Connection` + a `ProviderProfile`.
- Removed the dead connection classes, their tests, and the OAuth conformance/factory tests that depended on them.
- `OAuthFlow`/`OAuth1Flow` re-exports (auth-client's flows) are unchanged.

## Backlog
Obsoletes **A3** (OAuth→emit cleanup) and **B3** (callback-server threading) — both assumed these connections stay; they're gone. Marked obsolete in `docs/BACKLOG.md`.

## Verification
Full suite green; the previously-RED OAuth connection tests are removed with their classes. Codex fresh-eyes reviewed.

Spec: auth-client `docs/superpowers/specs/2026-06-13-oauth-provider-profile-design.md` (§ version boundary, step 2).

## Next
PR 3 (wearables) migrates descriptors → `ProviderProfile` and wires token persistence.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review (controller checklist — completed during planning)

- **Spec coverage:** spec PR-2 = "delete (or stub) transport's OAuth connection classes so nothing is left on the broken `OAuthFlow(spec)` input; refresh env." Covered: classes + tests deleted (Tasks 2–3); factory no longer calls the broken path (Task 2); env already on 26.6.1 via editable install, no pin to change (documented). The "raise" choice (vs silent fall-through) was user-confirmed.
- **Reference integrity:** every in-repo referent of `OAuth2Connection`/`OAuth1Connection`/`connections.oauth{1,2}` enumerated from grep — `connections/__init__.py` (Task 2), `test_factory.py` (Task 2), `test_protocol_shapes.py` (Task 3), the deleted packages themselves. The top-level public `__init__.py` does NOT export them (verified). Task 3 Step 3 greps to prove zero dangling references.
- **Placeholder scan:** none — every step has concrete code/commands + expected output.
- **No test-integrity shortcut:** the deleted tests are removed because the *classes they test* are deleted (root cause), not to dodge failures; the factory test is rewritten to assert the new contract, not deleted.
```

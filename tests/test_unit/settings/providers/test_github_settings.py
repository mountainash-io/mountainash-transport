"""Tests for GitHubRepoSettings — GitHub repository (read-only)."""

from __future__ import annotations

import pytest

from mountainash_auth_client import JWTAuth, NoAuth, OAuth2Auth, TokenAuth
from pydantic import SecretStr

from mountainash_utils_files.constants import CONST_STORAGE_PROVIDER_TYPE
from mountainash_utils_files.settings.providers.github_settings import (
    GITHUB_REPO_SPEC,
    GitHubRepoSettings,
)


def _make(*, auth=None, **extra):
    kwargs = {
        "PROVIDER_TYPE": CONST_STORAGE_PROVIDER_TYPE.GITHUB,
        "ORG": "mountainash-io",
        "REPO": "mountainash",
        "auth": auth if auth is not None else NoAuth(),
    }
    kwargs.update(extra)
    return GitHubRepoSettings(**kwargs)


@pytest.mark.unit
class TestGitHubConstruction:
    def test_minimal_required_fields(self):
        s = _make()
        assert s.ORG == "mountainash-io"
        assert s.REPO == "mountainash"

    def test_default_base_url(self):
        s = _make()
        assert s.BASE_URL == "https://api.github.com"

    def test_timeout_field_explicitly_declared(self):
        """Regression: TIMEOUT was previously undefined in the legacy class."""
        assert "TIMEOUT" in GitHubRepoSettings.model_fields
        s = _make()
        # Default value should be set to 30.0 by the descriptor.
        assert s.TIMEOUT == 30.0


@pytest.mark.unit
class TestGitHubScopeCut:
    """Legacy fields removed by scope-cut to repository-read-only mode."""

    @pytest.mark.parametrize(
        "field",
        [
            "STORAGE_TYPE",
            "PACKAGE_TYPE",
            "PACKAGE_VISIBILITY",
            "BRANCH",
            "API_VERSION",
        ],
    )
    def test_scope_cut_field_absent(self, field):
        assert field not in GitHubRepoSettings.model_fields


@pytest.mark.unit
class TestGitHubAuthPaths:
    def test_token_auth_pat_surfaces_token(self):
        s = _make(auth=TokenAuth(token=SecretStr("ghp_abc123")))
        kw = s.to_handler_kwargs()
        assert kw["token"] == "ghp_abc123"

    def test_jwt_auth_surfaces_token(self):
        s = _make(auth=JWTAuth(token=SecretStr("jwt.body.sig")))
        kw = s.to_handler_kwargs()
        assert kw["token"] == "jwt.body.sig"

    def test_oauth2_auth_surfaces_token(self):
        s = _make(
            auth=OAuth2Auth(
                token=SecretStr("gho_xyz"),
                client_id="my-app",
            ),
        )
        kw = s.to_handler_kwargs()
        assert kw["token"] == "gho_xyz"

    def test_noauth_produces_no_token(self):
        s = _make(auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert "token" not in kw


@pytest.mark.unit
class TestGitHubFsspecKwargs:
    def test_kwargs_shape_minimal(self):
        s = _make(auth=NoAuth())
        kw = s.to_handler_kwargs()
        assert kw["org"] == "mountainash-io"
        assert kw["repo"] == "mountainash"
        assert kw["base_url"] == "https://api.github.com"
        assert kw["timeout"] == 30.0

    def test_ref_sha_when_set(self):
        s = _make(REF="main")
        kw = s.to_handler_kwargs()
        assert kw["sha"] == "main"

    def test_enterprise_base_url_forwarded(self):
        s = _make(BASE_URL="https://github.example.corp/api/v3")
        kw = s.to_handler_kwargs()
        assert kw["base_url"] == "https://github.example.corp/api/v3"


@pytest.mark.unit
class TestGitHubDescriptor:
    def test_descriptor_name(self):
        assert GITHUB_REPO_SPEC.name == "github_repo"

    def test_descriptor_is_read_only(self):
        """GithubFileSystem is read-only — scope-cut enforces this."""
        assert GITHUB_REPO_SPEC.read_only is True

    def test_descriptor_sdk_package(self):
        assert GITHUB_REPO_SPEC.sdk_package == "fsspec"

    def test_descriptor_handler_class(self):
        assert (
            GITHUB_REPO_SPEC.handler_class == "GitHubRepoStorageBackend"
        )

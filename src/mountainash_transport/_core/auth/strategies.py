"""Auth strategies — inject credentials into SDK client kwargs."""
from __future__ import annotations

import typing as t

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthStrategy(Protocol):
    """Inject auth credentials into SDK client kwargs.

    Returns a NEW dict — does not mutate the input.
    """

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]: ...


class NoAuthStrategy:
    """Passthrough — no credentials injected."""

    def apply(self, kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
        return {**kwargs}

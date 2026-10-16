"""Preserve caller errors when a transfer invokes and wraps caller-owned I/O."""
from __future__ import annotations

import typing as t
from types import TracebackType


class _CallerInput:
    """Delegate input capabilities unchanged; retain errors only for this transfer."""

    def __init__(self, source: t.BinaryIO) -> None:
        self._source = source
        self._errors: list[tuple[BaseException, TracebackType | None]] = []

    def __getattr__(self, name: str) -> t.Any:
        try:
            value = getattr(self._source, name)
        except BaseException as exc:
            self._errors.append((exc, exc.__traceback__))
            raise
        if not callable(value):
            return value

        def invoke(*args: t.Any, **kwargs: t.Any) -> t.Any:
            try:
                return value(*args, **kwargs)
            except BaseException as exc:
                self._errors.append((exc, exc.__traceback__))
                raise
        return invoke

    def original_in(self, error: BaseException) -> tuple[BaseException, TracebackType | None] | None:
        pending = [error]
        seen: set[int] = set()
        while pending:
            current = pending.pop()
            if id(current) in seen:
                continue
            seen.add(id(current))
            for original, traceback in self._errors:
                if current is original:
                    return original, traceback
            if current.__context__ is not None:
                pending.append(current.__context__)
            if current.__cause__ is not None:
                pending.append(current.__cause__)
        return None

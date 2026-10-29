"""Shipped source must not contain modules whose body is entirely commented out."""
from __future__ import annotations

from pathlib import Path

import mountainash_transport

SRC = Path(mountainash_transport.__file__).parent


def test_no_comment_only_modules():
    dead = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*.py")
        if p.stat().st_size and all(
            not line.strip() or line.lstrip().startswith("#")
            for line in p.read_text().splitlines()
        )
    ]
    assert dead == []

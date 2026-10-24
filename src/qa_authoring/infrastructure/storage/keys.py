from __future__ import annotations

import hashlib


def object_key(prefix: str, content: bytes) -> str:
    """Content-addressed object key: the same bytes always land on the same key."""
    folder = f"{prefix.rstrip('/')}/" if prefix else ""
    return f"{folder}{hashlib.sha256(content).hexdigest()}"

from __future__ import annotations


class PromptTemplateNotFoundError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(f"prompt template {key!r} not found")
        self.key = key

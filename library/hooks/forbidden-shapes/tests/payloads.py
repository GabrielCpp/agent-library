"""The tool calls a harness sends the guard, as the tests of every rule build them."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def write(path: Path | str, content: str) -> dict[str, Any]:
    return {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": content}}


def edit(path: Path | str, old: str, new: str) -> dict[str, Any]:
    return {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(path), "old_string": old, "new_string": new},
    }

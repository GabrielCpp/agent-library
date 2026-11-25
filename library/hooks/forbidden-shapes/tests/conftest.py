"""What every rule's tests share: a folder that looks like a checkout."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A directory that looks like a checkout, so root detection and doc naming have a target."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "README.md").write_text("# a project\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    return tmp_path

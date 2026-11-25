"""What the private-name commit check refuses, and what it lets through."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_private_names.py"
NAME = "zorblax"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(tmp_path, "add", "seed.txt")
    git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")
    return tmp_path


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def stage(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    git(repo, "add", rel)


def run(
    repo: Path, *args: str, names: str | None = NAME, **env: str
) -> subprocess.CompletedProcess[str]:
    environ = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_COMMIT_")}
    environ.pop("STABLEMATE_PRIVATE_NAMES", None)
    if names is not None:
        environ["STABLEMATE_PRIVATE_NAMES"] = names
    environ.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=repo, env=environ, capture_output=True, text=True,
    )


def test_a_clean_staged_file_passes(repo: Path):
    stage(repo, "a.txt", "acme only\n")
    assert run(repo).returncode == 0


def test_a_name_in_staged_content_is_refused_with_its_line(repo: Path):
    stage(repo, "a.txt", "fine\nworks for Zorblax\n")
    result = run(repo)
    assert result.returncode == 1
    assert "a.txt:2:" in result.stderr


def test_a_name_in_a_staged_path_is_refused(repo: Path):
    stage(repo, f"docs/{NAME}.md", "clean\n")
    result = run(repo)
    assert result.returncode == 1
    assert "(in the path)" in result.stderr


def test_the_index_is_scanned_not_the_working_tree(repo: Path):
    stage(repo, "a.txt", "clean\n")
    (repo / "a.txt").write_text(f"{NAME}\n", encoding="utf-8")
    assert run(repo).returncode == 0


def test_an_unstaged_file_is_not_scanned(repo: Path):
    (repo / "loose.txt").write_text(f"{NAME}\n", encoding="utf-8")
    assert run(repo).returncode == 0


def test_pathspecs_limit_the_sweep(repo: Path):
    stage(repo, "a.txt", "clean\n")
    stage(repo, "b.txt", f"{NAME}\n")
    assert run(repo, "a.txt").returncode == 0
    assert run(repo, "b.txt").returncode == 1


def test_a_binary_file_is_skipped(repo: Path):
    path = repo / "blob.bin"
    path.write_bytes(b"\0" + NAME.encode())
    git(repo, "add", "blob.bin")
    assert run(repo).returncode == 0


def test_no_names_configured_passes(repo: Path):
    stage(repo, "a.txt", f"{NAME}\n")
    assert run(repo, names=None).returncode == 0


def test_names_fall_back_to_the_git_dir_file(repo: Path):
    (repo / ".git" / "private-names").write_text(f"# list\n{NAME}\n", encoding="utf-8")
    stage(repo, "a.txt", f"{NAME}\n")
    assert run(repo, names=None).returncode == 1


def test_a_name_in_the_inline_message_is_refused(repo: Path):
    stage(repo, "a.txt", "clean\n")
    result = run(repo, AGENT_COMMIT_COMMAND=f'git commit -m "fix: help {NAME}"')
    assert result.returncode == 1
    assert "commit command:1:" in result.stderr


def test_a_name_in_a_message_file_is_refused(repo: Path, tmp_path: Path):
    stage(repo, "a.txt", "clean\n")
    (repo / "MSG").write_text(f"fix: thing\n\nfor {NAME}\n", encoding="utf-8")
    result = run(
        repo,
        AGENT_COMMIT_COMMAND="git commit -F MSG",
        AGENT_COMMIT_CWD=str(repo),
    )
    assert result.returncode == 1
    assert "MSG:3:" in result.stderr


def test_a_clean_message_passes(repo: Path):
    stage(repo, "a.txt", "clean\n")
    assert run(repo, AGENT_COMMIT_COMMAND='git commit -m "fix: thing"').returncode == 0

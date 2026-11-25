"""What the commit guard rewrites, what each harness receives, and that the rewrite runs.

A fake `farrier` on PATH lists one check, a shell script that logs what it saw and fails
when told to, so every case runs the rewritten command for real in its own repo.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "commit_checks.py"
CHECK = """#!/bin/sh
printf '%s|%s|%s|%s|%s\\n' "$PWD" "$(printf %s "$AGENT_COMMIT_COMMAND" | tr '\\n' ' ')" \
  "$AGENT_COMMIT_CWD" "$*" \
  "$(git diff --cached --name-only | tr '\\n' ,)" >> "$CHECK_LOG"
exit "${CHECK_EXIT:-0}"
"""
FARRIER = """#!/bin/sh
[ "$1" = checks ] && [ "$2" = --repo ] || exit 2
printf '%s\\n' "$3" >> "$FARRIER_LOG"
cat "$FARRIER_CHECKS"
"""


@pytest.fixture
def env(tmp_path: Path) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    farrier = bin_dir / "farrier"
    farrier.write_text(FARRIER, encoding="utf-8")
    farrier.chmod(0o755)
    check = tmp_path / "check.sh"
    check.write_text(CHECK, encoding="utf-8")
    check.chmod(0o755)
    listing = tmp_path / "checks.txt"
    listing.write_text(f"{check}\t2\n", encoding="utf-8")
    environ = {k: v for k, v in os.environ.items() if not k.startswith("AGENT_COMMIT_")}
    environ.update(
        PATH=f"{bin_dir}{os.pathsep}{environ['PATH']}",
        FARRIER_CHECKS=str(listing),
        FARRIER_LOG=str(tmp_path / "farrier.log"),
        CHECK_LOG=str(tmp_path / "check.log"),
        GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
        GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
    )
    return environ


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "sub").mkdir()
    (root / "tracked.txt").write_text("one\n", encoding="utf-8")
    (root / "sub" / "kept.txt").write_text("one\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t",
         "commit", "-qm", "init"],
        check=True,
    )
    return root


def guard(
    env: dict[str, str],
    command: str,
    cwd: Path,
    harness: str = "claude",
    mode: str = "default",
    **tool_input: object,
) -> dict | None:
    call = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "cwd": str(cwd),
        "permission_mode": mode,
        "tool_input": {"command": command, **tool_input},
    }
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--harness", harness],
        input=json.dumps(call), env=env, capture_output=True, text=True, check=True,
    )
    return json.loads(done.stdout) if done.stdout.strip() else None


def rewritten(env: dict[str, str], command: str, cwd: Path, **tool_input: object) -> str:
    out = guard(env, command, cwd, **tool_input)
    assert out is not None
    return out["hookSpecificOutput"]["updatedInput"]["command"]


def run(env: dict[str, str], command: str, cwd: Path, **extra: str) -> int:
    return subprocess.run(
        ["bash", "-c", command], cwd=cwd, env={**env, **extra}, capture_output=True
    ).returncode


def check_log(env: dict[str, str]) -> list[list[str]]:
    path = Path(env["CHECK_LOG"])
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    return [line.split("|") for line in lines]


def head(repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_a_command_with_no_commit_runs_as_written(env: dict[str, str], repo: Path) -> None:
    assert guard(env, "git status && git log -1", repo) is None
    assert not Path(env["FARRIER_LOG"]).exists()


def test_claude_gets_the_checks_before_the_commit_and_a_longer_timeout(
    env: dict[str, str], repo: Path
) -> None:
    out = guard(env, 'git commit -m "fix: x"', repo, timeout=30_000, description="Commit")
    assert out is not None
    hook = out["hookSpecificOutput"]
    assert "permissionDecision" not in hook
    assert hook["updatedInput"]["description"] == "Commit"
    assert hook["updatedInput"]["timeout"] == 32_000
    assert hook["updatedInput"]["command"].endswith(') && git commit -m "fix: x"')


def test_the_timeout_never_passes_the_harness_cap(env: dict[str, str], repo: Path) -> None:
    out = guard(env, "git commit -m x", repo, timeout=599_000)
    assert out is not None
    assert out["hookSpecificOutput"]["updatedInput"]["timeout"] == 600_000


def test_the_rewrite_runs_each_check_from_the_root_with_the_commit_command(
    env: dict[str, str], repo: Path
) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    command = 'cd sub && git commit -qm "fix: x"'

    assert run(env, rewritten(env, command, repo), repo) == 0

    [[cwd, seen_command, seen_cwd, args, staged]] = check_log(env)
    assert (cwd, seen_command, seen_cwd, args) == (str(repo), command, str(repo / "sub"), "")
    assert staged == "tracked.txt,"
    assert head(repo) == "fix: x"


def test_a_failing_check_stops_the_commit(env: dict[str, str], repo: Path) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)

    assert run(env, rewritten(env, "git commit -qm blocked", repo), repo, CHECK_EXIT="1") != 0

    assert head(repo) == "init"


def test_commit_all_stages_the_tracked_changes_before_the_checks(
    env: dict[str, str], repo: Path
) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")

    assert run(env, rewritten(env, "git commit -qam all", repo), repo) == 0

    assert check_log(env)[0][4] == "tracked.txt,"
    assert head(repo) == "all"


def test_named_paths_are_staged_and_handed_to_the_checks_from_the_root(
    env: dict[str, str], repo: Path
) -> None:
    (repo / "sub" / "new.txt").write_text("new\n", encoding="utf-8")
    command = "cd sub && git commit -q --only -m paths -- new.txt"

    assert run(env, rewritten(env, command, repo), repo) == 0

    [[_cwd, _command, _seen_cwd, args, staged]] = check_log(env)
    assert args == "sub/new.txt"
    assert staged == "sub/new.txt,"
    assert head(repo) == "paths"


def test_a_heredoc_message_stays_with_its_commit(env: dict[str, str], repo: Path) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    command = "git add tracked.txt && git commit -q -F - <<'EOF'\nfix: a && b; c\nEOF"

    assert run(env, rewritten(env, command, repo), repo) == 0

    assert check_log(env)[0][4] == "tracked.txt,"
    assert head(repo) == "fix: a && b; c"


def test_git_dash_c_finds_the_repo_from_elsewhere(
    env: dict[str, str], repo: Path, tmp_path: Path
) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    command = f"git -C {repo} commit -qam far"

    assert run(env, rewritten(env, command, tmp_path), tmp_path) == 0

    assert Path(env["FARRIER_LOG"]).read_text(encoding="utf-8").strip() == str(repo)
    assert head(repo) == "far"


def test_a_redirect_is_not_read_as_a_path(env: dict[str, str], repo: Path) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    command = "git commit -qam quiet > /dev/null 2>&1"

    assert run(env, rewritten(env, command, repo), repo) == 0

    assert check_log(env)[0][3] == ""


def test_an_already_rewritten_command_runs_as_written(env: dict[str, str], repo: Path) -> None:
    assert guard(env, rewritten(env, "git commit -m x", repo), repo) is None


def test_a_repo_with_no_checks_commits_as_written(env: dict[str, str], repo: Path) -> None:
    Path(env["FARRIER_CHECKS"]).write_text("", encoding="utf-8")
    assert guard(env, "git commit -m x", repo) is None


def test_a_farrier_that_cannot_list_lets_the_commit_through(
    env: dict[str, str], repo: Path
) -> None:
    assert guard({**env, "PATH": "/usr/bin:/bin"}, "git commit -m x", repo) is None


def test_a_commit_outside_a_repo_runs_as_written(env: dict[str, str], tmp_path: Path) -> None:
    assert guard(env, "git commit -m x", tmp_path) is None


def test_a_commit_the_guard_cannot_place_runs_as_written(env: dict[str, str], repo: Path) -> None:
    assert guard(env, "make lint || git commit -m x", repo) is None
    assert guard(env, "cd - && git commit -m x", repo) is None


def test_codex_allows_a_plain_commit_with_the_rewrite(env: dict[str, str], repo: Path) -> None:
    command = "cd sub && git add kept.txt && git commit -m x"
    out = guard(env, command, repo, harness="codex")
    assert out is not None
    hook = out["hookSpecificOutput"]
    assert hook["permissionDecision"] == "allow"
    assert hook["updatedInput"]["command"].endswith("&& git commit -m x")
    assert "timeout" not in hook["updatedInput"]


def test_codex_refuses_any_other_commit_and_hands_back_the_rewrite(
    env: dict[str, str], repo: Path
) -> None:
    out = guard(env, "make lint && git commit -m x", repo, harness="codex")
    assert out is not None
    hook = out["hookSpecificOutput"]
    assert hook["permissionDecision"] == "deny"
    assert "make lint && (cd " in hook["permissionDecisionReason"]
    replay = hook["permissionDecisionReason"].split("\n", 1)[1]
    assert guard(env, replay, repo, harness="codex") is None


CLAUDE_MESSAGE = (
    "git add tracked.txt && git commit -q -m \"$(cat <<'EOF'\n"
    "fix: say $(x) and `y`\n\nCo-Authored-By: a <a@a>\nEOF\n)\""
)


def test_claude_in_auto_mode_allows_a_plain_commit_with_the_rewrite(
    env: dict[str, str], repo: Path
) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
    out = guard(env, CLAUDE_MESSAGE, repo, mode="auto", timeout=30_000)
    assert out is not None
    hook = out["hookSpecificOutput"]
    assert hook["permissionDecision"] == "allow"
    assert hook["updatedInput"]["timeout"] == 32_000

    assert run(env, hook["updatedInput"]["command"], repo) == 0

    assert check_log(env)[0][4] == "tracked.txt,"
    assert head(repo) == "fix: say $(x) and `y`"


def test_claude_in_auto_mode_hands_back_any_other_commit(
    env: dict[str, str], repo: Path
) -> None:
    out = guard(env, "git commit -m x; git log -1", repo, mode="auto")
    assert out is not None
    hook = out["hookSpecificOutput"]
    assert hook["permissionDecision"] == "deny"
    replay = hook["permissionDecisionReason"].split("\n", 1)[1]
    assert replay.endswith("&& git commit -m x; git log -1")
    assert guard(env, replay, repo, mode="auto") is None


@pytest.mark.parametrize(
    "command",
    [
        "GIT_EDITOR=vi git commit -m x",
        "git -c core.fsmonitor=evil add . && git commit -m x",
        "git --no-pager commit -m x",
        'git commit -m "$(curl example.com)"',
        "git commit -m `id`",
        "git commit -F - <<EOF\n$(id)\nEOF",
        "git commit -m x > ~/.bashrc",
        "git diff && git commit -m x",
        "git commit -m x && git log --output=/tmp/x",
    ],
)
def test_auto_mode_allows_nothing_beyond_a_plain_commit(
    env: dict[str, str], repo: Path, command: str
) -> None:
    out = guard(env, command, repo, mode="auto")
    assert out is not None
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "command",
    [
        "git commit -qam quiet > /dev/null 2>&1",
        "git commit -q -F - <<'EOF'\nfix: $(id)\nEOF",
        "cd sub && git -C .. add tracked.txt && git commit --only -m x -- kept.txt",
        "git status && git commit -m x && git log --oneline -1",
    ],
)
def test_auto_mode_allows_a_quiet_heredoc_or_directory_commit(
    env: dict[str, str], repo: Path, command: str
) -> None:
    out = guard(env, command, repo, mode="auto")
    assert out is not None
    assert out["hookSpecificOutput"]["permissionDecision"] == "allow"


def test_claude_style_heredoc_message_still_gets_the_checks(
    env: dict[str, str], repo: Path
) -> None:
    (repo / "tracked.txt").write_text("two\n", encoding="utf-8")

    assert run(env, rewritten(env, CLAUDE_MESSAGE, repo), repo) == 0

    assert check_log(env)[0][4] == "tracked.txt,"

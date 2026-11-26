"""What the timeout guard lets through, what it learns, and the timeout it fills in.

Every case runs the script as the harness does, with its cache in its own `tmp_path`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import shlex
import shutil

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "require_timeout.py"
parse_json: Callable[[str], object] = json.loads
Done = subprocess.CompletedProcess[str]


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    return tmp_path / "cache" / "require-timeout.json"


def run(cache: Path, command: str | None, timeout: int | None = None, cwd: str = "/repo",
        background: bool = False, mode: str = "default", harness: str | None = None) -> Done:
    tool_input: dict[str, object] = {}
    if command is not None:
        tool_input["command"] = command
    if timeout is not None:
        tool_input["timeout"] = timeout
    if background:
        tool_input["run_in_background"] = True
    call: dict[str, object] = {"tool_name": "Bash", "tool_input": tool_input, "cwd": cwd, "permission_mode": mode}
    environ = dict(os.environ, REQUIRE_TIMEOUT_CACHE=str(cache))
    flags = ["--harness", harness] if harness else []
    return subprocess.run(
        [sys.executable, str(SCRIPT), *flags], input=json.dumps(call), capture_output=True,
        text=True, env=environ, check=False,
    )


def teach(cache: Path, command: str, timeout: int | None = None, cwd: str = "/repo",
          harness: str | None = None) -> None:
    done = run(cache, command, timeout=timeout, cwd=cwd, harness=harness)
    assert (done.returncode, done.stdout) == (0, ""), done.stderr


def output_of(done: Done) -> object:
    assert done.returncode == 0, done.stderr
    return parse_json(done.stdout)


def rewrite(command: str, timeout: int) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {"command": command, "timeout": timeout},
        }
    }


def wrapped(command: str, seconds: int) -> dict[str, object]:
    program = "timeout" if shutil.which("timeout") else "gtimeout"
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "updatedInput": {"command": f"{program} -k 5 {seconds} bash -c {shlex.quote(command)}"},
        }
    }


def refusal(done: Done) -> str:
    output = output_of(done)
    assert isinstance(output, dict)
    decision = output["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    reason = decision["permissionDecisionReason"]
    if "Bash 'timeout' parameter" in reason:
        return "parameter"
    assert "`timeout <seconds>`" in reason
    return "prefix"


def test_a_call_with_no_timeout_and_no_history_is_refused(cache: Path) -> None:
    assert refusal(run(cache, "pytest -q")) == "parameter"


def test_opencode_is_refused_with_the_timeout_parameter(cache: Path) -> None:
    assert refusal(run(cache, "pytest -q", harness="opencode")) == "parameter"


def test_opencode_gets_the_learned_timeout_parameter(cache: Path) -> None:
    teach(cache, "pytest -q", 45_000, harness="opencode")
    assert output_of(run(cache, "pytest -q", harness="opencode")) == rewrite("pytest -q", 45_000)


def test_a_harness_without_a_timeout_parameter_is_told_to_prefix_timeout(cache: Path) -> None:
    assert refusal(run(cache, "pytest -q", harness="copilot")) == "prefix"


def test_a_harness_without_a_timeout_parameter_gets_the_command_wrapped(cache: Path) -> None:
    command = "cd /repo && pytest -q 'a b'"
    teach(cache, command, 30_000)
    assert output_of(run(cache, command, harness="copilot")) == wrapped(command, 30)


def test_a_command_that_times_itself_passes_and_teaches_its_inner_command(cache: Path) -> None:
    teach(cache, "timeout -k 5 2m pytest -q", harness="pi")
    assert output_of(run(cache, "pytest -q", harness="pi")) == wrapped("pytest -q", 120)
    assert output_of(run(cache, "pytest -q")) == rewrite("pytest -q", 120_000)


def test_a_shell_wrapped_in_timeout_teaches_its_script(cache: Path) -> None:
    teach(cache, "timeout 45 bash -c 'cd /repo && make all'", harness="copilot")
    assert output_of(run(cache, "cd /repo && make all", harness="copilot")) == wrapped("cd /repo && make all", 45)


def test_a_timeout_covering_only_the_first_command_does_not_count(cache: Path) -> None:
    command = "timeout 60 make build && make test"
    assert refusal(run(cache, command, harness="pi")) == "prefix"


def test_a_timeout_parameter_is_ignored_where_the_harness_has_none(cache: Path) -> None:
    assert refusal(run(cache, "pytest -q", timeout=90_000, harness="copilot")) == "prefix"


def test_a_learned_timeout_wraps_in_whole_seconds(cache: Path) -> None:
    teach(cache, "pytest -q", 1_500)
    assert output_of(run(cache, "pytest -q", harness="pi")) == wrapped("pytest -q", 2)


def test_a_call_with_a_timeout_passes_untouched(cache: Path) -> None:
    done = run(cache, "pytest -q", timeout=30_000)
    assert (done.returncode, done.stdout, done.stderr) == (0, "", "")


def test_a_background_call_passes_and_teaches_nothing(cache: Path) -> None:
    assert run(cache, "pytest -q", timeout=30_000, background=True).returncode == 0
    assert run(cache, "pytest -q", background=True).returncode == 0
    assert refusal(run(cache, "pytest -q")) == "parameter"


def poll_refusal(done: Done) -> bool:
    output = output_of(done)
    assert isinstance(output, dict)
    decision = output["hookSpecificOutput"]
    return decision["permissionDecision"] == "deny" and "timeout <duration>" in decision["permissionDecisionReason"]


@pytest.mark.parametrize("command", [
    "until pgrep -f server; do sleep 5; done",
    "while ! curl -sf localhost:8080; do sleep 2; done && echo up",
    "cd /repo && while true; do make check; sleep 60; done",
    "pgrep -f vite",
    "for f in a b; do until test -e $f; do sleep 1; done; done",
])
def test_a_background_poll_without_a_timeout_is_refused(cache: Path, command: str) -> None:
    assert poll_refusal(run(cache, command, background=True))


@pytest.mark.parametrize("harness", [None, "copilot"])
def test_a_background_poll_is_refused_on_every_harness(cache: Path, harness: str | None) -> None:
    assert poll_refusal(run(cache, "until pgrep x; do sleep 1; done", background=True, harness=harness))


@pytest.mark.parametrize("command", [
    "timeout 3h bash -c 'until pgrep -f server; do sleep 5; done'",
    "timeout -k 10 90m sh -c 'while true; do make check; sleep 60; done'",
    "timeout 10m pgrep -f vite",
])
def test_a_background_poll_inside_a_timeout_passes(cache: Path, command: str) -> None:
    done = run(cache, command, background=True)
    assert (done.returncode, done.stdout) == (0, ""), done.stderr


@pytest.mark.parametrize("command", [
    "timeout 0 bash -c 'until pgrep x; do sleep 1; done'",
    "timeout 60 pgrep x; while true; do sleep 1; done",
])
def test_a_timeout_that_does_not_bound_the_poll_is_refused(cache: Path, command: str) -> None:
    assert poll_refusal(run(cache, command, background=True))


@pytest.mark.parametrize("command", [
    "pytest -q",
    "echo while until pgrep",
    "grep -rn 'while true' src",
    "git log --grep=until",
])
def test_a_background_call_that_only_names_a_poll_word_passes(cache: Path, command: str) -> None:
    done = run(cache, command, background=True)
    assert (done.returncode, done.stdout) == (0, ""), done.stderr


def test_the_same_command_gets_its_last_timeout(cache: Path) -> None:
    teach(cache, "pytest -q", 30_000)
    teach(cache, "pytest -q", 90_000)
    assert output_of(run(cache, "pytest   -q")) == rewrite("pytest   -q", 90_000)


def test_a_similar_command_gets_the_largest_recent_timeout_of_its_signature(cache: Path) -> None:
    teach(cache, "cd /repo && uv run pytest -q tests/a.py", 20_000)
    teach(cache, "cd /repo && uv run pytest -q tests/b.py", 60_000)
    teach(cache, "uv run pytest -q tests/c.py 2>&1 | tail -5", 10_000)
    assert output_of(run(cache, "cd /repo && uv run pytest -q tests/d.py")) == rewrite("cd /repo && uv run pytest -q tests/d.py", 60_000)


def test_the_exact_command_wins_over_its_signature(cache: Path) -> None:
    teach(cache, "pytest -q tests/slow", 300_000)
    teach(cache, "pytest -q tests/fast", 5_000)
    assert output_of(run(cache, "pytest -q tests/fast")) == rewrite("pytest -q tests/fast", 5_000)
    assert output_of(run(cache, "pytest -q tests/other")) == rewrite("pytest -q tests/other", 300_000)


def test_a_different_program_is_not_similar(cache: Path) -> None:
    teach(cache, "pytest -q", 30_000)
    assert refusal(run(cache, "npm test")) == "parameter"


def test_history_does_not_cross_working_directories(cache: Path) -> None:
    teach(cache, "pytest -q", 30_000, cwd="/one")
    assert refusal(run(cache, "pytest -q", cwd="/two")) == "parameter"


def test_only_recent_timeouts_count_for_a_signature(cache: Path) -> None:
    teach(cache, "pytest t/x0", 500_000)
    for index in range(1, 6):
        teach(cache, f"pytest t/x{index}", 10_000)
    assert output_of(run(cache, "pytest t/y")) == rewrite("pytest t/y", 10_000)


def test_a_learned_timeout_is_capped(cache: Path) -> None:
    teach(cache, "make all", 9_000_000)
    assert output_of(run(cache, "make all")) == rewrite("make all", 600_000)


def test_an_unparseable_command_still_matches_itself(cache: Path) -> None:
    command = "echo 'unterminated"
    teach(cache, command, 7_000)
    assert output_of(run(cache, command)) == rewrite(command, 7_000)


def test_a_heredoc_commit_learns_its_signature(cache: Path) -> None:
    first = "git commit -F - <<'EOF'\nfeat: one\nEOF"
    second = "git commit -F - <<'EOF'\nfeat: it's two\nEOF"
    teach(cache, first, 15_000)
    assert output_of(run(cache, first)) == rewrite(first, 15_000)
    assert output_of(run(cache, second)) == rewrite(second, 15_000)


def test_auto_mode_gets_the_same_rewrite(cache: Path) -> None:
    teach(cache, "pytest -q", 30_000)
    assert output_of(run(cache, "pytest -q", mode="auto")) == rewrite("pytest -q", 30_000)


def test_a_corrupt_cache_counts_as_empty_and_is_replaced(cache: Path) -> None:
    cache.parent.mkdir(parents=True)
    _ = cache.write_text("{not json", encoding="utf-8")
    assert refusal(run(cache, "pytest -q")) == "parameter"
    teach(cache, "pytest -q", 30_000)
    assert output_of(run(cache, "pytest -q")) == rewrite("pytest -q", 30_000)


def test_an_unwritable_cache_falls_back_to_the_default(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    _ = blocker.write_text("", encoding="utf-8")
    cache = blocker / "require-timeout.json"
    assert run(cache, "pytest -q", timeout=30_000).returncode == 0
    assert refusal(run(cache, "pytest -q")) == "parameter"


def test_input_that_is_not_a_call_passes(cache: Path) -> None:
    environ = dict(os.environ, REQUIRE_TIMEOUT_CACHE=str(cache))
    for text in ("", "not json", "[]"):
        done = subprocess.run(
            [sys.executable, str(SCRIPT)], input=text, capture_output=True, text=True,
            env=environ, check=False,
        )
        assert done.returncode == 0


def test_a_background_shell_script_that_polls_is_refused(cache: Path) -> None:
    assert poll_refusal(run(cache, "nohup bash -c 'while true; do sleep 1; done'", background=True))

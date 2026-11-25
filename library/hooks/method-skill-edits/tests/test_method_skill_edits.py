"""Which edits the method-skill hook stops, which it lets through, and when it stays quiet.

Every case runs the script as the harness does, with its state in its own `tmp_path`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "method_skill_edits.py"


def run(tmp_path: Path, tool_input: dict[str, object], tool: str = "Edit", session: str = "s1",
        transcript: list[dict[str, object]] | None = None) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in transcript or []) + "\n", encoding="utf-8")
    call = {"session_id": session, "tool_name": tool, "tool_input": tool_input, "transcript_path": str(path)}
    environ = dict(os.environ, METHOD_SKILL_EDITS_STATE_DIR=str(tmp_path / "state"))
    environ.pop("METHOD_SKILL_EDITS_OFF", None)
    return subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(call),
                          capture_output=True, text=True, env=environ, check=False)


def edit(path: str, old: str, new: str) -> dict[str, object]:
    return {"file_path": path, "old_string": old, "new_string": new}


def skill_load(name: str) -> dict[str, object]:
    block = {"type": "tool_use", "name": "Skill", "input": {"skill": name}}
    return {"type": "assistant", "message": {"content": [block]}}


@pytest.mark.parametrize(("new", "what"), [
    ("try:\n    go()\nexcept Exception:\n    pass", "a broad except"),
    ("try:\n    go()\nexcept:\n    pass", "a broad except"),
    ("for attempt in range(3):\n    retry(go)", "a retry"),
    ("time.sleep(0.5)\ngo()", "a sleep"),
    ("value = data.get('x') or fallback", "a fallback"),
    ("import thing  # noqa: F401", "a lint or type ignore"),
    ("value: int = load()  # ty: ignore[invalid-assignment]", "a lint or type ignore"),
])
def test_an_escape_hatch_in_source_names_root_cause(tmp_path: Path, new: str, what: str) -> None:
    done = run(tmp_path, edit("/repo/app/core.py", "go()", new))
    assert done.returncode == 2
    assert f"adds {what} to core.py" in done.stderr
    assert "Load root-cause" in done.stderr


def test_a_skipped_test_names_root_cause_in_a_test_file(tmp_path: Path) -> None:
    done = run(tmp_path, edit("/repo/tests/test_core.py", "def test_x():", "@pytest.mark.skip\ndef test_x():"))
    assert done.returncode == 2
    assert "adds a skipped test" in done.stderr


def test_a_sleep_in_a_test_file_passes(tmp_path: Path) -> None:
    done = run(tmp_path, edit("/repo/tests/test_core.py", "go()", "time.sleep(1)\ngo()"))
    assert (done.returncode, done.stderr) == (0, "")


@pytest.mark.parametrize(("path", "new", "what"), [
    ("/repo/cli.py", "parser.add_argument('--fast', action='store_true')", "a command-line flag"),
    ("/repo/settings.py", "LEVEL = os.environ.get('LEVEL', 'info')", "a setting read from the environment"),
    ("/repo/model.py", "Kind = Literal['a', 'b']", "a set of kinds"),
    ("/repo/main.go", "fast := flag.Bool(\"fast\", false, \"\")", "a command-line flag"),
])
def test_a_new_carrier_names_vet_proposal(tmp_path: Path, path: str, new: str, what: str) -> None:
    done = run(tmp_path, edit(path, "", new))
    assert done.returncode == 2
    assert f"adds {what}" in done.stderr
    assert "Load vet-proposal" in done.stderr


def test_a_row_added_to_a_plan_names_vet_proposal(tmp_path: Path) -> None:
    done = run(tmp_path, edit("/repo/docs/plans/rewrite.md", "- one\n", "- one\n- two\n"))
    assert done.returncode == 2
    assert "adds a row to a plan to rewrite.md" in done.stderr


def test_a_new_plan_file_passes(tmp_path: Path) -> None:
    done = run(tmp_path, {"file_path": str(tmp_path / "plans" / "new.md"), "content": "- one\n- two\n"}, tool="Write")
    assert (done.returncode, done.stderr) == (0, "")


def test_an_edit_that_keeps_the_count_passes(tmp_path: Path) -> None:
    old = "except Exception:\n    log('x')"
    done = run(tmp_path, edit("/repo/app/core.py", old, "except Exception:\n    log('y')"))
    assert (done.returncode, done.stderr) == (0, "")


def test_an_edit_that_removes_a_hatch_passes(tmp_path: Path) -> None:
    done = run(tmp_path, edit("/repo/app/core.py", "time.sleep(1)\ngo()", "go()"))
    assert (done.returncode, done.stderr) == (0, "")


def test_a_narrow_except_passes(tmp_path: Path) -> None:
    done = run(tmp_path, edit("/repo/app/core.py", "go()", "try:\n    go()\nexcept KeyError:\n    pass"))
    assert (done.returncode, done.stderr) == (0, "")


def test_the_second_hatch_in_a_session_passes(tmp_path: Path) -> None:
    first = run(tmp_path, edit("/repo/a.py", "", "time.sleep(1)"))
    second = run(tmp_path, edit("/repo/b.py", "", "time.sleep(2)"))
    assert first.returncode == 2
    assert (second.returncode, second.stderr) == (0, "")


def test_a_loaded_skill_lets_the_edit_through(tmp_path: Path) -> None:
    done = run(tmp_path, edit("/repo/a.py", "", "time.sleep(1)"), transcript=[skill_load("stablemate-root-cause")])
    assert (done.returncode, done.stderr) == (0, "")


def test_one_edit_with_both_moves_names_both_skills(tmp_path: Path) -> None:
    new = "LEVEL = os.getenv('LEVEL')\ntime.sleep(1)"
    done = run(tmp_path, edit("/repo/a.py", "", new))
    assert done.returncode == 2
    assert "Load root-cause" in done.stderr
    assert "Load vet-proposal" in done.stderr


def test_a_write_compares_against_the_file_on_disk(tmp_path: Path) -> None:
    target = tmp_path / "core.py"
    target.write_text("try:\n    go()\nexcept Exception:\n    pass\n", encoding="utf-8")
    done = run(tmp_path, {"file_path": str(target), "content": target.read_text() + "x = 1\n"}, tool="Write")
    assert (done.returncode, done.stderr) == (0, "")


def test_a_multi_edit_counts_every_part(tmp_path: Path) -> None:
    edits = [{"old_string": "a", "new_string": "b"}, {"old_string": "c", "new_string": "time.sleep(1)"}]
    done = run(tmp_path, {"file_path": "/repo/a.py", "edits": edits}, tool="MultiEdit")
    assert done.returncode == 2


def test_markdown_outside_a_plan_passes(tmp_path: Path) -> None:
    done = run(tmp_path, edit("/repo/README.md", "", "- retry with a fallback\n"))
    assert (done.returncode, done.stderr) == (0, "")


def test_the_switch_turns_the_hook_off(tmp_path: Path) -> None:
    call = {"session_id": "s", "tool_name": "Edit", "tool_input": edit("/r/a.py", "", "time.sleep(1)")}
    environ = dict(os.environ, METHOD_SKILL_EDITS_STATE_DIR=str(tmp_path), METHOD_SKILL_EDITS_OFF="1")
    done = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(call),
                          capture_output=True, text=True, env=environ, check=False)
    assert (done.returncode, done.stderr) == (0, "")


def test_unreadable_input_passes(tmp_path: Path) -> None:
    done = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True, check=False)
    assert done.returncode == 0

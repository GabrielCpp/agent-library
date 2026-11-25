"""Which closing replies the follow-up check holds open, and which turns it lets end.

Every case runs the script as the harness does, with a transcript in its own `tmp_path`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "follow_up_check.py"


def user(text: str) -> dict[str, object]:
    return {"type": "user", "message": {"role": "user", "content": text}}


def reply(text: str) -> dict[str, object]:
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}}


def skill_load(name: str) -> dict[str, object]:
    return {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Skill", "input": {"skill": name}}]}}


def run(tmp_path: Path, entries: list[dict[str, object]], **extra: object) -> subprocess.CompletedProcess[str]:
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    call = {"session_id": "s1", "transcript_path": str(path), "stop_hook_active": False, **extra}
    environ = dict(os.environ)
    environ.pop("FOLLOW_UP_CHECK_OFF", None)
    return subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(call),
                          capture_output=True, text=True, env=environ, check=False)


def held(done: subprocess.CompletedProcess[str]) -> str | None:
    if not done.stdout.strip():
        return None
    decision = json.loads(done.stdout)
    assert decision["decision"] == "block"
    return decision["reason"]


@pytest.mark.parametrize("closing", [
    "Want me to wire the hook into the config too?",
    "Shall I also add tests for the parser?",
    "Would you like me to draft the migration?",
    "I can also rewrite the README if that helps.",
])
def test_an_offer_holds_the_turn(tmp_path: Path, closing: str) -> None:
    reason = held(run(tmp_path, [user("fix it"), reply(f"Fixed the parser.\n\n{closing}")]))
    assert reason is not None
    assert closing[:30] in reason
    assert "Load whole-first" in reason


def test_a_follow_up_holds_the_turn(tmp_path: Path) -> None:
    reason = held(run(tmp_path, [user("fix it"), reply("Fixed.\n\nFollow-up: the cache could move to SQLite.")]))
    assert reason is not None


def test_a_follow_up_naming_a_release_file_holds_the_turn(tmp_path: Path) -> None:
    closing = "Follow-up: change `release.yml` so verify and publish check out the release tags instead of main."
    assert held(run(tmp_path, [user("release it"), reply(f"Done.\n\n{closing}")])) is not None


@pytest.mark.parametrize("status", [
    "Story 3 is past its build and in a follow-up dev turn.",
    "The run has moved to the next step of the gate.",
    "It left the timer out as a follow-up; the plan records why.",
])
def test_a_status_line_that_names_a_follow_up_passes(tmp_path: Path, status: str) -> None:
    assert held(run(tmp_path, [user("status?"), reply(f"Checked the run.\n\n{status}")])) is None


@pytest.mark.parametrize("closing", ["**Next steps:**\n- migrate acme", "- Follow-ups: farrier needs a fix."])
def test_a_proposal_heading_holds_the_turn(tmp_path: Path, closing: str) -> None:
    assert held(run(tmp_path, [user("fix it"), reply(f"Fixed.\n\n{closing}")])) is not None


def test_a_follow_up_passes_once_whole_first_loaded(tmp_path: Path) -> None:
    entries = [user("plan"), skill_load("whole-first"), reply("ok"), user("fix it"),
               reply("Fixed.\n\nFollow-up: the cache could move to SQLite.")]
    assert held(run(tmp_path, entries)) is None


def test_an_offer_holds_even_after_whole_first_loaded(tmp_path: Path) -> None:
    entries = [user("plan"), skill_load("whole-first"), reply("ok"), user("fix it"),
               reply("Fixed.\n\nWant me to add the cache too?")]
    assert held(run(tmp_path, entries)) is not None


def test_an_offer_that_waits_on_a_push_passes(tmp_path: Path) -> None:
    done = run(tmp_path, [user("fix it"), reply("Committed on the branch.\n\nShall I push it?")])
    assert held(done) is None


def test_a_reply_with_no_offer_passes(tmp_path: Path) -> None:
    done = run(tmp_path, [user("fix it"), reply("Fixed the parser. The tests pass.")])
    assert held(done) is None


def test_an_offer_early_in_a_long_reply_passes(tmp_path: Path) -> None:
    body = "Shall I start? I started anyway.\n\n" + "The parser now reads every row.\n" * 40
    assert held(run(tmp_path, [user("fix it"), reply(body)])) is None


def test_a_held_turn_ends_the_second_time(tmp_path: Path) -> None:
    done = run(tmp_path, [user("fix it"), reply("Want me to add tests?")], stop_hook_active=True)
    assert held(done) is None


def test_the_reply_from_the_call_wins_over_the_transcript(tmp_path: Path) -> None:
    done = run(tmp_path, [user("fix it"), reply("Fixed.")], last_assistant_message="Fixed. Want me to add tests?")
    assert held(done) is not None


def test_only_the_reply_after_the_last_prompt_counts(tmp_path: Path) -> None:
    entries = [user("one"), reply("Want me to add tests?"), user("no, fix it"), skill_load("x")]
    assert held(run(tmp_path, entries)) is None


def test_unreadable_input_lets_the_turn_end(tmp_path: Path) -> None:
    done = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True, check=False)
    assert (done.returncode, done.stdout) == (0, "")

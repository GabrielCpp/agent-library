"""When the clock hook stays quiet, when it blocks a call, and what resets it.

Every case runs the script as the harness does, with its state in its own `tmp_path`.
"""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "clock.py"
START = 1_800_000_000
MIN = 60


def stamp(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def user(epoch: float, content: object = "do the thing", **extra: object) -> dict[str, object]:
    return {"type": "user", "timestamp": stamp(epoch), "message": {"role": "user", "content": content}, **extra}


def write(path: Path, entries: list[dict[str, object]]) -> Path:
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def transcript(tmp_path: Path) -> Path:
    return write(tmp_path / "t.jsonl", [user(START)])


def run(tmp_path: Path, at: float, transcript: Path | None, session: str = "s1",
        stdin: str | None = None, harness: str | None = None) -> subprocess.CompletedProcess[str]:
    call = {"session_id": session, "tool_name": "Bash", "transcript_path": str(transcript) if transcript else None}
    environ = dict(os.environ, CLOCK_HOOK_STATE_DIR=str(tmp_path / "state"), CLOCK_HOOK_NOW=str(at),
                   COPILOT_HOME=str(tmp_path / "copilot"), XDG_DATA_HOME=str(tmp_path / "data"))
    environ.pop("CLOCK_HOOK_MINUTES", None)
    flags = ["--harness", harness] if harness else []
    return subprocess.run(
        [sys.executable, str(SCRIPT), *flags], input=json.dumps(call) if stdin is None else stdin,
        capture_output=True, text=True, env=environ, check=False,
    )


def test_under_the_interval_passes(tmp_path: Path, transcript: Path) -> None:
    done = run(tmp_path, START + 44 * MIN, transcript)
    assert (done.returncode, done.stderr) == (0, "")


def test_past_the_interval_blocks_with_the_elapsed_time(tmp_path: Path, transcript: Path) -> None:
    done = run(tmp_path, START + 90 * MIN, transcript)
    assert done.returncode == 2
    assert done.stderr.startswith("Clock: 1 h 30 min since the request (")
    assert "What the next 45 min buy" in done.stderr


def test_the_nudge_routes_to_the_judging_skills(tmp_path: Path, transcript: Path) -> None:
    done = run(tmp_path, START + 50 * MIN, transcript)
    assert done.returncode == 2
    assert "Load step-back when line 2 names nothing new" in done.stderr
    assert "Load whole-first, then vet-proposal, when the work in hand is something the request did not name" in done.stderr
    assert done.stderr.rstrip().endswith("Then retry the call.")


def test_minutes_only_when_under_an_hour(tmp_path: Path, transcript: Path) -> None:
    done = run(tmp_path, START + 50 * MIN, transcript)
    assert done.returncode == 2
    assert "Clock: 50 min since the request" in done.stderr


def test_the_call_after_a_nudge_passes(tmp_path: Path, transcript: Path) -> None:
    assert run(tmp_path, START + 50 * MIN, transcript).returncode == 2
    assert run(tmp_path, START + 50 * MIN + 1, transcript).returncode == 0


def test_another_interval_later_blocks_again(tmp_path: Path, transcript: Path) -> None:
    assert run(tmp_path, START + 50 * MIN, transcript).returncode == 2
    assert run(tmp_path, START + 94 * MIN, transcript).returncode == 0
    assert run(tmp_path, START + 96 * MIN, transcript).returncode == 2


def test_a_new_human_prompt_resets(tmp_path: Path, transcript: Path) -> None:
    assert run(tmp_path, START + 50 * MIN, transcript).returncode == 2
    later = START + 100 * MIN
    write(transcript, [user(START), user(later - 10 * MIN)])
    assert run(tmp_path, later, transcript).returncode == 0
    assert run(tmp_path, later + 40 * MIN, transcript).returncode == 2


def test_tool_results_and_meta_entries_are_not_the_request(tmp_path: Path) -> None:
    path = write(tmp_path / "t.jsonl", [
        user(START),
        user(START + 40 * MIN, [{"type": "tool_result", "content": "ok"}]),
        user(START + 41 * MIN, "meta", isMeta=True),
    ])
    done = run(tmp_path, START + 50 * MIN, path)
    assert done.returncode == 2
    assert "Clock: 50 min" in done.stderr


def test_a_human_prompt_given_as_text_blocks_counts(tmp_path: Path) -> None:
    path = write(tmp_path / "t.jsonl", [user(START), user(START + 40 * MIN, [{"type": "text", "text": "hi"}])])
    assert run(tmp_path, START + 50 * MIN, path).returncode == 0


def test_a_missing_transcript_falls_back_to_first_seen(tmp_path: Path) -> None:
    missing = tmp_path / "none.jsonl"
    assert run(tmp_path, START, missing).returncode == 0
    assert run(tmp_path, START + 44 * MIN, missing).returncode == 0
    done = run(tmp_path, START + 46 * MIN, missing)
    assert done.returncode == 2
    assert "Clock: 46 min" in done.stderr


@pytest.mark.parametrize("stdin", ["", "not json", "[1]", '{"session_id": 5}'])
def test_garbage_input_passes(tmp_path: Path, stdin: str) -> None:
    done = run(tmp_path, START + 90 * MIN, None, stdin=stdin)
    assert (done.returncode, done.stderr) == (0, "")


def codex_turn(epoch: float, parent: str | None = None) -> dict[str, object]:
    attribution = {"turn_id": f"t{epoch}", "turn_trigger": "exec", "parent_turn_id": parent}
    return {"timestamp": stamp(epoch), "type": "event_msg", "payload": {"type": "task_started", "turn_attribution": attribution}}


def codex_prompt(epoch: float) -> dict[str, object]:
    content = [{"type": "input_text", "text": "do the thing"}]
    return {"timestamp": stamp(epoch), "type": "response_item", "payload": {"type": "message", "role": "user", "content": content}}


def test_a_codex_turn_start_is_the_request(tmp_path: Path) -> None:
    log = write(tmp_path / "rollout.jsonl", [
        codex_turn(START), codex_prompt(START),
        codex_turn(START + 60 * MIN), codex_prompt(START + 60 * MIN),
        codex_prompt(START + 100 * MIN),
    ])
    assert run(tmp_path, START + 104 * MIN, log).returncode == 0
    done = run(tmp_path, START + 106 * MIN, log)
    assert done.returncode == 2
    assert "Clock: 46 min since the request" in done.stderr


def test_a_codex_turn_a_parent_turn_started_is_not_the_request(tmp_path: Path) -> None:
    log = write(tmp_path / "rollout.jsonl", [codex_turn(START), codex_turn(START + 40 * MIN, parent="t0")])
    assert run(tmp_path, START + 50 * MIN, log).returncode == 2


def copilot_message(epoch: float, source: str | None = None) -> dict[str, object]:
    data: dict[str, object] = {"content": "do the thing"}
    if source:
        data["source"] = source
    return {"type": "user.message", "timestamp": stamp(epoch), "data": data}


def copilot_log(tmp_path: Path, session: str, entries: list[dict[str, object]]) -> None:
    folder = tmp_path / "copilot" / "session-state" / session
    folder.mkdir(parents=True)
    write(folder / "events.jsonl", entries)


def test_a_copilot_user_message_is_the_request(tmp_path: Path) -> None:
    copilot_log(tmp_path, "c1", [
        copilot_message(START), copilot_message(START + 60 * MIN),
        copilot_message(START + 100 * MIN, source="autopilot"),
        copilot_message(START + 101 * MIN, source="agent-7"),
    ])
    assert run(tmp_path, START + 104 * MIN, None, session="c1", harness="copilot").returncode == 0
    done = run(tmp_path, START + 106 * MIN, None, session="c1", harness="copilot")
    assert done.returncode == 2
    assert "Clock: 46 min since the request" in done.stderr


def opencode_db(tmp_path: Path) -> sqlite3.Connection:
    folder = tmp_path / "data" / "opencode"
    folder.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(folder / "opencode.db")
    db.executescript(
        "create table if not exists session (id text primary key, parent_id text);"
        "create table if not exists message (id text primary key, session_id text, time_created integer, data text);"
        "create table if not exists part (id text primary key, message_id text, session_id text, data text);"
    )
    return db


def opencode_message(db: sqlite3.Connection, session: str, epoch: float, role: str = "user",
                     parts: list[dict[str, object]] | None = None) -> None:
    mid = f"m{db.execute('select count(*) from message').fetchone()[0]}"
    db.execute("insert into message values (?, ?, ?, ?)", (mid, session, int(epoch * 1000), json.dumps({"role": role})))
    for index, part in enumerate(parts if parts is not None else [{"type": "text", "text": "do"}]):
        db.execute("insert into part values (?, ?, ?, ?)", (f"{mid}p{index}", mid, session, json.dumps(part)))
    db.commit()


def test_an_opencode_user_text_is_the_request(tmp_path: Path) -> None:
    db = opencode_db(tmp_path)
    db.execute("insert into session values ('root', null), ('child', 'root')")
    opencode_message(db, "root", START)
    opencode_message(db, "root", START + 60 * MIN)
    opencode_message(db, "root", START + 61 * MIN, role="assistant")
    opencode_message(db, "root", START + 100 * MIN, parts=[{"type": "compaction"}])
    opencode_message(db, "root", START + 101 * MIN, parts=[{"type": "text", "text": "Continue", "synthetic": True}])
    opencode_message(db, "child", START + 102 * MIN)
    assert run(tmp_path, START + 104 * MIN, None, session="child", harness="opencode").returncode == 0
    done = run(tmp_path, START + 106 * MIN, None, session="child", harness="opencode")
    assert done.returncode == 2
    assert "Clock: 46 min since the request" in done.stderr


def test_a_missing_harness_store_falls_back_to_first_seen(tmp_path: Path) -> None:
    for harness in ("copilot", "opencode"):
        session = f"none-{harness}"
        assert run(tmp_path, START, None, session=session, harness=harness).returncode == 0
        assert run(tmp_path, START + 50 * MIN, None, session=session, harness=harness).returncode == 2

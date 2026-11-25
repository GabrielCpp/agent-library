#!/usr/bin/env python3
"""Show the agent the time since the user's request, at a fixed interval, and make it check its outcome.

The hook reads one PreToolUse call on stdin. It finds the newest request of the session, or
else the first time it saw the session. ``--harness`` says where the session keeps its
requests. In a Claude transcript a request is a human prompt. In a Codex transcript it is a
turn that no other turn started. In Copilot's session log under ``$COPILOT_HOME``, else
``~/.copilot``, it is a user message with no other source. In OpenCode's database under
``$XDG_DATA_HOME/opencode``, it is a user message of the root session with a text part
OpenCode did not write itself. Once the interval has
passed since that prompt, and since the last nudge, it blocks one call with a message.
The next call passes. Any failure lets the call through.

State lives in ``$CLOCK_HOOK_STATE_DIR``, else ``~/.local/state/clock-hook``. The interval
is ``$CLOCK_HOOK_MINUTES``, default 45. ``$CLOCK_HOOK_NOW`` overrides the clock in epoch seconds.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import cast

parse_json: Callable[[str], object] = json.loads

DEFAULT_MINUTES = 45
MESSAGE = (
    "Clock: {elapsed} since the request ({start}). Before this call, write three lines. "
    "1. What the person who asked has in hand now that they did not have at the start. "
    "2. What the next {interval} buy toward the outcome they asked for, and whether any "
    "result would change your next action. "
    "3. Continue, cut scope, or stop and report. Stopping with the outcome delivered and "
    "the rest named is a finished turn. "
    "Before line 3, load a skill when its case holds. "
    "Load step-back when line 2 names nothing new, when the same kind of attempt has repeated, "
    "or when a sub-task has outgrown the task it serves. "
    "Load whole-first, then vet-proposal, when the work in hand is something the request did not name. "
    "Then retry the call."
)


def as_object(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def state_dir() -> Path:
    override = os.environ.get("CLOCK_HOOK_STATE_DIR")
    return Path(override) if override else Path.home() / ".local" / "state" / "clock-hook"


def now() -> float:
    override = os.environ.get("CLOCK_HOOK_NOW")
    return float(override) if override else time.time()


def minutes() -> float:
    override = os.environ.get("CLOCK_HOOK_MINUTES")
    return float(override) if override else float(DEFAULT_MINUTES)


def is_human_prompt(entry: dict[str, object]) -> bool:
    if entry.get("type") != "user" or entry.get("isMeta") is True:
        return False
    message = as_object(entry.get("message"))
    content = message.get("content") if message else None
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        items = cast("list[object]", content)
        return not any(
            (as_object(item) or {}).get("type") == "tool_result" for item in items
        )
    return False


def is_codex_request(entry: dict[str, object]) -> bool:
    payload = as_object(entry.get("payload"))
    if entry.get("type") != "event_msg" or payload is None or payload.get("type") != "task_started":
        return False
    attribution = as_object(payload.get("turn_attribution")) or {}
    return attribution.get("parent_turn_id") is None


def is_request(entry: dict[str, object]) -> bool:
    return is_human_prompt(entry) or is_codex_request(entry)


def parse_time(stamp: str) -> float:
    return datetime.fromisoformat(stamp).timestamp()


def request_time(transcript: object) -> float | None:
    if not isinstance(transcript, str) or not transcript:
        return None
    return newest_request(Path(transcript), is_request)


def is_copilot_request(entry: dict[str, object]) -> bool:
    data = as_object(entry.get("data"))
    return entry.get("type") == "user.message" and data is not None and data.get("source") in (None, "user")


def newest_request(path: Path, accepts: Callable[[dict[str, object]], bool]) -> float | None:
    found: float | None = None
    try:
        with open(path, encoding="utf-8") as lines:
            for line in lines:
                try:
                    entry = as_object(parse_json(line))
                    stamp = entry.get("timestamp") if entry else None
                    if entry and accepts(entry) and isinstance(stamp, str):
                        found = parse_time(stamp)
                except ValueError:
                    continue
    except OSError:
        return None
    return found


def copilot_request_time(session: str) -> float | None:
    if clean_name(session) != session:
        return None
    home = os.environ.get("COPILOT_HOME") or str(Path.home() / ".copilot")
    return newest_request(Path(home) / "session-state" / session / "events.jsonl", is_copilot_request)


OPENCODE_ROOT = "select parent_id from session where id = ?"
OPENCODE_REQUEST = """
    select m.time_created from message m
    where m.session_id = ? and json_extract(m.data, '$.role') = 'user' and exists (
        select 1 from part p where p.message_id = m.id
        and json_extract(p.data, '$.type') = 'text'
        and coalesce(json_extract(p.data, '$.synthetic'), 0) = 0
    )
    order by m.time_created desc limit 1
"""


def opencode_request_time(session: str) -> float | None:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    path = Path(base) / "opencode" / "opencode.db"
    if not path.is_file():
        return None
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1) as db:
            seen = {session}
            while True:
                row = db.execute(OPENCODE_ROOT, (session,)).fetchone()
                if not row or not isinstance(row[0], str) or row[0] in seen:
                    break
                session = row[0]
                seen.add(session)
            row = db.execute(OPENCODE_REQUEST, (session,)).fetchone()
    except sqlite3.Error:
        return None
    return row[0] / 1000 if row and isinstance(row[0], (int, float)) else None


def request_time_for(harness: str, call: dict[str, object], session: str) -> float | None:
    if harness == "copilot":
        return copilot_request_time(session)
    if harness == "opencode":
        return opencode_request_time(session)
    return request_time(call.get("transcript_path"))


def clean_name(session: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session)


def load(path: Path) -> dict[str, object]:
    try:
        return as_object(parse_json(path.read_text(encoding="utf-8"))) or {}
    except (OSError, ValueError):
        return {}


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def human(seconds: float) -> str:
    total = int(seconds // 60)
    hours, rest = divmod(total, 60)
    return f"{hours} h {rest} min" if hours else f"{rest} min"


def decide(call: dict[str, object], harness: str = "claude") -> str | None:
    session = call.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    current = now()
    interval = minutes() * 60
    path = state_dir() / f"{clean_name(session)}.json"
    state = load(path)
    start = request_time_for(harness, call, session)
    if start is None:
        start = number(state.get("request_ts"))
        if start is None:
            start = current
    last = number(state.get("last_nudge"))
    if number(state.get("request_ts")) != start:
        last = None
    elapsed = current - start
    nudge = elapsed >= interval and (last is None or current - last >= interval)
    if nudge:
        last = current
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"request_ts": start, "last_nudge": last}), encoding="utf-8")
    if not nudge:
        return None
    return MESSAGE.format(
        elapsed=human(elapsed),
        start=datetime.fromtimestamp(start).strftime("%H:%M"),
        interval=human(interval),
    )


def main(argv: list[str]) -> int:
    harness = argv[argv.index("--harness") + 1] if "--harness" in argv[:-1] else "claude"
    try:
        call = as_object(parse_json(sys.stdin.read()))
        message = decide(call, harness) if call else None
    except (OSError, ValueError, TypeError, ArithmeticError):
        return 0
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

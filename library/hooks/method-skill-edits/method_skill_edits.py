#!/usr/bin/env python3
"""Stop an edit that needs a method skill until the agent has loaded that skill.

The hook reads one PreToolUse call for Edit, MultiEdit or Write on stdin. It counts each
pattern in the text the edit replaces and in the text it writes. A pattern whose count grows
is a move a method skill exists for:

- root-cause: an escape hatch, such as a broad except, a retry, a sleep, a fallback, a lint
  or type ignore, a skipped test or a waiver.
- vet-proposal: a new carrier, such as a command-line flag, a setting read from the
  environment, a set of kinds, or a row added to a plan.

When the session's transcript shows no load of that skill and the hook has not already
stopped the session for it, the hook blocks the call once and names the skill. The next
call passes, so a false match costs one step. Any failure lets the call through.

State lives in ``$METHOD_SKILL_EDITS_STATE_DIR``, else ``~/.local/state/method-skill-edits``.
``METHOD_SKILL_EDITS_OFF=1`` disables the hook.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

parse_json: Callable[[str], object] = json.loads

SOURCE = re.compile(r"\.(py|pyi|ts|tsx|js|jsx|mjs|go|dart|kt|kts|java|swift|rs|php|rb|sh|bash)$")
TEST = re.compile(r"(^|/)(tests?|__tests__|spec|e2e)/|(^|/)test_[^/]*$|_test\.\w+$|\.(test|spec)\.\w+$")
PLAN = re.compile(r"(^|/)(plans?|stories|epics)/[^/]*\.md$|(^|/)[^/]*plan[^/]*\.md$", re.IGNORECASE)
PLAN_ROW = re.compile(r"^\s*(?:[-*+] |\d+\. |\|(?!\s*-+\s*\|))", re.MULTILINE)


@dataclass(frozen=True)
class Move:
    """A pattern whose growth in an edit is a move one method skill exists for."""

    skill: str
    what: str
    pattern: re.Pattern[str]
    tests_too: bool = False


ROOT_CAUSE = "root-cause"
VET = "vet-proposal"

MOVES = (
    Move(ROOT_CAUSE, "a broad except", re.compile(r"\bexcept\s*(?:\(?\s*(?:Base)?Exception\b[^:]*)?:")),
    Move(ROOT_CAUSE, "an empty catch", re.compile(r"\bcatch\s*(?:\([^)]*\))?\s*\{\s*\}")),
    Move(ROOT_CAUSE, "a retry", re.compile(r"\bretr(?:y|ies|ying)\b|\bmax_attempts\b|\bbackoff\b", re.IGNORECASE)),
    Move(ROOT_CAUSE, "a sleep", re.compile(r"\btime\.sleep\(|\basyncio\.sleep\(|\btime\.Sleep\(|\bThread\.sleep\(")),
    Move(ROOT_CAUSE, "a fallback", re.compile(r"\bfall_?back\b", re.IGNORECASE)),
    Move(ROOT_CAUSE, "a lint or type ignore", re.compile(
        r"#\s*(?:noqa|type:\s*ignore|ty:\s*ignore|pyright:\s*ignore)|@ts-(?:ignore|expect-error|nocheck)"
        r"|eslint-disable|//\s*nolint|@Suppress\(|@SuppressWarnings\(")),
    Move(ROOT_CAUSE, "a skipped test", re.compile(
        r"\bpytest\.mark\.(?:skip|skipif|xfail)\b|\bpytest\.(?:skip|xfail)\(|\b(?:it|test|describe)\.(?:skip|todo)\("
        r"|\bt\.Skip\(|@(?:Disabled|Ignore)\b"), tests_too=True),
    Move(ROOT_CAUSE, "a waiver", re.compile(r"\bwaive[rds]?\b|\ballow_?list\b|\bexempt(?:ion)?s?\b|\bknown_failures?\b", re.IGNORECASE)),
    Move(ROOT_CAUSE, "a shell error swallowed", re.compile(r"\|\|\s*true\b")),
    Move(VET, "a command-line flag", re.compile(
        r"\badd_argument\(\s*['\"]-|@click\.option\(|\btyper\.Option\(|\bflag\.(?:String|Bool|Int|Duration|Float)(?:Var)?\(")),
    Move(VET, "a setting read from the environment", re.compile(
        r"\bos\.environ\.get\(|\bos\.getenv\(|\bos\.environ\[|\bprocess\.env\.\w|\bos\.Getenv\(")),
    Move(VET, "a set of kinds", re.compile(r"\bLiteral\[|\bclass\s+\w+\((?:Str|Int)?Enum\)")),
)

MESSAGES = {
    ROOT_CAUSE: (
        "This edit adds {what} to {path}. That is an escape hatch, the move the root-cause "
        "skill exists for. Load root-cause with the Skill tool and write the why-chain for this "
        "fix before the edit. If the chain ends at a core property of the problem, retry the "
        "edit unchanged. Otherwise fix the origin instead. This check fires once per session."
    ),
    VET: (
        "This edit adds {what} to {path}. A new carrier is the move the vet-proposal skill "
        "exists for. Load vet-proposal with the Skill tool and vet it: name who needs it and "
        "the variable it stands for. Then retry the edit, or drop it. This check fires once "
        "per session."
    ),
}


def as_object(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def text(value: object) -> str:
    return value if isinstance(value, str) else ""


def state_dir() -> Path:
    override = os.environ.get("METHOD_SKILL_EDITS_STATE_DIR")
    return Path(override) if override else Path.home() / ".local" / "state" / "method-skill-edits"


def before_and_after(tool: str, tool_input: dict[str, object], path: str) -> list[tuple[str, str]]:
    """Each pair of replaced text and written text the call holds."""
    if tool == "Write":
        try:
            old = Path(path).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            old = ""
        return [(old, text(tool_input.get("content")))]
    if tool == "MultiEdit":
        edits = tool_input.get("edits")
        items = cast("list[object]", edits) if isinstance(edits, list) else []
        pairs = []
        for item in items:
            edit = as_object(item) or {}
            pairs.append((text(edit.get("old_string")), text(edit.get("new_string"))))
        return pairs
    return [(text(tool_input.get("old_string")), text(tool_input.get("new_string")))]


def grown(pairs: list[tuple[str, str]], pattern: re.Pattern[str]) -> bool:
    return sum(len(pattern.findall(new)) - len(pattern.findall(old)) for old, new in pairs) > 0


def moves_in(tool: str, tool_input: dict[str, object]) -> list[tuple[str, str, str]]:
    """Each (skill, what, file name) the edit makes, at most one per skill."""
    path = text(tool_input.get("file_path"))
    if not path:
        return []
    pairs = before_and_after(tool, tool_input, path)
    name = Path(path).name
    found: dict[str, tuple[str, str, str]] = {}
    if SOURCE.search(path):
        is_test = bool(TEST.search(path))
        for move in MOVES:
            if move.skill in found or (is_test and not move.tests_too):
                continue
            if grown(pairs, move.pattern):
                found[move.skill] = (move.skill, move.what, name)
    elif PLAN.search(path) and tool != "Write" and VET not in found and grown(pairs, PLAN_ROW):
        found[VET] = (VET, "a row to a plan", name)
    return list(found.values())


def skill_name(name: str) -> str:
    return name.rsplit(":", 1)[-1]


def loaded_skills(transcript: object) -> set[str]:
    """The method skills the session loaded, by their bare names."""
    names: set[str] = set()
    if not isinstance(transcript, str) or not transcript:
        return names
    try:
        with open(transcript, encoding="utf-8", errors="ignore") as lines:
            for line in lines:
                if '"Skill"' not in line and "<command-name>" not in line:
                    continue
                for skill in (ROOT_CAUSE, VET):
                    if re.search(rf'"skill"\s*:\s*"(?:[\w-]*[:-])?{skill}"|<command-name>/?(?:[\w-]*[:-])?{skill}</command-name>', line):
                        names.add(skill)
    except OSError:
        return names
    return names


def clean_name(session: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", session)


def decide(call: dict[str, object]) -> str | None:
    if os.environ.get("METHOD_SKILL_EDITS_OFF") == "1":
        return None
    tool = text(call.get("tool_name"))
    tool_input = as_object(call.get("tool_input"))
    session = text(call.get("session_id"))
    if tool not in ("Edit", "MultiEdit", "Write") or tool_input is None or not session:
        return None
    moves = moves_in(tool, tool_input)
    if not moves:
        return None
    loaded = loaded_skills(call.get("transcript_path"))
    state_path = state_dir() / f"{clean_name(session)}.json"
    try:
        warned = set(cast("list[str]", json.loads(state_path.read_text(encoding="utf-8"))))
    except (OSError, ValueError, TypeError):
        warned = set()
    due = [move for move in moves if move[0] not in loaded and move[0] not in warned]
    if not due:
        return None
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(sorted(warned | {move[0] for move in due})), encoding="utf-8")
    return "\n\n".join(MESSAGES[skill].format(what=what, path=name) for skill, what, name in due)


def main() -> int:
    try:
        call = as_object(parse_json(sys.stdin.read()))
        message = decide(call) if call else None
    except (OSError, ValueError, TypeError):
        return 0
    if message:
        print(message, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

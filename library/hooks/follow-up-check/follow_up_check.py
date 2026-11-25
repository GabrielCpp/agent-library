#!/usr/bin/env python3
"""Hold a turn open once when its last reply ends by offering or proposing more work.

The hook reads one Stop call on stdin. It takes the reply the agent ended on, from
``last_assistant_message`` or else the session transcript, and reads its closing lines. A
closing line that offers work ("Want me to", "Shall I") or proposes a follow-up is the move
the whole-first skill exists for. The hook blocks the stop on an offer every time, and on a
follow-up only while the session has not loaded whole-first. It asks the agent to screen the
offer: do the work that belongs to the request, keep the rest as one plain line, or drop it.

An offer that waits on a hand-back action (push, merge, publish, deploy, delete, send) passes,
because the agent may not take that action alone. A follow-up gets no such pass: a hand-back
word in it is as often a file or a job name as the action, and whole-first keeps a real
hand-back as its one line anyway. A turn the hook already held
(``stop_hook_active``) ends, so a run is told once and never loops. Any failure lets the turn
end. ``FOLLOW_UP_CHECK_OFF=1`` disables the hook.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from typing import cast

parse_json: Callable[[str], object] = json.loads

CLOSING_CHARS = 700
OFFER = re.compile(
    r"\b(?:want me to|shall i|should i|do you want me to|would you like me to|would you like (?:a|an|the)\b"
    r"|let me know if you(?:'d| would)? (?:like|want)|i can also|happy to)\b",
    re.IGNORECASE,
)
PROPOSAL = re.compile(
    r"^(?:[-*]\s+)?(?:\*\*)?(?:possible |suggested |worth a )?(?:follow-?ups?|next steps?)(?:\*\*)?\s*(?:\([^)]*\))?\s*:"
    r"|\b(?:a|one|another) (?:possible |natural |good )?follow-?up (?:could|would|is to|worth)\b",
    re.IGNORECASE,
)
HAND_BACK = re.compile(r"\b(?:push|merge|force|publish|release|deploy|delete|remove|rm|send|post)\w*\b", re.IGNORECASE)
WHOLE_FIRST = re.compile(
    r'"skill"\s*:\s*"(?:[\w-]*[:-])?whole-first"|<command-name>/?(?:[\w-]*[:-])?whole-first</command-name>'
)
REASON = (
    "Your reply ends by offering or proposing more work: \"{line}\". That is the move the "
    "whole-first skill exists for. Load whole-first with the Skill tool and screen the offer "
    "against the request. Work that belongs to the request is yours to do now, not to offer. "
    "Work that does not belongs on one plain line with no question, or nowhere. Then end the turn."
)


def as_object(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def message_text(entry: dict[str, object]) -> str:
    message = as_object(entry.get("message")) or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    items = cast("list[object]", content) if isinstance(content, list) else []
    parts = [text for item in items if (block := as_object(item)) and block.get("type") == "text"
             and isinstance(text := block.get("text"), str)]
    return "\n".join(parts)


def is_human_prompt(entry: dict[str, object]) -> bool:
    if entry.get("type") != "user" or entry.get("isMeta") is True or entry.get("isSidechain") is True:
        return False
    message = as_object(entry.get("message")) or {}
    content = message.get("content")
    if isinstance(content, str):
        return True
    items = cast("list[object]", content) if isinstance(content, list) else []
    return bool(items) and not any((as_object(item) or {}).get("type") == "tool_result" for item in items)


def read_session(transcript: object) -> tuple[str, bool]:
    """The last reply text since the user's last prompt, and whether the session loaded whole-first."""
    if not isinstance(transcript, str) or not transcript:
        return "", False
    reply = ""
    loaded = False
    with open(transcript, encoding="utf-8", errors="ignore") as lines:
        for line in lines:
            try:
                entry = as_object(parse_json(line))
            except ValueError:
                continue
            if entry is None or entry.get("isSidechain") is True:
                continue
            if is_human_prompt(entry):
                reply = ""
                loaded = loaded or bool(WHOLE_FIRST.search(line))
                continue
            if WHOLE_FIRST.search(line):
                loaded = True
            if entry.get("type") == "assistant":
                said = message_text(entry)
                if said.strip():
                    reply = said
    return reply, loaded


def closing_line(reply: str, pattern: re.Pattern[str], *, hand_back_passes: bool) -> str | None:
    """The closing sentence *pattern* finds, unless it waits on a hand-back and *hand_back_passes*."""
    closing = reply.strip()[-CLOSING_CHARS:]
    for line in reversed([line.strip() for line in closing.splitlines() if line.strip()]):
        for sentence in re.split(r"(?<=[.?!])\s+", line):
            if pattern.search(sentence) and not (hand_back_passes and HAND_BACK.search(sentence)):
                return sentence[:200]
    return None


def verdict(call: dict[str, object]) -> dict[str, str] | None:
    if os.environ.get("FOLLOW_UP_CHECK_OFF") == "1" or call.get("stop_hook_active"):
        return None
    reply, loaded = read_session(call.get("transcript_path"))
    last = call.get("last_assistant_message")
    if isinstance(last, str) and last.strip():
        reply = last
    if not reply:
        return None
    line = closing_line(reply, OFFER, hand_back_passes=True)
    if line is None and not loaded:
        line = closing_line(reply, PROPOSAL, hand_back_passes=False)
    if line is None:
        return None
    return {"decision": "block", "reason": REASON.format(line=line)}


def main() -> int:
    try:
        call = as_object(parse_json(sys.stdin.read() or "{}"))
        decision = verdict(call) if call else None
    except (OSError, ValueError, TypeError):
        return 0
    if decision is not None:
        print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    sys.exit(main())

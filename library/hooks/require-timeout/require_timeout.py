#!/usr/bin/env python3
"""Make every foreground shell call carry a timeout, filling it from past calls when it can.

The guard reads one PreToolUse call on stdin. A call that runs in the background passes,
unless it polls. A polling call runs ``until``, ``while`` or ``pgrep`` as a command, or in a
``bash -c`` script, and it can wait forever. Each poll must sit inside a ``timeout <duration>``
command, or the guard refuses the call.

A foreground call that sets a timeout passes, and the guard records that timeout in its
cache under two keys for the call's working directory: the command as written, and its
signature.
A signature keeps each simple command's program and the plain words after it, so
``pytest -q tests/a.py`` and ``pytest -q tests/b.py`` share ``pytest -q``.

A call with no timeout takes the last timeout recorded for the same command, or else the
largest of the recent timeouts recorded for its signature. A call the cache knows nothing
about is refused, so the agent estimates its own timeout and retries.

``--harness`` names the harness that runs the guard. Claude and OpenCode carry a timeout
parameter, so the guard rewrites that parameter and leaves the command alone. Claude's auto
mode accepts that rewrite, because the command its review saw is unchanged. Every other
harness gets the command wrapped in coreutils ``timeout``. There a command that already
starts with ``timeout <duration>`` sets its own timeout, and the guard learns it for the
command it wraps. A machine with no ``timeout`` or ``gtimeout`` leaves the command as is.

The cache lives in ``$REQUIRE_TIMEOUT_CACHE``, else ``$XDG_CACHE_HOME/agent-hooks``, else
``~/.cache/agent-hooks``. A cache the guard cannot read counts as empty.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import shlex
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar, cast

T = TypeVar("T")
parse_json: Callable[[str], object] = json.loads

MAX_TIMEOUT_MS = 600_000
KILL_AFTER_SECONDS = 5
NATIVE_HARNESSES = {"claude", "opencode"}
TIMEOUT_PROGRAMS = ("timeout", "gtimeout")
TIMEOUT_VALUE_OPTIONS = {"-k", "-s", "--kill-after", "--signal"}
SHELLS = {"bash", "sh"}
DURATION = re.compile(r"^(\d+(?:\.\d+)?)([smhd]?)$")
DURATION_SECONDS = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}
MAX_ENTRIES = 1000
RECENT = 5
SIGNATURE_WORDS = 3
SEPARATORS = {"&&", "||", ";", ";;", "|", "|&", "&", "(", ")", "\n"}
REDIRECT = re.compile(r"^(?:\d*|&)(?:>>?|<<?<?|>\||<>|>&|<&)$")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
HEREDOC_BODY = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1.*?\n\t*\2(?=\n|$)", re.DOTALL)
PLAIN_WORD = re.compile(r"^-{0,2}[A-Za-z][A-Za-z0-9_.:-]*$")
SKIPPED_PROGRAMS = {"cd", "pushd", "popd", "export", "set", "echo", "true", ":"}
POLL_PROGRAMS = {"until", "while", "pgrep"}
COMMAND_PREFIXES = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "time"}


def cache_path() -> Path:
    override = os.environ.get("REQUIRE_TIMEOUT_CACHE")
    if override:
        return Path(override)
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "agent-hooks" / "require-timeout.json"


def normalized(command: str) -> str:
    return " ".join(command.split())


def segment_signature(words: list[str]) -> str | None:
    while words and ASSIGNMENT.match(words[0]):
        words = words[1:]
    if not words:
        return None
    program = os.path.basename(words[0])
    if program in SKIPPED_PROGRAMS:
        return None
    kept = [program]
    for word in words[1:]:
        if len(kept) > SIGNATURE_WORDS or not PLAIN_WORD.match(word):
            break
        kept.append(word)
    return " ".join(kept)


def tokens_of(command: str) -> list[str] | None:
    lexer = shlex.shlex(HEREDOC_BODY.sub(" ", command), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def signature(command: str) -> str | None:
    """The programs *command* runs, each with its plain leading words, or None."""
    tokens = tokens_of(command)
    if tokens is None:
        return None
    parts: list[str] = []
    words: list[str] = []
    skip_next = False
    for token in tokens + [";"]:
        if skip_next:
            skip_next = False
            continue
        if token in SEPARATORS:
            part = segment_signature(words)
            if part and (not parts or parts[-1] != part):
                parts.append(part)
            words = []
        elif REDIRECT.match(token):
            skip_next = True
        else:
            words.append(token)
    return " ; ".join(parts) or None


def segment_end(tokens: list[str], start: int) -> int:
    return next((i for i in range(start, len(tokens)) if tokens[i] in SEPARATORS), len(tokens))


def unbounded_poll(command: str) -> bool:
    """Whether *command* runs ``until``, ``while`` or ``pgrep`` outside a ``timeout``.

    A shell script passed with ``-c`` counts as part of *command*.
    """
    tokens = tokens_of(command)
    if tokens is None:
        return False
    at_command = True
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if at_command and timed(tokens[index:segment_end(tokens, index)]):
            index = segment_end(tokens, index)
            continue
        after_shell = index >= 2 and os.path.basename(tokens[index - 2]) in SHELLS
        if after_shell and tokens[index - 1] == "-c" and unbounded_poll(token):
            return True
        if at_command and os.path.basename(token) in POLL_PROGRAMS:
            return True
        if not (at_command and ASSIGNMENT.match(token)):
            at_command = token in SEPARATORS or (at_command and token in COMMAND_PREFIXES)
        index += 1
    return False


def keys(cwd: str, command: str) -> tuple[str, str | None]:
    exact = f"exact\0{cwd}\0{normalized(command)}"
    sig = signature(command)
    return exact, (f"sig\0{cwd}\0{sig}" if sig else None)


def as_object(value: object) -> dict[str, object] | None:
    return cast("dict[str, object]", value) if isinstance(value, dict) else None


def as_ints(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    items = cast("list[object]", value)
    return [item for item in items if isinstance(item, int) and not isinstance(item, bool)]


@dataclass
class Entry:
    """The recent timeouts recorded under one key, and when the key was last used."""

    timeouts: list[int]
    used: float

    @classmethod
    def parse(cls, value: object) -> Entry | None:
        data = as_object(value)
        if data is None:
            return None
        used = data.get("used")
        timeouts = as_ints(data.get("timeouts"))
        if not timeouts or not isinstance(used, (int, float)):
            return None
        return cls(timeouts, float(used))


Entries = dict[str, Entry]


class Cache:
    """Recent timeouts per key, kept in one JSON file under an exclusive lock."""

    path: Path

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> Entries:
        try:
            data = as_object(parse_json(self.path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return {}
        stored = as_object((data or {}).get("entries")) or {}
        entries: Entries = {}
        for name, value in stored.items():
            entry = Entry.parse(value)
            if entry is not None:
                entries[name] = entry
        return entries

    def _store(self, entries: Entries) -> None:
        newest = sorted(entries.items(), key=lambda item: item[1].used)[-MAX_ENTRIES:]
        serial = {
            name: {"timeouts": entry.timeouts, "used": entry.used} for name, entry in newest
        }
        handle, temp = tempfile.mkstemp(dir=self.path.parent, prefix=".require-timeout-")
        with os.fdopen(handle, "w", encoding="utf-8") as out:
            json.dump({"version": 1, "entries": serial}, out)
        os.replace(temp, self.path)

    def _locked(self, change: Callable[[Entries], tuple[T, bool]], default: T) -> T:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path.with_suffix(".lock"), "w", encoding="utf-8") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                entries = self._load()
                result, changed = change(entries)
                if changed:
                    self._store(entries)
                return result
        except OSError:
            return default

    def record(self, names: list[str], timeout: int) -> None:
        def change(entries: Entries) -> tuple[None, bool]:
            now = time.time()
            for name in names:
                entry = entries.get(name)
                recent = entry.timeouts[-(RECENT - 1):] if entry else []
                entries[name] = Entry(recent + [timeout], now)
            return None, True

        self._locked(change, None)

    def lookup(self, exact: str, sig: str | None) -> int | None:
        def change(entries: Entries) -> tuple[int | None, bool]:
            exact_entry = entries.get(exact)
            if exact_entry:
                exact_entry.used = time.time()
                return exact_entry.timeouts[-1], True
            sig_entry = entries.get(sig) if sig else None
            if sig_entry:
                sig_entry.used = time.time()
                return max(sig_entry.timeouts), True
            return None, False

        return self._locked(change, None)


def duration_ms(word: str) -> int | None:
    match = DURATION.match(word)
    if not match:
        return None
    seconds = float(match.group(1)) * DURATION_SECONDS[match.group(2)]
    return valid_timeout(seconds * 1000)


def timed(words: list[str]) -> tuple[int, list[str]] | None:
    """The timeout a simple command starting with ``timeout <duration>`` sets, and what it runs."""
    if not words or os.path.basename(words[0]) not in TIMEOUT_PROGRAMS:
        return None
    index = 1
    while index < len(words) and words[index].startswith("-"):
        index += 2 if words[index] in TIMEOUT_VALUE_OPTIONS else 1
    if index + 1 >= len(words):
        return None
    timeout = duration_ms(words[index])
    return None if timeout is None else (timeout, words[index + 1:])


def own_timeout(command: str) -> tuple[int, str] | None:
    """The timeout a leading ``timeout <duration>`` sets on all of *command*, and what it runs."""
    tokens = tokens_of(command)
    if not tokens or any(token in SEPARATORS for token in tokens):
        return None
    while tokens and ASSIGNMENT.match(tokens[0]):
        tokens = tokens[1:]
    bounded = timed(tokens)
    if bounded is None:
        return None
    timeout, inner = bounded
    if len(inner) == 3 and os.path.basename(inner[0]) in SHELLS and inner[1] == "-c":
        return timeout, inner[2]
    return timeout, shlex.join(inner)


def timeout_program() -> str | None:
    return next((name for name in TIMEOUT_PROGRAMS if shutil.which(name)), None)


def wrapped(command: str, timeout: int, program: str) -> str:
    seconds = -(-timeout // 1000)
    shell = "bash" if shutil.which("bash") else "sh"
    return f"{program} -k {KILL_AFTER_SECONDS} {seconds} {shell} -c {shlex.quote(command)}"


def valid_timeout(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    return int(min(value, MAX_TIMEOUT_MS))


Output = dict[str, object]


def rewrite(updated: dict[str, object]) -> Output:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": updated}}


NATIVE_REFUSAL = (
    "Blocked: estimate how long this command will take and set the Bash 'timeout' parameter (ms)"
    " to ~2x that estimate (max 600000), or use run_in_background for long jobs. Then retry."
)
POLL_REFUSAL = (
    "Blocked: this background command polls (until, while or pgrep) and could wait forever."
    " Wrap each poll as `timeout <duration> bash -c '...'`, set to the longest wait you accept."
    " Then retry."
)
WRAPPED_REFUSAL = (
    "Blocked: estimate how long this command will take and start it with `timeout <seconds>`"
    " set to ~2x that estimate (max 600), or run it in the background for long jobs. Then retry."
)


def refuse(reason: str) -> Output:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def decide(call: dict[str, object], cache: Cache, harness: str = "claude") -> Output | None:
    """The JSON to print for *call*, or None to let it run as written."""
    tool_input = as_object(call.get("tool_input"))
    if tool_input is None:
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return None
    if tool_input.get("run_in_background") is True:
        return refuse(POLL_REFUSAL) if unbounded_poll(command) else None
    cwd = call.get("cwd")
    cwd = cwd if isinstance(cwd, str) and cwd else os.getcwd()
    native = harness in NATIVE_HARNESSES
    timeout = valid_timeout(tool_input.get("timeout")) if native else None
    taught = command
    if not native:
        own = own_timeout(command)
        if own is not None:
            timeout, taught = own
    exact, sig = keys(cwd, taught)
    if timeout:
        cache.record([name for name in (exact, sig) if name], timeout)
        return None
    program = None if native else timeout_program()
    if not native and program is None:
        return None
    timeout = cache.lookup(exact, sig)
    if timeout is None:
        return refuse(WRAPPED_REFUSAL if program else NATIVE_REFUSAL)
    if program is None:
        return rewrite(dict(tool_input, timeout=timeout))
    return rewrite(dict(tool_input, command=wrapped(command, timeout, program)))


def main(argv: list[str]) -> int:
    harness = argv[argv.index("--harness") + 1] if "--harness" in argv[:-1] else "claude"
    try:
        call = as_object(parse_json(sys.stdin.read()))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if call is None:
        return 0
    output = decide(call, Cache(cache_path()), harness)
    if output is not None:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

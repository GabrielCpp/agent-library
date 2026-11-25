#!/usr/bin/env python3
"""Run a repo's commit checks inside an agent's own `git commit` call.

The guard reads one PreToolUse call on stdin. When the shell command commits, it asks
`farrier checks --repo <root>` for the repo's checks and rewrites the command so they run
first, from the repo root, with the commit command in ``$AGENT_COMMIT_COMMAND`` and the
directory it runs in under ``$AGENT_COMMIT_CWD``. A commit of named paths stages them first
and hands the checks the same paths. ``-a`` stages the tracked changes first.

Claude and OpenCode take the rewrite as is, with the call's timeout raised by the checks'
budgets. Codex rewrites only a call it is told to allow, and Claude's auto mode refuses a
rewrite nobody allowed, because its review saw the command the agent wrote. So for Codex,
and for Claude in auto mode, the guard allows a plain commit: nothing but ``cd``,
``git add``, ``git commit``, ``git log`` and ``git status`` joined by ``&&``, with no
environment prefix, no git option but ``-C``, no ``--output``, no command substitution
beyond a quoted heredoc message, and no redirect but to ``/dev/null``. It refuses any
other commit with the rewritten command for the agent to run instead.

Anything the guard cannot read passes through untouched: no commit, a commit it cannot
place, a repo with no checks, or a farrier that lists none.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

MARKER = "AGENT_COMMIT_COMMAND="
DEFAULT_TIMEOUT_MS = 120_000
MAX_TIMEOUT_MS = 600_000
LIST_SECONDS = 10
SEPARATORS = ("&&", "||", ";;", ";", "|", "&", "\n")
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
REDIRECT = re.compile(r"^(\d*|&)(>>?|<<?-?|>\|)(.*)$")
HEREDOC = re.compile(r"<<(?!<)-?\s*(['\"]?)([^\s'\";&|<>()]+)\1")
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
COMMIT_VALUE_SHORT = set("mFCct")
COMMIT_VALUE_LONG = {
    "--message", "--file", "--reuse-message", "--reedit-message", "--fixup", "--squash",
    "--author", "--date", "--template", "--cleanup", "--trailer", "--untracked-files",
    "--pathspec-from-file",
}
COMMIT_OPTIONAL_VALUE_SHORT = set("Su")
APPROVED = {"cd", "add", "commit", "log", "status"}
CAT_MESSAGE = re.compile(r"\$\(cat <<-?\s*'([^'\n]+)'\n.*?\n\t*\1\n\s*\)", re.DOTALL)
QUOTED_HEREDOC = re.compile(r"<<-?\s*'([^'\n]+)'\n.*?\n\t*\1(?=\n|$)", re.DOTALL)
SUBSTITUTION = re.compile(r"\$\(|`|<\(|>\(")


def blank_messages(command: str) -> str:
    """*command* with each quoted-heredoc ``$(cat ...)`` message blanked to the same length."""
    return CAT_MESSAGE.sub(lambda match: "x" * len(match.group(0)), command)


@dataclass
class Segment:
    """One simple command of a shell line, with where it starts and what joins it to the last."""

    text: str
    start: int
    joined_by: str


@dataclass
class Commit:
    """The commit a shell line makes, as far as the guard can read it."""

    segment: Segment
    directory: Path
    stage_tracked: bool = False
    paths: list[str] = field(default_factory=list)


def heredoc_end(command: str, index: int, delimiters: list[str]) -> int:
    """Where the bodies of *delimiters* end, the newline at *index* opening the first."""
    for delimiter in delimiters:
        while True:
            line_end = command.find("\n", index + 1)
            line = command[index + 1:] if line_end == -1 else command[index + 1:line_end]
            index = len(command) if line_end == -1 else line_end
            if line.lstrip("\t") == delimiter or line_end == -1:
                break
    return index


def split_segments(command: str) -> list[Segment]:
    """The top-level simple commands of *command*, quotes, subshells and heredocs kept whole."""
    segments: list[Segment] = []
    start, depth, quote, joined_by = 0, 0, "", ""
    pending: list[str] = []
    index = 0
    while index < len(command):
        char = command[index]
        if not quote and char == "<" and (index == 0 or command[index - 1] != "<"):
            heredoc = HEREDOC.match(command, index)
            if heredoc:
                pending.append(heredoc.group(2))
                index = heredoc.end()
                continue
        if not quote and char == "\n" and pending:
            index = heredoc_end(command, index, pending)
            pending = []
            continue
        if not quote and char == "&" and (
            command.startswith("&>", index) or (index and command[index - 1] in "<>")
        ):
            index += 1
            continue
        if quote:
            if char == "\\" and quote == '"':
                index += 2
                continue
            if char == quote:
                quote = ""
            index += 1
            continue
        if char == "\\":
            index += 2
            continue
        if char in "'\"":
            quote = char
        elif char == "(" or command.startswith("${", index):
            depth += 1
        elif char in ")}" and depth:
            depth -= 1
        elif depth == 0:
            separator = next((sep for sep in SEPARATORS if command.startswith(sep, index)), "")
            if separator:
                segments.append(Segment(command[start:index], start, joined_by))
                joined_by = separator
                index += len(separator)
                start = index
                continue
        index += 1
    segments.append(Segment(command[start:], start, joined_by))
    return [segment for segment in segments if segment.text.strip()]


def words(segment: Segment, redirects: list[tuple[str, str]] | None = None) -> list[str] | None:
    text = segment.text
    heredoc = HEREDOC.search(text)
    if heredoc:
        body = text.find("\n", heredoc.end())
        text = text if body == -1 else text[:body]
    try:
        found = shlex.split(text)
    except ValueError:
        return None
    while found and ASSIGNMENT.match(found[0]):
        found.pop(0)
    kept: list[str] = []
    skip_next = False
    for index, word in enumerate(found):
        if skip_next:
            skip_next = False
            continue
        redirect = REDIRECT.match(word)
        if redirect:
            skip_next = not redirect.group(3)
            if redirects is not None:
                following = found[index + 1] if index + 1 < len(found) else ""
                redirects.append((redirect.group(2), redirect.group(3) or following))
            continue
        kept.append(word)
    return kept


def git_subcommand(argv: list[str]) -> tuple[str, list[str], list[str]] | None:
    """The git subcommand, its arguments and the directories ``-C`` names, or None."""
    if not argv or argv[0] != "git":
        return None
    index, directories = 1, []
    while index < len(argv) and argv[index].startswith("-"):
        option = argv[index]
        if option in GIT_VALUE_OPTIONS:
            if option == "-C" and index + 1 < len(argv):
                directories.append(argv[index + 1])
            index += 2
            continue
        index += 1
    if index >= len(argv):
        return None
    return argv[index], argv[index + 1:], directories


def read_commit_args(args: list[str]) -> tuple[bool, list[str]]:
    """Whether the commit stages tracked changes, and the paths it names."""
    stage_tracked, paths, index = False, [], 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--":
            paths.extend(args[index:])
            break
        if arg in ("-a", "--all"):
            stage_tracked = True
        elif arg.startswith("--"):
            if arg in COMMIT_VALUE_LONG:
                index += 1
        elif arg.startswith("-") and len(arg) > 1:
            for position, letter in enumerate(arg[1:], start=1):
                if letter == "a":
                    stage_tracked = True
                elif letter in COMMIT_OPTIONAL_VALUE_SHORT:
                    break
                elif letter in COMMIT_VALUE_SHORT:
                    if position == len(arg) - 1:
                        index += 1
                    break
        else:
            paths.append(arg)
    return stage_tracked, paths


def find_commit(command: str, cwd: Path) -> Commit | None:
    """The first commit in *command*, with the directory it runs in, or None."""
    directory = cwd
    for segment in split_segments(blank_messages(command)):
        argv = words(segment)
        if argv is None:
            return None
        if argv and argv[0] == "cd":
            if len(argv) > 2 or (len(argv) == 2 and argv[1] == "-"):
                return None
            target = Path(argv[1]).expanduser() if len(argv) == 2 else Path.home()
            directory = directory / target
            continue
        parsed = git_subcommand(argv)
        if parsed is None or parsed[0] != "commit":
            continue
        if segment.joined_by not in ("", "&&", ";", "\n"):
            return None
        _sub, args, directories = parsed
        for name in directories:
            directory = directory / Path(name).expanduser()
        stage_tracked, paths = read_commit_args(args)
        return Commit(segment, directory, stage_tracked, paths)
    return None


def repo_root(directory: Path) -> Path | None:
    try:
        done = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=LIST_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Path(done.stdout.strip()) if done.returncode == 0 and done.stdout.strip() else None


def listed_checks(root: Path) -> list[tuple[str, float]]:
    """Each check farrier lists for *root*, with its budget in seconds."""
    farrier = shutil.which("farrier")
    if farrier is None:
        return []
    try:
        done = subprocess.run(
            [farrier, "checks", "--repo", str(root)],
            capture_output=True, text=True, timeout=LIST_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if done.returncode != 0:
        return []
    checks: list[tuple[str, float]] = []
    for line in done.stdout.splitlines():
        run, _tab, budget = line.partition("\t")
        if not run.strip():
            continue
        try:
            checks.append((run, float(budget)))
        except ValueError:
            checks.append((run, 0.0))
    return checks


def checks_block(command: str, commit: Commit, root: Path, checks: list[tuple[str, float]]) -> str:
    """The subshell that stages what the commit names, then runs every check from *root*."""
    directory = os.path.normpath(commit.directory)
    steps = [
        f"cd {shlex.quote(str(root))}",
        f"export {MARKER}{shlex.quote(command)} AGENT_COMMIT_CWD={shlex.quote(directory)}",
    ]
    if commit.stage_tracked:
        steps.append(f"git -C {shlex.quote(directory)} add -u")
    pathspecs: list[str] = []
    if commit.paths:
        quoted = " ".join(shlex.quote(path) for path in commit.paths)
        steps.append(f"git -C {shlex.quote(directory)} add -A -- {quoted}")
        pathspecs = [
            os.path.relpath(os.path.join(directory, path), root) for path in commit.paths
        ]
    suffix = "".join(f" {shlex.quote(path)}" for path in pathspecs)
    steps.extend(f"{run}{suffix}" for run, _budget in checks)
    return "(" + " && ".join(steps) + ")"


def rewrite(command: str, commit: Commit, root: Path, checks: list[tuple[str, float]]) -> str:
    start = commit.segment.start + len(commit.segment.text) - len(commit.segment.text.lstrip())
    block = checks_block(command, commit, root, checks)
    return f"{command[:start]}{block} && {command[start:]}"


def safe_redirect(operator: str, target: str) -> bool:
    return "<" in operator or target.startswith("&") or target == "/dev/null"


def approved(command: str) -> bool:
    """True when *command* is a plain commit the guard may allow without a review."""
    plain = blank_messages(command)
    if SUBSTITUTION.search(QUOTED_HEREDOC.sub("", plain)):
        return False
    for segment in split_segments(plain):
        if segment.joined_by not in ("", "&&"):
            return False
        if ASSIGNMENT.match(segment.text.lstrip()):
            return False
        redirects: list[tuple[str, str]] = []
        argv = words(segment, redirects)
        if not argv or not all(safe_redirect(*redirect) for redirect in redirects):
            return False
        if argv[0] == "cd":
            continue
        parsed = git_subcommand(argv)
        if parsed is None or parsed[0] not in APPROVED:
            return False
        if any(arg.startswith("--output") for arg in parsed[1]):
            return False
        options = argv[1:argv.index(parsed[0], 1)]
        if any(option != "-C" for option in options[::2]):
            return False
    return True


def answer(harness: str, call: dict, rewritten: str, original: str, budget: float) -> dict:
    tool_input = dict(call.get("tool_input") or {})
    tool_input["command"] = rewritten
    if harness != "codex":
        timeout = tool_input.get("timeout")
        base = timeout if isinstance(timeout, (int, float)) and timeout > 0 else DEFAULT_TIMEOUT_MS
        tool_input["timeout"] = int(min(MAX_TIMEOUT_MS, base + budget * 1000))
    if harness == "codex" or call.get("permission_mode") == "auto":
        if approved(original):
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": tool_input,
                }
            }
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "This commit must run the repo's commit checks first. Run this command "
                    f"instead, unchanged:\n{rewritten}"
                ),
            }
        }
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "updatedInput": tool_input}}


def decide(call: dict, harness: str) -> dict | None:
    """The hook output for *call*, or None to let it run as written."""
    command = (call.get("tool_input") or {}).get("command")
    if not isinstance(command, str) or MARKER in command or "commit" not in command:
        return None
    commit = find_commit(command, Path(call.get("cwd") or os.getcwd()))
    if commit is None:
        return None
    root = repo_root(commit.directory)
    if root is None:
        return None
    checks = listed_checks(root)
    if not checks:
        return None
    budget = sum(seconds for _run, seconds in checks)
    return answer(harness, call, rewrite(command, commit, root, checks), command, budget)


def main(argv: list[str]) -> int:
    harness = argv[argv.index("--harness") + 1] if "--harness" in argv[:-1] else "claude"
    try:
        call = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(call, dict):
        return 0
    output = decide(call, harness)
    if output is not None:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

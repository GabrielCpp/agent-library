#!/usr/bin/env python3
"""Deny a tool call that adds a forbidden shape to a file.

A forbidden shape is a rule with no counter-case, so a machine can hold it. Three are held here.

**A code comment.** `check_no_comments.py` owns that rule and its reasons.

**A clock wait in a test.** A test file gains a call that pauses for a set time: `sleep(seconds)`
under any module, Playwright's `wait_for_timeout`, a `setTimeout` wrapped in a promise. The pause
is a guess at how long the work takes. A loaded machine takes longer than the guess. A pause
inside a loop is poll pacing and passes, and so does `sleep(0)`, which only yields. A Rust source
file is a test file from its `#[cfg(test)]` line down.

**A load-time effect.** Code that runs when a module loads gains a statement that changes
something the module does not own: the import path, the environment, the working directory, a
signal handler, an exit hook, the root logger, a global. Each language has its own load time:

| Language | Runs at load | Entry point that passes |
| --- | --- | --- |
| Python | the top level of a module | `if __name__ == "__main__":` |
| Go | `func init()` and package-level initialisers | `func main()` |
| Java | a `static { }` block | `main` |
| Kotlin | an `init { }` block of an `object`, a top-level initialiser | `main` |
| Rust | a function marked `#[ctor]` | `fn main()` |
| TypeScript, JavaScript | the top level of a module | a file named `setup` or `config` |

Python is read through `ast`. The others go through a line scanner that tracks the open blocks,
so a nested statement is judged by the headers above it.

Each rule is asymmetric the way the comment rule is. A change passes when its count of a shape
does not grow, so a file that already carries one stays editable and a tree never gains another.

The two new shapes are judged on the whole file before and after the change. An `Edit` is applied
to the text on disk first. A Codex patch that updates a file carries fragments only, so the
load-time rule sits out and the clock rule reads the fragments.

Set `CLAUDE_FORBIDDEN_SHAPES_OFF=1` to switch the whole guard off. `CLAUDE_NO_COMMENTS_OFF=1`
switches off the comment rule alone.

Run:
    echo '{"tool_name":"Write","tool_input":{"file_path":"tests/test_x.py","content":"import time\\ntime.sleep(1)\\n"}}' \\
      | python3 ~/.claude/hooks/forbidden-shapes/check_forbidden_shapes.py --hook
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import check_no_comments as comments

TEST_FOLDERS = frozenset(
    {"tests", "test", "__tests__", "e2e", "spec", "specs", "integration_test", "androidTest"}
)
TEST_NAME = re.compile(
    r"^(?:test_.*|conftest\.py|.*_test\.[A-Za-z]+|.*\.(?:test|spec)\.[A-Za-z]+"
    r"|.*(?:Tests?|IT)\.(?:kt|java|swift|cs))$"
)
PYTHON_WAITS = frozenset({"sleep", "wait_for_timeout"})
SPELLED_WAIT = re.compile(
    r"\b(?:sleep|usleep|waitForTimeout|wait_for_timeout)\s*\(\s*(?!0\s*\))"
    r"|\bFuture\.delayed\s*\("
    r"|\bsetTimeout\s*\(\s*(?:resolve|res|r|done)\b"
    r"|\bawait\s+setTimeout\s*\("
    r"|\bcy\.wait\s*\(\s*\d",
    re.IGNORECASE,
)
LOAD_CALLS = frozenset(
    {
        "sys.path.insert",
        "sys.path.append",
        "sys.path.extend",
        "site.addsitedir",
        "os.chdir",
        "os.putenv",
        "os.unsetenv",
        "os.environ.update",
        "os.environ.setdefault",
        "os.environ.pop",
        "os.environ.clear",
        "atexit.register",
        "signal.signal",
        "logging.basicConfig",
    }
)
LOAD_TARGETS = frozenset({"os.environ", "sys.path", "sys.argv", "sys.stdout", "sys.stderr"})
LITERAL = re.compile(r'"(?:\\.|[^"\\])*"|`[^`]*`|\'(?:\\.|[^\'\\])\'')
LINE_COMMENT = re.compile(r"//.*")
LOOP = re.compile(r"^\s*(?:\}\s*)?(?:for|while|loop|do)\b|\.forEach\b|\brepeat\s*\(")
FUNCTION = re.compile(r"\b(?:func|fun|fn|function)\b|[=-]>\s*\{")
RUST_TESTS = "#[cfg(test)]"
JVM_EFFECT = re.compile(
    r"\bSystem\.(?:setProperty|clearProperty|setOut|setErr|setIn)\s*\("
    r"|\baddShutdownHook\s*\(|\bsetDefaultUncaughtExceptionHandler\s*\("
    r"|\b(?:Locale|TimeZone)\.setDefault\s*\("
)
JS_EFFECT = re.compile(
    r"\bprocess\.env(?:\.\w+|\[[^\]]*\])\s*=(?!=)"
    r"|\bprocess\.(?:chdir|on|once)\s*\("
    r"|^\s*(?:globalThis|global|window)\.\w+\s*=(?!=)"
    r"|\bObject\.defineProperty\s*\(\s*(?:globalThis|global|window)\b"
)


@dataclass(frozen=True)
class LoadTime:
    """Where one language runs code at load, and what that code may not do."""

    effect: re.Pattern[str]
    block: re.Pattern[str] | None = None
    parent: re.Pattern[str] | None = None
    top_level: bool = False
    anywhere: bool = False
    exempt_name: re.Pattern[str] | None = None


GO_LOAD = LoadTime(
    effect=re.compile(
        r"\bos\.(?:Setenv|Unsetenv|Clearenv|Chdir)\s*\(|\bsignal\.Notify\s*\(|\bflag\.Parse\s*\("
        r"|\blog\.Set(?:Output|Flags|Prefix)\s*\(|\bslog\.SetDefault\s*\("
        r"|\bhttp\.Handle(?:Func)?\s*\("
    ),
    block=re.compile(r"^\s*func\s+init\s*\(\s*\)"),
    top_level=True,
)
JAVA_LOAD = LoadTime(effect=JVM_EFFECT, block=re.compile(r"^\s*static\s*\{"))
KOTLIN_LOAD = LoadTime(
    effect=JVM_EFFECT,
    block=re.compile(r"^\s*init\s*\{"),
    parent=re.compile(r"\bobject\b"),
    top_level=True,
)
RUST_LOAD = LoadTime(effect=re.compile(r"#\[(?:ctor::)?ctor\b"), anywhere=True)
JS_LOAD = LoadTime(
    effect=JS_EFFECT, top_level=True, exempt_name=re.compile(r"setup|\.config\.", re.IGNORECASE)
)
LOAD_TIME: dict[str, LoadTime] = {
    ".go": GO_LOAD,
    ".java": JAVA_LOAD,
    ".kt": KOTLIN_LOAD,
    ".kts": KOTLIN_LOAD,
    ".rs": RUST_LOAD,
    **dict.fromkeys((".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs"), JS_LOAD),
}


@dataclass(frozen=True)
class Change:
    """One file a tool call writes: its text before and after, whole or as fragments."""

    path: str
    before: str
    after: str
    whole: bool


def _off() -> bool:
    return os.environ.get("CLAUDE_FORBIDDEN_SHAPES_OFF", "") not in ("", "0", "false")


def is_test_file(raw: str) -> bool:
    path = Path(raw)
    return bool(TEST_NAME.match(path.name)) or any(part in TEST_FOLDERS for part in path.parts[:-1])


def _dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _is_zero(call: ast.Call) -> bool:
    return (
        len(call.args) == 1
        and isinstance(call.args[0], ast.Constant)
        and call.args[0].value == 0
        and not isinstance(call.args[0].value, bool)
    )


class _Waits(ast.NodeVisitor):
    """Collects each pause that no loop paces."""

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines
        self.loops = 0
        self.found: list[str] = []

    def _loop(self, node: ast.While | ast.For | ast.AsyncFor) -> None:
        self.loops += 1
        self.generic_visit(node)
        self.loops -= 1

    visit_While = _loop
    visit_For = _loop
    visit_AsyncFor = _loop

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> None:
        held, self.loops = self.loops, 0
        self.generic_visit(node)
        self.loops = held

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function
    visit_Lambda = _function

    def visit_Call(self, node: ast.Call) -> None:
        name = _dotted(node.func).rpartition(".")[2]
        if name in PYTHON_WAITS and not self.loops and not _is_zero(node):
            self.found.append(self.lines[node.lineno - 1].strip())
        self.generic_visit(node)


def _parsed(text: str) -> ast.Module | None:
    try:
        return ast.parse(text)
    except (SyntaxError, ValueError):
        return None


def scanned(text: str) -> list[tuple[str, str, list[str]]]:
    """Each line of a brace language: as written, without literals, and under its open headers.

    A header is the line that opened a block still open. A line that opens a block counts as
    under itself, so a block written on one line is judged like one written on three.
    """
    rows: list[tuple[str, str, list[str]]] = []
    stack: list[str] = []
    for line in text.splitlines():
        bare = LINE_COMMENT.sub("", LITERAL.sub("", line))
        rows.append((line.strip(), bare, [*stack, bare] if "{" in bare else list(stack)))
        for char in bare:
            if char == "{":
                stack.append(bare)
            elif char == "}" and stack:
                stack.pop()
    return rows


def _paced(headers: list[str]) -> bool:
    """Whether a loop encloses the line, inside the function that holds it."""
    for header in reversed(headers):
        if LOOP.search(header):
            return True
        if FUNCTION.search(header):
            return False
    return False


def clock_waits(change: Change, text: str) -> Counter[str] | None:
    """Each pause for a set time that `text` holds, or None where this rule does not apply."""
    suffix = Path(change.path).suffix
    if not is_test_file(change.path):
        if suffix != ".rs" or not change.whole:
            return None
        text = text.split(RUST_TESTS, 1)[1] if RUST_TESTS in text else ""
    if suffix in (".py", ".pyi"):
        tree = _parsed(text)
        if tree is None:
            return Counter(line.strip() for line in text.splitlines() if SPELLED_WAIT.search(line))
        visitor = _Waits(text.splitlines())
        visitor.visit(tree)
        return Counter(visitor.found)
    return Counter(
        line
        for line, bare, headers in scanned(text)
        if SPELLED_WAIT.search(bare) and not _paced(headers)
    )


def _is_entry_block(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and _dotted(node.test.left) == "__name__"
    )


def _load_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """Every statement that runs when the module loads, the entry block left out."""
    found: list[ast.stmt] = []
    for node in body:
        if _is_entry_block(node):
            continue
        found.append(node)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            continue
        for name in ("body", "orelse", "finalbody"):
            found.extend(_load_statements(getattr(node, name, None) or []))
        for handler in getattr(node, "handlers", None) or []:
            found.extend(_load_statements(handler.body))
    return found


def _acts_outside(node: ast.stmt) -> bool:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return any(_dotted(decorator) in LOAD_CALLS for decorator in node.decorator_list)
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        return _dotted(node.value.func) in LOAD_CALLS
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign | ast.Delete):
        targets = list(node.targets)
    elif isinstance(node, ast.AugAssign | ast.AnnAssign):
        targets = [node.target]
    return any(
        _dotted(target.value if isinstance(target, ast.Subscript) else target) in LOAD_TARGETS
        for target in targets
    )


def _runs_at_load(rule: LoadTime, headers: list[str]) -> bool:
    if rule.anywhere or (rule.top_level and not headers):
        return True
    if rule.block is None:
        return False
    return any(
        rule.block.search(header)
        and (rule.parent is None or (depth > 0 and rule.parent.search(headers[depth - 1])))
        for depth, header in enumerate(headers)
    )


def load_effects(change: Change, text: str) -> Counter[str] | None:
    """Each statement of `text` that acts outside its module at load, or None when unjudged."""
    if not change.whole:
        return None
    path = Path(change.path)
    rule = LOAD_TIME.get(path.suffix)
    if rule is not None:
        if rule.exempt_name is not None and rule.exempt_name.search(path.name):
            return None
        return Counter(
            line
            for line, bare, headers in scanned(text)
            if rule.effect.search(bare) and _runs_at_load(rule, headers)
        )
    if path.suffix != ".py":
        return None
    if not text.strip():
        return Counter()
    tree = _parsed(text)
    if tree is None:
        return None
    lines = text.splitlines()
    return Counter(
        lines[node.lineno - 1].strip() for node in _load_statements(tree.body) if _acts_outside(node)
    )


def _quoted(offenders: list[str]) -> str:
    shown = "; ".join(f'"{body[:72]}"' for body in offenders[:3])
    return shown + (f" (and {len(offenders) - 3} more)" if len(offenders) > 3 else "")


def _clock_steer(path: str, offenders: list[str]) -> str:
    return (
        f"Refusing to add a clock wait to the test file {path}: {_quoted(offenders)}. "
        f"A test never waits on the clock. The pause is a guess at how long the work takes, and "
        f"a loaded machine takes longer. Wait on the event the work produces: a line of output, "
        f"a file, a state, a `threading.Event`, an `asyncio.Event`, `expect(locator)`. Give the "
        f"wait a deadline of 30 s or more. Where the work offers no event, poll its condition in "
        f"a loop the condition ends. A fake that must hold its answer blocks on an event the "
        f"test sets. Time the product counts comes from an injected clock the test advances. "
        f"A claim that nothing happened waits for a second piece of work and then asserts the "
        f"first left no trace. Deleting or moving an existing wait is allowed."
    )


def _load_steer(path: str, offenders: list[str]) -> str:
    return (
        f"Refusing to add a load-time effect to {path}: {_quoted(offenders)}. "
        f"Loading a module changes nothing outside it. The change is in place for every test "
        f"that runs after the load and for none before, so a test passes only when some other "
        f"module loaded first. Move the statement into a function. The entry point calls it for "
        f"the product: `main`, or the block under `if __name__ == \"__main__\":`. A test calls "
        f"it from a fixture that undoes it at teardown, such as pytest's `monkeypatch`, Go's "
        f"`t.Setenv` and `t.Chdir`, JUnit's `@BeforeEach` with `@AfterEach`, or `beforeEach` "
        f"with `vi.stubEnv`. A search path goes in the runner's configuration."
    )


SHAPES = ((clock_waits, _clock_steer), (load_effects, _load_steer))


def _on_disk(raw: str) -> str | None:
    try:
        return Path(raw).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _edited(text: str, pairs: list[tuple[str, str]], replace_all: bool) -> str:
    for old, new in pairs:
        text = text.replace(old, new) if replace_all else text.replace(old, new, 1)
    return text


def _edit_change(raw: str, tool_input: dict[str, object]) -> Change | None:
    pairs = comments._edit_pairs(
        tool_input.get("edits"), tool_input.get("old_string"), tool_input.get("new_string")
    )
    if not pairs:
        return None
    existing = _on_disk(raw)
    if existing is None:
        return Change(raw, "\n".join(old for old, _ in pairs), "\n".join(new for _, new in pairs), False)
    return Change(raw, existing, _edited(existing, pairs, tool_input.get("replace_all") is True), True)


def changes(payload: dict[str, object]) -> list[Change]:
    """Every code file a PreToolUse payload writes, with its text before and after."""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return []
    found: list[Change] = []
    command = tool_input.get("command")
    if isinstance(command, str):
        if comments.PATCH_OPENING in command:
            for raw, new_text, old_text in comments.patch_sections(command):
                if old_text is None:
                    found.append(Change(raw, _on_disk(raw) or "", new_text, True))
                else:
                    found.append(Change(raw, old_text, new_text, False))
        for raw, body in comments.heredoc_writes(command):
            found.append(Change(raw, _on_disk(raw) or "", body, True))
    raw = tool_input.get("file_path")
    tool = payload.get("tool_name")
    if isinstance(raw, str) and tool == "Write":
        content = tool_input.get("content")
        if isinstance(content, str):
            found.append(Change(raw, _on_disk(raw) or "", content, True))
    elif isinstance(raw, str) and tool in ("Edit", "MultiEdit"):
        change = _edit_change(raw, tool_input)
        if change is not None:
            found.append(change)
    return [change for change in found if comments.code_suffix(change.path)]


def shape_decision(payload: dict[str, object]) -> str | None:
    """The denial for a payload that grows the count of a clock wait or a load-time effect."""
    for change in changes(payload):
        for count, steer in SHAPES:
            before, after = count(change, change.before), count(change, change.after)
            if before is None or after is None or after.total() <= before.total():
                continue
            return steer(comments._relative(change.path), sorted((after - before).elements()))
    return None


def hook_decision(payload: dict[str, object]) -> str | None:
    """The `permissionDecisionReason` for a PreToolUse payload, or None to let it through."""
    if _off():
        return None
    return comments.hook_decision(payload) or shape_decision(payload)


def main(argv: list[str]) -> int:
    if "--hook" not in argv:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        reason = hook_decision(payload)
    except Exception as error:
        print(f"forbidden-shapes: the check failed and let the call through: {error!r}", file=sys.stderr)
        return 0
    if reason is None:
        return 0
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

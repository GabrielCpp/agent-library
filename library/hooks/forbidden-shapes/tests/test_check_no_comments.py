"""What the comment guard refuses, per language, and the many shapes it must not refuse.

Every case builds its own project under `tmp_path`, because a global hook has no repository
to lean on and a test that read one would only prove the guard works in that one checkout.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from payloads import edit as _edit
from payloads import write as _write

SCRIPT = Path(__file__).resolve().parents[1] / "check_no_comments.py"


@pytest.fixture(scope="module")
def guard() -> Any:
    """The guard, imported from its path.

    Registered in `sys.modules` before `exec_module`, because the module uses `@dataclass`
    under `from __future__ import annotations`, and `dataclasses` resolves the resulting
    string annotations through `sys.modules[cls.__module__]`. Absent, that lookup returns
    None and the decorator dies on `NoneType.__dict__`.
    """
    spec = importlib.util.spec_from_file_location("check_no_comments", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_no_comments"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_NO_COMMENTS_OFF", raising=False)
    monkeypatch.delenv("CLAUDE_NO_COMMENTS_STRICT_DOC", raising=False)


def _bash(command: str) -> dict[str, Any]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_denies_a_new_comment(guard: Any, project: Path) -> None:
    payload = _write(project / "src" / "a.py", "# explain the thing\nx = 1\n")
    reason = guard.hook_decision(payload)
    assert reason is not None
    assert "explain the thing" in reason


def test_allows_rewording_and_deleting(guard: Any, project: Path) -> None:
    """The asymmetry is the design: a tree never gains a comment line."""
    target = project / "src" / "b.py"
    target.write_text("# old wording\nx = 1\n", encoding="utf-8")
    assert guard.hook_decision(_edit(target, "# old wording", "# new wording")) is None
    assert guard.hook_decision(_edit(target, "# old wording\n", "")) is None


def test_denies_a_reword_that_grows_the_comment(guard: Any, project: Path) -> None:
    target = project / "src" / "b2.py"
    target.write_text("# old wording\nx = 1\n", encoding="utf-8")
    edit = _edit(target, "# old wording", "# new wording\n# and a second line")
    assert guard.hook_decision(edit) is not None


def test_allows_code_change_that_carries_comments_through(guard: Any, project: Path) -> None:
    target = project / "src" / "c.py"
    target.write_text("# keeps the lease warm\nvalue = compute()\n", encoding="utf-8")
    edit = _edit(
        target,
        "# keeps the lease warm\nvalue = compute()",
        "# keeps the lease warm\nvalue = compute(retries=3)",
    )
    assert guard.hook_decision(edit) is None


def test_allows_rewriting_a_commented_file_unchanged(guard: Any, project: Path) -> None:
    """Without this, every Write to an existing commented file is denied and the guard dies."""
    target = project / "src" / "d.py"
    body = "# a comment that is already here\nx = 1\n"
    target.write_text(body, encoding="utf-8")
    assert guard.hook_decision(_write(target, body)) is None


def test_duplicating_an_existing_comment_is_an_addition(guard: Any, project: Path) -> None:
    target = project / "src" / "e.py"
    target.write_text("# once\nx = 1\n", encoding="utf-8")
    assert guard.hook_decision(_write(target, "# once\nx = 1\n# once\ny = 2\n")) is not None


def test_a_docstring_is_not_a_comment(guard: Any, project: Path) -> None:
    content = '"""What this module is for, at length.\n\nMore prose.\n"""\n\nx = 1\n'
    assert guard.hook_decision(_write(project / "src" / "f.py", content)) is None


def test_a_hash_inside_a_string_is_a_string(guard: Any, project: Path) -> None:
    content = 'url = "https://example.com/#anchor"\nsep = "#"\ntext = """\n# not a comment\n"""\n'
    assert guard.hook_decision(_write(project / "src" / "g.py", content)) is None


def test_syntax_follows_the_extension(guard: Any, project: Path) -> None:
    """`//` is a comment in Go and integer division in Python. `#` is the reverse."""
    assert guard.hook_decision(_write(project / "src" / "h.py", "half = total // 2\n")) is None
    assert guard.hook_decision(_write(project / "src" / "h.go", "// explain\nvar x = 1\n")) is not None
    assert guard.hook_decision(_write(project / "src" / "i.go", "x := map[string]int{}\n")) is None


def test_a_slash_inside_a_go_raw_string_is_a_string(guard: Any, project: Path) -> None:
    content = 'var pattern = `http://example.com`\nvar q = "a // b"\n'
    assert guard.hook_decision(_write(project / "src" / "j.go", content)) is None


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("a.py", "import os  # noqa: F401\n"),
        ("b.py", "value = cast(x)  # ty: ignore[invalid-argument-type]\n"),
        ("c.py", "value = cast(x)  # pyright: ignore[reportUnknownMemberType]\n"),
        ("d.py", "#!/usr/bin/env python3\nx = 1\n"),
        ("e.py", "# -*- coding: utf-8 -*-\nx = 1\n"),
        ("f.py", "# SPDX-License-Identifier: MIT\nx = 1\n"),
        ("g.py", "# Copyright (c) 2026 Someone\nx = 1\n"),
        ("h.go", "//go:build linux\npackage main\n"),
        ("i.go", "// Code generated by protoc. DO NOT EDIT.\npackage main\n"),
        ("j.ts", "// eslint-disable-next-line no-console\nconsole.log(1)\n"),
        ("k.ts", "// @ts-expect-error upstream types are wrong\nconst x = f()\n"),
        ("l.c", "#pragma once\nint x;\n"),
    ],
)
def test_machine_read_lines_are_not_comments(
    guard: Any, project: Path, name: str, content: str
) -> None:
    assert guard.hook_decision(_write(project / "src" / name, content)) is None


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("a.rs", "/// The width of the frame.\npub struct Frame;\n"),
        ("b.rs", "//! Crate-level documentation.\npub struct Frame;\n"),
        ("c.ts", "/** The width of the frame. */\nexport const w = 1\n"),
        ("d.java", "/**\n * What this class does.\n */\nclass A {}\n"),
        ("e.dart", "/// What this widget builds.\nclass A {}\n"),
    ],
)
def test_the_languages_doc_form_is_allowed(
    guard: Any, project: Path, name: str, content: str
) -> None:
    """The cross-language reading of "a docstring is fine": the construct the language's own
    doc tooling reads is documentation, and an ordinary comment is not."""
    assert guard.hook_decision(_write(project / "src" / name, content)) is None


def test_strict_doc_denies_the_doc_form_too(
    guard: Any, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_NO_COMMENTS_STRICT_DOC", "1")
    payload = _write(project / "src" / "a.rs", "/// The width of the frame.\npub struct Frame;\n")
    assert guard.hook_decision(payload) is not None


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("a.py", "x = 1  # trailing prose\n"),
        ("b.ts", "const x = 1 // trailing prose\n"),
        ("c.ts", "/* a block of prose */\nconst x = 1\n"),
        ("d.css", "/* why this margin exists */\nbody { margin: 0 }\n"),
        ("e.sql", "-- why this index exists\nCREATE INDEX i ON t (c);\n"),
        ("f.lua", "-- why this loop exists\nfor i = 1, 3 do end\n"),
        ("g.rb", "# why this method exists\ndef a; end\n"),
        ("h.rs", "// an ordinary comment, not a doc comment\npub struct Frame;\n"),
        ("i.php", "// an ordinary comment\n$x = 1;\n"),
        ("j.hs", "-- an ordinary comment\nmain = return ()\n"),
    ],
)
def test_denies_a_comment_in_each_language(
    guard: Any, project: Path, name: str, content: str
) -> None:
    assert guard.hook_decision(_write(project / "src" / name, content)) is not None


@pytest.mark.parametrize(
    "name",
    [
        "pyproject.toml",
        "Makefile",
        "Dockerfile",
        "docker-compose.yml",
        "README.md",
        "docs/note.md",
        "settings.json",
        "main.tf",
        "deploy.sh",
        ".eslintrc.js",
    ],
)
def test_config_and_docs_are_out_of_scope(guard: Any, project: Path, name: str) -> None:
    """A comment in a build table is the only documentation that format admits, and `.md` is
    the destination rather than a place to police."""
    target = project / name
    target.parent.mkdir(parents=True, exist_ok=True)
    assert guard.hook_decision(_write(target, "# a comment\nkey = 1\n")) is None


@pytest.mark.parametrize(
    "relative",
    [
        "node_modules/pkg/index.js",
        "vendor/lib/thing.go",
        ".venv/lib/python3.12/site-packages/x.py",
        "dist/bundle.js",
        "target/debug/build.rs",
        "src/migrations/0001_init.py",
    ],
)
def test_vendored_and_generated_trees_are_skipped(
    guard: Any, project: Path, relative: str
) -> None:
    target = project / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    assert guard.hook_decision(_write(target, "// a comment\nvar x = 1\n")) is None


def test_a_generated_file_marker_exempts_the_whole_file(guard: Any, project: Path) -> None:
    content = "// Code generated by thing. DO NOT EDIT.\n\n// a comment\nvar x = 1\n"
    assert guard.hook_decision(_write(project / "src" / "a.go", content)) is None


def test_a_bash_heredoc_write_is_judged(guard: Any, project: Path) -> None:
    """`cat > x.py <<EOF` is a Write wearing a Bash costume."""
    target = project / "src" / "a.py"
    command = f"cat > {target} <<'EOF'\n# explain the thing\nx = 1\nEOF"
    reason = guard.hook_decision(_bash(command))
    assert reason is not None
    assert "explain the thing" in reason


def test_a_bash_heredoc_write_of_clean_code_is_allowed(guard: Any, project: Path) -> None:
    target = project / "src" / "a.py"
    command = f'cat > {target} <<\'EOF\'\n"""A docstring."""\n\nx = 1\nEOF'
    assert guard.hook_decision(_bash(command)) is None


def test_a_bash_heredoc_tee_is_judged(guard: Any, project: Path) -> None:
    target = project / "src" / "b.ts"
    command = f"cat <<'EOF' | tee {target}\n// explain the thing\nconst x = 1\nEOF"
    assert guard.hook_decision(_bash(command)) is not None


@pytest.mark.parametrize(
    "command",
    [
        "grep -rn '# TODO' src/",
        "git commit -m 'fix: a thing'",
        "cat > notes.md <<'EOF'\n# A heading\nEOF",
        "python3 -c 'print(1)'",
        "cat src/a.py",
    ],
)
def test_ordinary_bash_is_untouched(guard: Any, project: Path, command: str) -> None:
    assert guard.hook_decision(_bash(command)) is None


def test_the_denial_names_a_destination_that_exists(guard: Any, project: Path) -> None:
    """A message a reader has to interpret is a message that gets ignored."""
    (project / "docs").mkdir()
    reason = guard.hook_decision(_write(project / "src" / "a.py", "# prose\nx = 1\n"))
    assert reason is not None
    assert "README.md" in reason or "docs/" in reason


def test_project_root_comes_from_the_nearest_git(guard: Any, project: Path) -> None:
    deep = project / "src" / "deep" / "deeper"
    deep.mkdir(parents=True)
    assert guard.project_root(deep / "a.py") == project


def test_project_root_falls_back_to_the_harness_variable(
    guard: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    stray = tmp_path / "nowhere"
    stray.mkdir()
    assert guard.project_root(stray / "a.py") in (tmp_path, stray)


def test_the_off_switch_disables_everything(
    guard: Any, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_NO_COMMENTS_OFF", "1")
    assert guard.hook_decision(_write(project / "src" / "a.py", "# prose\nx = 1\n")) is None


def test_a_malformed_payload_never_blocks_a_call(guard: Any) -> None:
    """A hook that errors on an unexpected payload blocks every call it cannot parse."""
    assert guard.hook_decision({}) is None
    assert guard.hook_decision({"tool_name": "Write", "tool_input": "not a dict"}) is None
    assert guard.hook_decision({"tool_name": "Write", "tool_input": {"file_path": 7}}) is None
    assert guard.hook_decision({"tool_name": "Read", "tool_input": {"file_path": "a.py"}}) is None
    assert guard.hook_decision({"tool_name": "Bash", "tool_input": {"command": 7}}) is None


def test_an_unparseable_edit_fragment_still_compares(guard: Any, project: Path) -> None:
    """`tokenize` fails on a fragment, and the fallback scanner has to carry the comparison."""
    target = project / "src" / "a.py"
    target.write_text("def f():\n    return 1\n", encoding="utf-8")
    edit = _edit(target, "    return 1", "    # explain\n    return 2")
    assert guard.hook_decision(edit) is not None


def test_multiedit_judges_every_pair(guard: Any, project: Path) -> None:
    target = project / "src" / "a.py"
    target.write_text("a = 1\nb = 2\n", encoding="utf-8")
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(target),
            "edits": [
                {"old_string": "a = 1", "new_string": "a = 11"},
                {"old_string": "b = 2", "new_string": "# explain\nb = 22"},
            ],
        },
    }
    assert guard.hook_decision(payload) is not None


def test_hook_mode_emits_a_deny_decision(project: Path) -> None:
    """End to end, over the wire the hook actually speaks."""
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--hook"],
        input=json.dumps(_write(project / "src" / "a.py", "# prose\nx = 1\n")),
        capture_output=True,
        text=True,
        check=True,
    )
    decision = json.loads(done.stdout)["hookSpecificOutput"]
    assert decision["hookEventName"] == "PreToolUse"
    assert decision["permissionDecision"] == "deny"


def test_hook_mode_survives_garbage_stdin() -> None:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), "--hook"],
        input="}{ not json",
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == ""


def test_the_guard_obeys_its_own_rule(guard: Any) -> None:
    """A guard that breaks its own rule is an argument for ignoring it."""
    body = SCRIPT.read_text(encoding="utf-8")
    assert guard.hook_decision(_write(SCRIPT, body)) is None
    assert sum(guard.python_comment_lines(body).values()) == 0


def test_every_python_file_here_tokenizes_exactly(guard: Any) -> None:
    """If the exact reader ever stops applying to Python, this fails rather than degrading."""
    for path in SCRIPT.parent.rglob("*.py"):
        assert guard.python_comment_lines(path.read_text(encoding="utf-8")) is not None, path


def test_a_block_comment_does_not_swallow_the_code_after_it(guard: Any, project: Path) -> None:
    """`catch { /* ignore */ }` ends in a brace, not in the closer.

    Reading the body with `removesuffix` left it as `ignore */ }`, which both mis-reports the
    comment and, to anything deleting by that span, takes the brace with it.
    """
    line = "try { localStorage.clear(); } catch { /* ignore */ }\n"
    found = guard.comments_of(line, ".ts", whole_file=True)
    assert list(found) == ["ignore"]


def test_a_generated_header_exempts_the_file(guard: Any, project: Path) -> None:
    """A generator's own header is the file saying who owns it."""
    for header in (
        "// Generated by React Router",
        "// @generated",
        "/* DO NOT EDIT */",
        "// This file is generated",
    ):
        content = f"{header}\n\n// a comment nobody wrote by hand\nexport const a = 1\n"
        assert guard.hook_decision(_write(project / "src" / "a.ts", content)) is None, header


def test_a_url_in_a_template_literal_is_not_a_comment(guard: Any, project: Path) -> None:
    """A backtick is a string delimiter in the JS family, so `https://x` is a string."""
    content = "const upstream = `https://${host}/a`\nconsole.log(`at ${a}//${b}`)\n"
    assert guard.hook_decision(_write(project / "src" / "a.mjs", content)) is None


def test_an_exempt_block_covers_its_own_continuation_lines(guard: Any, project: Path) -> None:
    """A `/*!` license block and a `/**` docblock are exempt whole, not just on line one.

    Judged line by line, the second line of a minified stylesheet's license header reads as a
    comment, and `* see http://x` inside a docblock opens one at the URL's slashes.
    """
    license_block = "/*!\n * Animate.css - http://daneden.me/animate\n * MIT License\n */\nbody{margin:0}\n"
    assert guard.hook_decision(_write(project / "src" / "a.css", license_block)) is None
    docblock = "/**\n * The width.\n * @see http://example.com/docs\n */\nexport const w = 1\n"
    assert guard.hook_decision(_write(project / "src" / "b.ts", docblock)) is None


def test_an_ordinary_block_still_counts_every_line(guard: Any, project: Path) -> None:
    content = "/*\n * why this exists\n * and more prose\n */\nexport const w = 1\n"
    reason = guard.hook_decision(_write(project / "src" / "c.ts", content))
    assert reason is not None
    assert "why this exists" in reason


def test_a_regex_literal_is_not_a_comment(guard: Any, project: Path) -> None:
    """Telling `/regex/` from division needs the preceding token, not quote state."""
    content = (
        'const stem = file.replace(/\\.ts$/, "")\n'
        "await page.waitForURL(/projects/, { timeout: 20000 })\n"
        "const ok = e.match(/500.*GET.*\\/projects\\/.*\\/x\\//)\n"
        "const only = /^https:/i.test(url)\n"
    )
    assert guard.hook_decision(_write(project / "src" / "a.ts", content)) is None


def test_division_is_still_division(guard: Any, project: Path) -> None:
    """The regex rule must not swallow a real trailing comment after a division."""
    reason = guard.hook_decision(
        _write(project / "src" / "b.ts", "const ratio = total / count // rounds down\n")
    )
    assert reason is not None
    assert "rounds down" in reason
    assert guard.hook_decision(_write(project / "src" / "c.ts", "const p = a / b / c\n")) is None


def test_a_regex_containing_a_slash_in_a_class_is_one_literal(guard: Any, project: Path) -> None:
    content = "const re = /[/]+/g\nconst also = /a[^/]*\\/b/\n"
    assert guard.hook_decision(_write(project / "src" / "d.ts", content)) is None


def test_a_multiline_template_literal_holding_comment_text_is_a_string(
    guard: Any, project: Path
) -> None:
    """A fixture's backticked source is data, and a JS template literal spans lines."""
    content = (
        "const source = `\n"
        "  // await route.fulfill({ status: 200 })\n"
        "  /* page.route('/api/x', (r) => r.fulfill({})) */\n"
        "`\n"
        "export const s = source\n"
    )
    assert guard.hook_decision(_write(project / "src" / "a.mjs", content)) is None


def test_a_go_raw_string_spans_lines_too(guard: Any, project: Path) -> None:
    content = "package a\n\nvar q = `\n// not a comment\nSELECT 1\n`\n"
    assert guard.hook_decision(_write(project / "src" / "a.go", content)) is None


def test_a_comment_after_a_closed_template_literal_still_counts(guard: Any, project: Path) -> None:
    content = "const s = `\n  a\n`\nexport const b = 1 // why b\n"
    reason = guard.hook_decision(_write(project / "src" / "b.mjs", content))
    assert reason is not None
    assert "why b" in reason


def patch_payload(body: str) -> dict[str, object]:
    return {
        "tool_name": "apply_patch",
        "tool_input": {"command": f"*** Begin Patch\n{body}\n*** End Patch\n"},
    }


def test_a_codex_patch_adding_a_comment_is_denied(guard: Any) -> None:
    body = "*** Update File: x.py\n@@\n a = 1\n+# why\n b = 2"
    assert guard.hook_decision(patch_payload(body)) is not None


def test_a_codex_patch_creating_a_commented_file_is_denied(guard: Any, tmp_path: Path) -> None:
    body = f"*** Add File: {tmp_path}/new.py\n+# why\n+a = 1"
    assert guard.hook_decision(patch_payload(body)) is not None


def test_a_codex_patch_rewording_a_comment_passes(guard: Any) -> None:
    body = "*** Update File: x.py\n@@\n-# stale\n+# fresh\n a = 1"
    assert guard.hook_decision(patch_payload(body)) is None


def test_a_codex_patch_of_plain_code_passes(guard: Any) -> None:
    body = "*** Update File: x.py\n@@\n-a = 1\n+a = 2"
    assert guard.hook_decision(patch_payload(body)) is None


def test_a_codex_patch_deleting_a_file_after_an_edit_judges_only_the_edit(guard: Any) -> None:
    body = "*** Delete File: gone.py\n*** Update File: x.py\n@@\n-a = 1\n+a = 2"
    assert guard.hook_decision(patch_payload(body)) is None


def test_a_codex_patch_to_a_config_format_is_not_judged(guard: Any) -> None:
    body = "*** Update File: pyproject.toml\n@@\n+# why"
    assert guard.hook_decision(patch_payload(body)) is None

"""What the two shapes beside the comment rule refuse, and the shapes they must let through.

Every case builds its own project under `tmp_path`, as the comment guard's cases do.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from payloads import edit as _edit
from payloads import write as _write

FOLDER = Path(__file__).resolve().parents[1]


@pytest.fixture
def guard(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.syspath_prepend(str(FOLDER))
    monkeypatch.delenv("CLAUDE_FORBIDDEN_SHAPES_OFF", raising=False)
    monkeypatch.delenv("CLAUDE_NO_COMMENTS_OFF", raising=False)
    return importlib.import_module("check_forbidden_shapes")


SLEEPING_TEST = "import time\n\n\ndef test_it():\n    start()\n    time.sleep(0.5)\n    assert done()\n"


@pytest.mark.parametrize(
    "call",
    ["time.sleep(0.5)", "sleep(seconds)", "await asyncio.sleep(1)", "page.wait_for_timeout(200)"],
)
def test_denies_a_clock_wait_in_a_python_test(guard: Any, project: Path, call: str) -> None:
    body = f"async def test_it(page, seconds):\n    {call}\n    assert done()\n"
    reason = guard.hook_decision(_write(project / "tests" / "test_a.py", body))
    assert reason is not None
    assert "clock wait" in reason
    assert call in reason


def test_a_test_file_is_known_by_its_name_outside_a_tests_folder(guard: Any, project: Path) -> None:
    assert guard.hook_decision(_write(project / "src" / "test_a.py", SLEEPING_TEST)) is not None
    assert guard.hook_decision(_write(project / "src" / "conftest.py", SLEEPING_TEST)) is not None


def test_allows_a_sleep_in_product_code(guard: Any, project: Path) -> None:
    body = "import time\n\n\ndef backoff():\n    time.sleep(0.5)\n"
    assert guard.hook_decision(_write(project / "src" / "retry.py", body)) is None


def test_allows_a_pause_that_paces_a_poll_loop(guard: Any, project: Path) -> None:
    body = (
        "import time\n\n\ndef wait_until(condition, deadline):\n"
        "    while not condition():\n        assert time.monotonic() < deadline\n"
        "        time.sleep(0.01)\n"
    )
    assert guard.hook_decision(_write(project / "tests" / "support.py", body)) is None


def test_a_function_defined_inside_a_loop_is_not_paced_by_it(guard: Any, project: Path) -> None:
    body = (
        "import time\n\nfor case in CASES:\n"
        "    def test_case():\n        time.sleep(1)\n"
    )
    assert guard.hook_decision(_write(project / "tests" / "test_b.py", body)) is not None


def test_allows_a_zero_sleep_that_only_yields(guard: Any, project: Path) -> None:
    body = "import asyncio\n\n\nasync def test_it():\n    await asyncio.sleep(0)\n"
    assert guard.hook_decision(_write(project / "tests" / "test_c.py", body)) is None


def test_allows_a_sleep_inside_a_string(guard: Any, project: Path) -> None:
    body = 'CHILD = "import time; time.sleep(60)"\n\n\ndef test_it():\n    run(CHILD)\n'
    assert guard.hook_decision(_write(project / "tests" / "test_d.py", body)) is None


def test_an_edit_is_judged_on_the_whole_file(guard: Any, project: Path) -> None:
    target = project / "tests" / "test_e.py"
    target.write_text(SLEEPING_TEST, encoding="utf-8")
    assert guard.hook_decision(_edit(target, "start()", "begin()")) is None
    assert guard.hook_decision(_edit(target, "time.sleep(0.5)", "time.sleep(2)")) is None
    assert guard.hook_decision(_edit(target, "    time.sleep(0.5)\n", "")) is None
    grown = _edit(target, "start()", "start()\n    time.sleep(1)")
    assert guard.hook_decision(grown) is not None


def test_an_edit_that_adds_a_pause_inside_an_existing_loop_passes(guard: Any, project: Path) -> None:
    target = project / "tests" / "test_f.py"
    target.write_text("def wait(ready):\n    while not ready():\n        pass\n", encoding="utf-8")
    assert guard.hook_decision(_edit(target, "        pass", "        time.sleep(0.01)")) is None


def test_rewriting_a_file_that_already_sleeps_passes(guard: Any, project: Path) -> None:
    target = project / "tests" / "test_g.py"
    target.write_text(SLEEPING_TEST, encoding="utf-8")
    assert guard.hook_decision(_write(target, SLEEPING_TEST.replace("done", "finished"))) is None


@pytest.mark.parametrize(
    ("name", "line"),
    [
        ("a.spec.ts", "await page.waitForTimeout(500);"),
        ("a.test.ts", "await new Promise((resolve) => setTimeout(resolve, 500));"),
        ("a_test.go", "time.Sleep(2 * time.Second)"),
        ("ATest.kt", "Thread.sleep(500)"),
        ("a_test.dart", "await Future.delayed(const Duration(seconds: 1));"),
    ],
)
def test_denies_a_clock_wait_spelled_in_another_language(
    guard: Any, project: Path, name: str, line: str
) -> None:
    reason = guard.hook_decision(_write(project / "src" / name, f"{line}\n"))
    assert reason is not None
    assert "clock wait" in reason


def test_allows_a_timer_that_is_not_a_wait(guard: Any, project: Path) -> None:
    body = "setTimeout(() => button.click(), 0);\nvi.advanceTimersByTime(500);\n"
    assert guard.hook_decision(_write(project / "src" / "a.test.ts", body)) is None


def test_a_heredoc_that_writes_a_sleeping_test_is_denied(guard: Any, project: Path) -> None:
    command = f"cat > {project}/tests/test_h.py <<'EOF'\n{SLEEPING_TEST}EOF"
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    assert guard.hook_decision(payload) is not None


def test_a_patch_that_adds_a_pause_to_a_test_is_denied(guard: Any, project: Path) -> None:
    patch = (
        "*** Begin Patch\n"
        f"*** Update File: {project}/tests/test_i.py\n"
        "@@\n     start()\n+    time.sleep(1)\n     assert done()\n"
        "*** End Patch\n"
    )
    payload = {"tool_name": "apply_patch", "tool_input": {"command": patch}}
    assert guard.hook_decision(payload) is not None


@pytest.mark.parametrize(
    "statement",
    [
        "sys.path.insert(0, str(HERE))",
        "sys.path.append(str(HERE))",
        'os.environ["MODE"] = "test"',
        'os.environ.setdefault("MODE", "test")',
        "os.chdir(HERE)",
        "atexit.register(close)",
        "signal.signal(signal.SIGTERM, stop)",
        "logging.basicConfig(level=logging.INFO)",
        'del os.environ["MODE"]',
    ],
)
def test_denies_a_load_time_effect(guard: Any, project: Path, statement: str) -> None:
    body = f"import os\nimport sys\n\nHERE = 1\n{statement}\n"
    for target in (project / "src" / "tool.py", project / "tests" / "conftest.py"):
        reason = guard.hook_decision(_write(target, body))
        assert reason is not None
        assert "load-time effect" in reason
        assert statement in reason


def test_denies_a_load_time_effect_under_a_top_level_branch(guard: Any, project: Path) -> None:
    body = "import sys\n\ntry:\n    import fast\nexcept ImportError:\n    sys.path.append('vendor')\n"
    assert guard.hook_decision(_write(project / "src" / "a.py", body)) is not None
    decorated = "import atexit\n\n\n@atexit.register\ndef close():\n    pass\n"
    assert guard.hook_decision(_write(project / "src" / "b.py", decorated)) is not None


def test_allows_the_effect_inside_a_function_or_the_entry_block(guard: Any, project: Path) -> None:
    body = (
        "import logging\nimport os\nimport sys\n\n\n"
        "def main():\n    logging.basicConfig(level=logging.INFO)\n    os.chdir('/')\n\n\n"
        'if __name__ == "__main__":\n    sys.path.insert(0, ".")\n    main()\n'
    )
    assert guard.hook_decision(_write(project / "src" / "cli.py", body)) is None


def test_allows_a_module_that_builds_its_own_values(guard: Any, project: Path) -> None:
    body = (
        "import logging\nimport os\nimport re\n\n"
        "LOG = logging.getLogger(__name__)\nPATTERN = re.compile('a+')\n"
        "HOME = os.environ.get('HOME')\nTABLE = {}\nTABLE.update(a=1)\n"
        "pytest.importorskip('playwright')\n"
    )
    assert guard.hook_decision(_write(project / "src" / "values.py", body)) is None


def test_an_edit_inside_a_function_is_not_read_as_top_level(guard: Any, project: Path) -> None:
    target = project / "src" / "cli.py"
    target.write_text("import os\n\n\ndef main():\n    run()\n", encoding="utf-8")
    assert guard.hook_decision(_edit(target, "    run()", "    os.chdir('/')\n    run()")) is None
    top = _edit(target, "import os\n", "import os\nos.chdir('/')\n")
    assert guard.hook_decision(top) is not None


def test_a_file_that_already_acts_on_load_stays_editable(guard: Any, project: Path) -> None:
    target = project / "src" / "old.py"
    target.write_text("import sys\nsys.path.insert(0, 'a')\nX = 1\n", encoding="utf-8")
    assert guard.hook_decision(_edit(target, "X = 1", "X = 2")) is None
    assert guard.hook_decision(_edit(target, "sys.path.insert(0, 'a')\n", "")) is None
    assert guard.hook_decision(_edit(target, "X = 1", "X = 1\nsys.path.append('b')")) is not None


def test_a_file_that_does_not_parse_is_left_alone(guard: Any, project: Path) -> None:
    body = "import sys\nsys.path.insert(0, 'a')\ndef broken(:\n"
    assert guard.hook_decision(_write(project / "src" / "broken.py", body)) is None


def test_the_comment_rule_still_holds_and_is_asked_first(guard: Any, project: Path) -> None:
    body = "# explain the thing\nimport time\ntime.sleep(1)\n"
    reason = guard.hook_decision(_write(project / "tests" / "test_j.py", body))
    assert reason is not None
    assert "explain the thing" in reason


def test_the_comment_switch_leaves_the_other_shapes_on(
    guard: Any, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_NO_COMMENTS_OFF", "1")
    body = "# explain the thing\nX = 1\n"
    assert guard.hook_decision(_write(project / "src" / "a.py", body)) is None
    assert guard.hook_decision(_write(project / "tests" / "test_k.py", SLEEPING_TEST)) is not None
    command = f"cat > {project}/tests/test_l.py <<'EOF'\n{SLEEPING_TEST}EOF"
    assert guard.hook_decision({"tool_name": "Bash", "tool_input": {"command": command}}) is not None


def test_the_whole_guard_switches_off(
    guard: Any, project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_FORBIDDEN_SHAPES_OFF", "1")
    body = "# explain the thing\nimport time\ntime.sleep(1)\n"
    assert guard.hook_decision(_write(project / "tests" / "test_m.py", body)) is None


def test_the_installed_command_denies_through_stdin(project: Path) -> None:
    payload = _write(project / "tests" / "test_n.py", SLEEPING_TEST)
    result = subprocess.run(
        [sys.executable, str(FOLDER / "check_forbidden_shapes.py"), "--hook"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        env={"PATH": "/usr/bin:/bin"},
    )
    assert result.returncode == 0, result.stderr
    decision = json.loads(result.stdout)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "clock wait" in decision["permissionDecisionReason"]


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("a_test.go", "func TestIt(t *testing.T) {\n\tstart()\n\ttime.Sleep(time.Second)\n}\n"),
        ("src/test/java/AIT.java", "class AIT {\n  void it() throws Exception {\n    Thread.sleep(500);\n  }\n}\n"),
        ("src/test/java/ATest.java", "class ATest {\n  void it() {\n    TimeUnit.SECONDS.sleep(1);\n  }\n}\n"),
        ("ATest.kt", "class ATest {\n  fun it() {\n    Thread.sleep(500)\n  }\n}\n"),
        ("tests/it.rs", "#[test]\nfn it() {\n    std::thread::sleep(Duration::from_secs(1));\n}\n"),
        ("a.test.ts", "it('works', async () => {\n  await sleep(500);\n});\n"),
        ("a.test.ts", "import { setTimeout } from 'timers/promises';\nawait setTimeout(500);\n"),
    ],
)
def test_denies_a_clock_wait_in_each_supported_language(
    guard: Any, project: Path, name: str, body: str
) -> None:
    target = project / "pkg" / name
    reason = guard.hook_decision(_write(target, body))
    assert reason is not None
    assert "clock wait" in reason


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("a_test.go", "func waitFor(ok func() bool) {\n\tfor !ok() {\n\t\ttime.Sleep(time.Millisecond)\n\t}\n}\n"),
        ("a_test.go", "func waitFor(ok func() bool) {\n\tfor !ok() { time.Sleep(time.Millisecond) }\n}\n"),
        ("ATest.java", "class ATest {\n  void await() {\n    while (!ok()) {\n      Thread.sleep(5);\n    }\n  }\n}\n"),
        ("ATest.java", "class ATest {\n  void await() {\n    do {\n      Thread.sleep(5);\n    } while (!ok());\n  }\n}\n"),
        ("ATest.kt", "fun await(ok: () -> Boolean) {\n  while (!ok()) {\n    Thread.sleep(5)\n  }\n}\n"),
        ("tests/it.rs", "fn wait_for(ok: impl Fn() -> bool) {\n    while !ok() {\n        thread::sleep(TICK);\n    }\n}\n"),
        ("a.test.ts", "async function waitFor(ok: () => boolean) {\n  while (!ok()) {\n    await sleep(5);\n  }\n}\n"),
    ],
)
def test_allows_poll_pacing_in_each_supported_language(
    guard: Any, project: Path, name: str, body: str
) -> None:
    assert guard.hook_decision(_write(project / "pkg" / name, body)) is None


def test_a_function_literal_inside_a_loop_is_not_paced_by_it(guard: Any, project: Path) -> None:
    body = (
        "func TestAll(t *testing.T) {\n\tfor _, c := range cases {\n"
        "\t\tt.Run(c.name, func(t *testing.T) {\n\t\t\ttime.Sleep(time.Second)\n\t\t})\n\t}\n}\n"
    )
    assert guard.hook_decision(_write(project / "pkg" / "a_test.go", body)) is not None


def test_a_wait_named_in_a_string_is_not_a_wait(guard: Any, project: Path) -> None:
    body = 'func TestIt(t *testing.T) {\n\trun("sleep(5)")\n}\n'
    assert guard.hook_decision(_write(project / "pkg" / "a_test.go", body)) is None


def test_a_rust_source_file_is_a_test_file_below_its_test_marker(guard: Any, project: Path) -> None:
    product = "fn backoff() {\n    thread::sleep(TICK);\n}\n"
    target = project / "src" / "lib.rs"
    assert guard.hook_decision(_write(target, product)) is None
    tested = product + "\n#[cfg(test)]\nmod tests {\n    #[test]\n    fn it() {\n        thread::sleep(TICK);\n    }\n}\n"
    assert guard.hook_decision(_write(target, tested)) is not None


@pytest.mark.parametrize(
    ("name", "body", "shown"),
    [
        ("a.go", 'func init() {\n\tos.Setenv("MODE", "test")\n}\n', "os.Setenv"),
        ("a.go", "func init() {\n\tif debug {\n\t\tlog.SetOutput(os.Stderr)\n\t}\n}\n", "log.SetOutput"),
        ("a.go", 'var _ = os.Chdir("/")\n', "os.Chdir"),
        ("A.java", 'class A {\n  static {\n    System.setProperty("a", "b");\n  }\n}\n', "System.setProperty"),
        ("A.java", 'class A {\n  static { Locale.setDefault(Locale.ROOT); }\n}\n', "Locale.setDefault"),
        ("A.kt", 'object A {\n  init {\n    System.setProperty("a", "b")\n  }\n}\n', "System.setProperty"),
        ("A.kt", 'val set = System.setProperty("a", "b")\n', "System.setProperty"),
        ("a.rs", "#[ctor]\nfn before_main() {\n    start();\n}\n", "#[ctor]"),
        ("a.ts", 'process.env.MODE = "test";\n', "process.env.MODE"),
        ("a.ts", 'process.on("exit", close);\n', "process.on"),
        ("a.ts", "globalThis.fetch = fake;\n", "globalThis.fetch"),
    ],
)
def test_denies_a_load_time_effect_in_each_supported_language(
    guard: Any, project: Path, name: str, body: str, shown: str
) -> None:
    reason = guard.hook_decision(_write(project / "src" / name, body))
    assert reason is not None
    assert "load-time effect" in reason
    assert shown in reason


@pytest.mark.parametrize(
    ("name", "body"),
    [
        ("a.go", 'func main() {\n\tflag.Parse()\n\tos.Setenv("MODE", "run")\n}\n'),
        ("a.go", "func init() {\n\ttable = build()\n}\n"),
        ("A.java", 'class A {\n  public static void main(String[] args) {\n    System.setProperty("a", "b");\n  }\n}\n'),
        ("A.java", "class A {\n  static {\n    TABLE = build();\n  }\n}\n"),
        ("A.kt", 'class A {\n  init {\n    System.setProperty("a", "b")\n  }\n}\n'),
        ("A.kt", 'fun main() {\n  System.setProperty("a", "b")\n}\n'),
        ("a.rs", 'fn main() {\n    std::env::set_var("A", "b");\n}\n'),
        ("a.ts", 'export function start() {\n  process.env.MODE = "run";\n}\n'),
        ("a.ts", 'if (process.env.MODE === "run") {\n  start();\n}\nconst mode = process.env.MODE;\n'),
        ("vitest.setup.ts", "globalThis.fetch = fake;\n"),
    ],
)
def test_allows_the_same_calls_outside_load_time(
    guard: Any, project: Path, name: str, body: str
) -> None:
    assert guard.hook_decision(_write(project / "src" / name, body)) is None

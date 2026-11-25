---
name: rust-testing
description: "Rust tests: cfg(test) unit tests, integration tests, fakes, tokio async tests, axum router tests, assert_cmd CLI tests. Load when adding or changing a test, fake or harness, clippy rejects unwrap in a test file, or choosing a proving test."
applyTo: '**/tests/**/*.rs,**/testing.rs'
tags: [rust, backend, cli, tests]
---

# Testing

The methodology is {{ skill_link("testing-design") }} and {{ skill_link("testing-component") }}. This skill states where each test lives in a Cargo workspace and how it is written.

## Where a test goes

| Test | Location | Proves |
|---|---|---|
| Service | `#[cfg(test)] mod tests` at the foot of `service.rs` | A rule of the domain, over fakes |
| Adapter | `#[cfg(test)] mod tests` at the foot of the adapter file | The real file or database round trip, in a temp directory |
| API | `crates/api/tests/<resource>.rs` | Status, headers and body of each route, through the real router |
| CLI `run` | `#[cfg(test)] mod tests` at the foot of `run.rs` | The exact output text of each command |
| CLI binary | `crates/cli/tests/cli.rs` | Exit codes, stdout and stderr of the built program |
| Desktop | See {{ skill_link("rust-desktop") }} | Presenter state and rendered elements |

- A unit test module sees the private items of its file through `use super::*;`.
- A file in `tests/` is a separate crate. It sees the public API of the library alone, which is why each host has a `lib.rs`.

## Service test

```rust
#[cfg(test)]
mod tests {
    use chrono::{TimeZone, Utc};

    use super::*;
    use crate::testing::{FixedClock, MemoryTaskRepository};

    fn service() -> TaskService {
        let clock = FixedClock(Utc.with_ymd_and_hms(2026, 1, 2, 3, 4, 5).unwrap());
        TaskService::new(Arc::new(MemoryTaskRepository::default()), Arc::new(clock))
    }

    #[tokio::test]
    async fn add_rejects_a_blank_title_and_stores_nothing() {
        let tasks = service();

        let error = tasks.add("   ").await.unwrap_err();

        assert!(matches!(error, TaskError::InvalidTitle));
        assert_eq!(tasks.list().await.unwrap(), vec![]);
    }
}
```

- Mark an async test `#[tokio::test]`. Each test gets its own runtime.
- Build the service through a helper that wires the fakes with the same `new` as production.
- Name a test as a sentence about behaviour. The name is the failure message.
- Assert on an error variant with `matches!`. Assert on values with `assert_eq!`, which prints both sides.
- Inject a `FixedClock` and assert on the exact timestamp. Keep `sleep` and the wall clock out of tests.

## Fakes

```rust
#[derive(Default)]
pub struct MemoryTaskRepository {
    tasks: Mutex<HashMap<TaskId, Task>>,
}

#[async_trait]
impl TaskRepository for MemoryTaskRepository {
    async fn save(&self, task: &Task) -> Result<(), TaskError> {
        let mut tasks = self.tasks.lock().unwrap_or_else(PoisonError::into_inner);
        tasks.insert(task.id, task.clone());
        Ok(())
    }
}
```

The block shows one of the four methods.

- Write a fake as a working in-memory version of the port, in `crates/core/src/testing.rs`. {{ skill_link("rust-di") }} covers the `test-support` feature that exposes it to the hosts.
- Use no mocking crate. A fake keeps real behaviour, so a test asserts on the outcome and survives a refactor of the call sequence.
- Take the lock with `lock().unwrap_or_else(PoisonError::into_inner)`. The module compiles under the feature as well as under `test`, so the `unwrap_used` lint applies to it.

## Clippy in tests

- `clippy.toml` allows `unwrap` and `expect` inside `#[test]` functions and `#[cfg(test)]` modules.
- A helper function in a `tests/*.rs` file is neither. Start every file in `tests/` with `#![allow(clippy::unwrap_used)]`.
- Compare with an empty collection as `assert_eq!(list, vec![])`. Clippy rejects `assert!(list.is_empty())` under the workspace lints, and the first form prints the unexpected items.

## API test

```rust
fn app() -> Router {
    let clock = FixedClock(Utc.with_ymd_and_hms(2026, 1, 2, 3, 4, 5).unwrap());
    let tasks = TaskService::new(Arc::new(MemoryTaskRepository::default()), Arc::new(clock));
    router(AppState { tasks })
}

#[tokio::test]
async fn a_blank_title_is_a_422_problem_and_nothing_is_stored() {
    let app = app();

    let reply = send(&app, "POST", "/tasks", Some(r#"{"title":"  "}"#)).await;

    assert_eq!(reply.status, StatusCode::UNPROCESSABLE_ENTITY);
    assert_eq!(reply.content_type, "application/problem+json");
    assert_eq!(reply.body["detail"], "title must be 1 to 120 characters");
    let list = send(&app, "GET", "/tasks", None).await;
    assert_eq!(list.body, json!([]));
}
```

- Send the request through the router in process with `tower::ServiceExt::oneshot`. No port is bound, so tests run in parallel and finish in milliseconds.
- Assert on the status, the content type and the body. For a rejected write, also assert that a later read shows no change.

The `send` helper and the `Reply` struct are in [references/api-harness.md](references/api-harness.md). Copy them into the first test file of an API crate.

## CLI binary test

```rust
fn tally(dir: &TempDir) -> Command {
    let mut command = Command::cargo_bin("tally").unwrap();
    command
        .env_remove("TALLY_DATA_FILE")
        .arg("--data-file")
        .arg(dir.path().join("tasks.json"));
    command
}

#[test]
fn a_blank_title_exits_1_with_the_reason_on_stderr() {
    let dir = TempDir::new().unwrap();

    tally(&dir)
        .args(["add", " "])
        .assert()
        .code(1)
        .stdout("")
        .stderr("error: title must be 1 to 120 characters\n");
}
```

- Run the built binary with `assert_cmd::Command::cargo_bin`. Cargo builds it before the test starts.
- Give each test its own `TempDir`, and remove every environment variable that the CLI reads. A developer's shell then cannot change the result.
- Assert on the exit code and on both streams.

## Adapter test

- Test an adapter against the real medium in a `tempfile::tempdir()`. Cover the round trip, the empty or missing store, and a corrupt store.
- Prove persistence by reading through a second adapter instance on the same path.

## Closing check

```bash
cargo test --workspace
cargo test -p tally-api a_blank_title
```

The first command runs every test. The second runs the tests of one crate whose name contains the text, which is the fast loop while writing one. Then run the closing commands in {{ skill_link("rust") }}.

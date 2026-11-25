---
name: rust-di
description: "Rust dependency injection: Send + Sync ports, async_trait, Arc<dyn Port>, composition root, config, test-support fakes. Load when adding a port, service or adapter, wiring a host, a trait object fails to compile, or a test needs fakes."
applyTo: '**/compose.rs,**/ports.rs,**/service.rs,**/config.rs,**/testing.rs'
tags: [rust, backend, standards]
---

# Dependency Injection

The port and composition root contract is {{ skill_link("hexagonal-architecture") }}. This skill states how it is wired in Rust. Rust projects wire by hand: `new` takes the dependencies and one function per host builds the graph. No container resolves types at run time, so a missing dependency fails the build.

## Ports

```rust
#[async_trait]
pub trait TaskRepository: Send + Sync {
    async fn save(&self, task: &Task) -> Result<(), TaskError>;
    async fn find(&self, id: TaskId) -> Result<Option<Task>, TaskError>;
    async fn list(&self) -> Result<Vec<Task>, TaskError>;
    async fn delete(&self, id: TaskId) -> Result<bool, TaskError>;
}

pub trait Clock: Send + Sync {
    fn now(&self) -> DateTime<Utc>;
}
```

- Declare a port as a trait in the feature's `ports.rs` in core. Name it for what the domain needs, not for the technology behind it.
- Add `Send + Sync` as supertraits. A service that holds the port then crosses threads, which axum and tokio require.
- Put `#[async_trait]` on a trait with `async fn` and on every `impl` of it. A plain `async fn` in a trait cannot be used as `dyn Trait`.
- Take `&self` in every method. An adapter that changes state holds a mutex or a connection pool inside.
- Put time, randomness and the network behind ports. `TaskId::generate` is the one exception here, because no test asserts on the id value.

## Services

```rust
#[derive(Clone)]
pub struct TaskService {
    repo: Arc<dyn TaskRepository>,
    clock: Arc<dyn Clock>,
}

impl TaskService {
    pub fn new(repo: Arc<dyn TaskRepository>, clock: Arc<dyn Clock>) -> Self {
        Self { repo, clock }
    }
}
```

- Hold each port as `Arc<dyn Port>` in a private field and take it in `new`.
- Derive `Clone` on the service. A clone copies the pointers, and every host hands a clone to each request, command or callback.
- Use `Arc<dyn Port>` for a dependency chosen at startup. Use a generic `impl Trait` parameter for a helper that takes a closure or an iterator.

## Composition root

```rust
pub fn compose(config: &Config) -> AppState {
    let repo = Arc::new(JsonFileTaskRepository::new(&config.data_file));
    let clock = Arc::new(SystemClock);
    AppState {
        tasks: TaskService::new(repo, clock),
    }
}
```

- Write one `compose` function per host, in `src/compose.rs`. It is the only code in the host that names a concrete adapter.
- Pass dependencies as arguments all the way down. Keep them out of `static`, `OnceLock` and thread-local storage.
- An `Arc<JsonFileTaskRepository>` converts to `Arc<dyn TaskRepository>` at the call to `new`. Write no cast.

## Lifetimes

| C# container scope | Rust form |
|---|---|
| Singleton | Build it once in `compose` and clone the `Arc` |
| Scoped per request | Build it inside the handler from the shared parts |
| Transient | Call the constructor where the value is used |

## Config

```rust
impl Config {
    pub fn from_env() -> anyhow::Result<Self> {
        Self::from_lookup(|key| std::env::var(key).ok())
    }

    pub fn from_lookup(lookup: impl Fn(&str) -> Option<String>) -> anyhow::Result<Self> {
        let addr = lookup("TALLY_ADDR").unwrap_or_else(|| "127.0.0.1:8080".to_owned());
        let addr = addr
            .parse()
            .with_context(|| format!("TALLY_ADDR must be host:port, got {addr:?}"))?;
        let data_file = lookup("TALLY_DATA_FILE").unwrap_or_else(|| "tally.json".to_owned());
        Ok(Self {
            addr,
            data_file: PathBuf::from(data_file),
        })
    }
}
```

- Read the environment once, in `main`, into a typed `Config`. Every other function receives the struct or one field of it.
- Parse through an injected lookup. A test passes a closure, and no test mutates the process environment.
- Name the variable and the bad value in the error context.

## Fakes

```rust
pub mod tasks;

#[cfg(any(test, feature = "test-support"))]
pub mod testing;
```

```toml
[features]
test-support = []
```

```toml
[dev-dependencies]
tally-core = { workspace = true, features = ["test-support"] }
```

- Write one fake per port in `crates/core/src/testing.rs`: a struct with in-memory state behind a `std::sync::Mutex`.
- Gate the module on `test` or the `test-support` feature. Core's own tests see it, each host enables the feature under `[dev-dependencies]`, and a release build leaves it out.
- A host test builds the real service over fakes with the same `new` that `compose` calls. {{ skill_link("rust-testing") }} shows the harnesses.

## Closing check

```bash
grep -rln "tally_infra" crates/*/src
```

The output lists composition roots alone. Then run the closing commands in {{ skill_link("rust") }}.

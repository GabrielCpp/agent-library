---
name: kmp-architecture
description: "Kotlin Multiplatform app architecture: feature packages (domain, data, ui), repository ports, Koin composition root, thin hosts. Load when adding a feature, repository, module or injection binding, or deciding where a Kotlin file belongs."
applyTo: '**/*.kt'
tags: [kmp, mobile, standards]
---

# Architecture

The generic contracts are {{ skill_link("hexagonal-architecture") }} and {{ skill_link("vertical-slicing") }}. This skill states how they land in a Kotlin Multiplatform app.

## Package layout

All paths sit under `shared/src/commonMain/kotlin/<base package>/`.

```text
App.kt                     root composable, navigation graph
di/AppModule.kt            composition root
di/AppConfig.kt            values the host passes in
designsystem/              theme, tokens, shared components
platform/                  ports for platform capabilities
data/AppDatabase.kt        the one Room database
feature/<name>/domain/     models, repository interface
feature/<name>/data/       API client, DAO, repository implementation
feature/<name>/ui/         view models, screens
```

One feature is one folder. A feature that another feature needs exposes its `domain` package and nothing else.

## Import directions

| Package | May import | Never imports |
|---|---|---|
| `domain` | Kotlin, coroutines | Ktor, Room, Compose, `data`, `ui` |
| `data` | its own `domain`, Ktor, Room, `platform` ports | Compose, `ui` |
| `ui` | its own `domain`, `designsystem`, Compose, lifecycle | `data`, Ktor, Room |
| `designsystem` | Compose | any `feature` |
| `di` | everything | |

A Konsist test in `shared/src/jvmTest` enforces this table. See {{ skill_link("kmp-testing") }}.

## Ports and adapters

- The repository interface in `domain` is the port. It speaks in domain models and returns `Flow` for reads and `suspend` functions for writes.
- The implementation in `data` is the adapter. It maps DTOs and entities to domain models at its edge, so neither type leaves `data`.
- A view model takes the interface. It never names the implementation.
- A platform capability is a port in `platform/` with one adapter per target. See {{ skill_link("kmp-platform") }}.

```kotlin
interface NotesRepository {
    fun observeNotes(): Flow<List<Note>>
    suspend fun refresh(): RefreshOutcome
}

enum class RefreshOutcome { Updated, Offline, ServerError }
```

## Composition root

- `di/AppModule.kt` is the only file that binds an interface to an implementation.
- It exposes one `startApp(config, platform)` function. Each host calls it once at launch and passes a module that holds its platform adapters.
- Bind a repository and the database as `single`. Bind a view model with `viewModelOf`.
- Inject by constructor. `KoinComponent` and `get()` inside a class body hide a dependency, so only a route composable resolves from Koin, through `koinViewModel()`.
- Pass environment values such as the API base URL in an `AppConfig` data class that the host builds. It sits in its own file, because detekt wants a file named for its one top-level class.

```kotlin
fun appModule(config: AppConfig): Module =
    module {
        single { NotesApi(get(), config.apiBaseUrl) }
        single { get<RoomDatabase.Builder<AppDatabase>>().open(Dispatchers.IO) }
        single { get<AppDatabase>().noteDao() }
        single<NotesRepository> { RoomNotesRepository(get(), get()) }
        viewModelOf(::NotesViewModel)
        viewModel { params -> NoteDetailViewModel(params.get(), get(), get()) }
    }

fun startApp(
    config: AppConfig,
    platform: Module,
    configure: KoinApplication.() -> Unit = {},
): KoinApplication =
    startKoin {
        configure()
        modules(appModule(config), platform)
    }
```

The `configure` parameter lets the Android host add `androidContext(...)` and lets a test add overrides.

## Adding a feature

1. Create `feature/<name>/domain` with the model and the repository interface.
2. Create `feature/<name>/data` with the adapter, and bind it in `di/AppModule.kt`.
3. Create `feature/<name>/ui` with the view model and the screen, following {{ skill_link("kmp-state") }} and {{ skill_link("kmp-compose") }}.
4. Add the destination to the navigation graph in `App.kt`.
5. Add a fake of the repository interface in `commonTest` and test the view model against it.

The step closes when `./gradlew :shared:jvmTest` exits 0 and the screen opens on one target.

## When to split a Gradle module

Keep one `shared` module until a build measurement says otherwise. Split a feature into its own Gradle module when an incremental build of `shared` passes one minute, or when two teams own separate features. A split module keeps the same three packages.

---
name: kmp-testing
description: "Kotlin Multiplatform tests: commonTest, fakes, Turbine, Ktor mock engine, Compose UI tests, Konsist architecture tests. Load when adding or changing a test, fake or view model, a coroutine test hangs or flakes, or choosing a proving test."
applyTo: '**/*Test.kt,**/commonTest/**,**/jvmTest/**'
tags: [kmp, mobile, tests]
---

# Testing

The methodology is {{ skill_link("testing-component") }}. Tests live in `shared/src/commonTest` and run with `./gradlew :shared:jvmTest` on any host in seconds.

## Where a test goes

| Test | Source set | Proves |
|---|---|---|
| View model | `commonTest` | state for each event, with a fake repository |
| Repository | `commonTest` | mapping and error handling, with `MockEngine` and a fake DAO |
| Screen | `commonTest` | the stateless screen renders a state and fires callbacks |
| Architecture | `jvmTest` | import rules, with Konsist |
| Migration | `jvmTest` | a real Room file migrates from the exported schema |

- Write a test in `commonTest` unless it needs a JVM-only library. A `commonTest` file imports no `java.*` and no `org.junit.*`. It uses `kotlin.test`.
- Put a test under `androidApp` only for Android-only behavior. A shared screen needs no instrumented test.

## Fakes

- Fake every port by hand in `commonTest`: a small class that implements the interface with in-memory state.
- Give a fake a gate when a test must observe the loading state.

```kotlin
class FakeNotesRepository(
    initial: List<Note> = emptyList(),
) : NotesRepository {
    private val notes = MutableStateFlow(initial)
    val refreshGate = CompletableDeferred<RefreshOutcome>()

    override fun observeNotes(): Flow<List<Note>> = notes

    override suspend fun refresh(): RefreshOutcome = refreshGate.await()
}
```

- Use no mocking library. The common ones need the JVM or a compiler plugin per target, and a fake reads better.

## View model test

```kotlin
@OptIn(ExperimentalCoroutinesApi::class)
class NotesViewModelTest {
    private val dispatcher = StandardTestDispatcher()

    @BeforeTest
    fun installMain() = Dispatchers.setMain(dispatcher)

    @AfterTest
    fun removeMain() = Dispatchers.resetMain()

    @Test
    fun aRefreshThatFindsNoNetworkReportsOffline() =
        runTest(dispatcher) {
            val repository = FakeNotesRepository()
            val viewModel = NotesViewModel(repository)

            viewModel.state.test {
                skipItems(2)
                viewModel.onRefresh()
                assertEquals(NotesUiState.Ready(emptyList(), refreshing = true, lastRefresh = null), awaitItem())
                repository.refreshGate.complete(RefreshOutcome.Offline)
                dispatcher.scheduler.advanceUntilIdle()
                assertEquals(RefreshOutcome.Offline, (expectMostRecentItem() as NotesUiState.Ready).lastRefresh)
            }
        }
}
```

- Set `Dispatchers.Main` to the test dispatcher and pass the same dispatcher to `runTest`. A second scheduler makes the test hang.
- Collect a `StateFlow` built with `stateIn(WhileSubscribed)` inside Turbine's `test { }`. With no collector the upstream never starts, and `state.value` stays at the initial value.
- Never call `delay` or `Thread.sleep` in a test. Advance with `dispatcher.scheduler.advanceUntilIdle()` or release a gate.
- Inject every dispatcher and clock that the code under test uses.

## Repository test

- Build the real repository with `HttpClient(MockEngine { respond(...) })` configured like production, and a fake DAO.
- Cover one success, one `respondError(HttpStatusCode.InternalServerError)`, and one engine that throws `IOException`.
- Assert the rows written and the result returned.

## Screen test

```kotlin
@OptIn(ExperimentalTestApi::class)
class NotesScreenTest {
    @Test
    fun aNoteRowOpensThatNote() =
        runComposeUiTest {
            val opened = mutableListOf<String>()
            val notes = listOf(Note("a", "Milk", "", null), Note("b", "Bread", "", null))
            setContent {
                AppTheme {
                    NotesScreen(
                        state = NotesUiState.Ready(notes, refreshing = false, lastRefresh = null),
                        onRefresh = {},
                        onOpenNote = opened::add,
                    )
                }
            }
            onNodeWithText("Bread").performClick()
            assertEquals(listOf("b"), opened)
        }
}
```

- Import `runComposeUiTest` from `androidx.compose.ui.test.v2`. The older package is deprecated.
- Render the stateless screen with a plain state value. A screen test starts no Koin and no view model.
- Find nodes by text, content description or role, as in {{ skill_link("kmp-a11y") }}.

## Architecture test

A Konsist test in `jvmTest` reads `Konsist.scopeFromProduction("shared")` and asserts three rules: `domain` imports no framework and no other layer, `ui` imports no `data`, Ktor or Room, and `commonMain` imports no `java.` or `android.`. Prove a new rule once by breaking it on purpose and watching the test fail.

## What a change needs

- A new or changed view model event: one view model test per outcome.
- A new or changed repository call: success and each failure type.
- A new or changed screen: one screen test that performs the main action.
- A bug fix: a test that fails before the fix and passes after it.

## Closing check

`./gradlew :shared:jvmTest` exits 0 and the new test appears in the report. On a Mac, `./gradlew :shared:iosSimulatorArm64Test` runs the same common tests on iOS.

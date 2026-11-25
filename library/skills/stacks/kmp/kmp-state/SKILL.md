---
name: kmp-state
description: "Kotlin Multiplatform ViewModel and UiState: StateFlow, sealed loading state, intents, stateIn, SavedStateHandle, rememberSaveable. Load when writing a ViewModel, UiState or state-collecting screen, or a screen loses state on rotation."
applyTo: '**/*ViewModel.kt,**/ui/**/*.kt'
tags: [kmp, mobile, standards]
---

# View Models and UI State

View models come from `org.jetbrains.androidx.lifecycle`. The same class runs on Android, iOS and desktop.

## The contract

- One screen has one view model and one `UiState` type.
- The view model exposes `val state: StateFlow<UiState>` and nothing else that the screen reads.
- The screen sends an intent by calling a view model function named for what the user did: `onRefresh()`, `onAdd(title)`.
- `UiState` holds values ready to show. The screen formats nothing and decides nothing.
- A view model imports no Compose type and no platform type.

```kotlin
sealed interface NotesUiState {
    data object Loading : NotesUiState

    data class Ready(
        val notes: List<Note>,
        val refreshing: Boolean,
        val lastRefresh: RefreshOutcome?,
    ) : NotesUiState
}

class NotesViewModel(
    private val repository: NotesRepository,
) : ViewModel() {
    private val refreshing = MutableStateFlow(false)
    private val lastRefresh = MutableStateFlow<RefreshOutcome?>(null)

    val state: StateFlow<NotesUiState> =
        combine(repository.observeNotes(), refreshing, lastRefresh) { notes, busy, outcome ->
            NotesUiState.Ready(notes, busy, outcome)
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(STOP_TIMEOUT_MS), NotesUiState.Loading)

    fun onRefresh() {
        if (refreshing.value) return
        refreshing.value = true
        viewModelScope.launch {
            try {
                lastRefresh.value = repository.refresh()
            } finally {
                refreshing.value = false
            }
        }
    }

    private companion object {
        const val STOP_TIMEOUT_MS = 5_000L
    }
}
```

## Rules

- Derive state from repository flows with `combine` and `stateIn`. Copying a flow into a `MutableStateFlow` by hand creates a second source of truth.
- Use `SharingStarted.WhileSubscribed(5_000)`. The upstream survives a rotation or a window resize and stops when the screen leaves.
- Use a `sealed interface` with `Loading` and `Ready` when the first frame has no data yet. Use one data class with defaults when an empty state is valid at once. Separate flows for loading, content and error can show a spinner over an error.
- Reset a busy flag in `finally`. A cancelled or failed call then never leaves the spinner on.
- Guard an intent that starts work against a second tap while the first runs.
- Change a `MutableStateFlow` that holds a data class with `update { it.copy(...) }`. Reading `value` and assigning it back from two coroutines loses a write.
- Model a one-off effect such as a snackbar as a nullable field. The screen shows it and calls a function such as `onNoticeShown()`. A `Channel` or `SharedFlow` of events drops the effect when no collector is active.
- Read a route argument from `SavedStateHandle` with `savedStateHandle.toRoute<Destination>()`, or take the id as a Koin parameter.
- Start work in `init` or from an intent. A screen never calls `LaunchedEffect(Unit) { viewModel.load() }`.
- Hold an enum or a key in state for user-facing text, such as `RefreshOutcome.Offline`. The screen resolves it with `stringResource`.

## Compose-side state

| State | Where it lives |
|---|---|
| Data, loading, errors, anything a test asserts | `UiState` in the view model |
| Text field content before submit, scroll position, expanded flags | `rememberSaveable` in the composable |
| Animation and focus objects | `remember` |

Collect with `collectAsStateWithLifecycle()` in the route composable only. See {{ skill_link("kmp-compose") }}.

## Closing check

Each view model has a test in `commonTest` that asserts the state sequence for every intent, following {{ skill_link("kmp-testing") }}. `./gradlew :shared:jvmTest` exits 0.

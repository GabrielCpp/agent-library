---
name: kmp-compose
description: "Compose Multiplatform screen rules: route and stateless screen, state hoisting, lazy list keys, Res resources, typed navigation. Load when writing a composable, screen, navigation destination or string resource, or on recomposition."
applyTo: '**/ui/**/*.kt,**/App.kt,**/composeResources/**'
tags: [kmp, mobile, standards]
---

# Compose Screens

Every screen is written once in `commonMain` and runs on Android, iOS and desktop.

## Route and screen

Each destination has two composables in one file.

- `XxxRoute` resolves the view model with `koinViewModel()`, collects state with `collectAsStateWithLifecycle()` and passes navigation callbacks. It holds no layout.
- `XxxScreen` takes the state and lambdas as parameters. It reads no view model, no Koin and no navigation controller, so a test renders it with a plain state value.

```kotlin
@Composable
fun NotesRoute(
    onOpenNote: (String) -> Unit,
    viewModel: NotesViewModel = koinViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    NotesScreen(state = state, onRefresh = viewModel::onRefresh, onOpenNote = onOpenNote)
}

@Composable
fun NotesScreen(
    state: NotesUiState,
    onRefresh: () -> Unit,
    onOpenNote: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Scaffold(modifier = modifier) { padding -> NotesContent(state, onOpenNote, Modifier.padding(padding)) }
}
```

## Composable rules

- Give every public composable a `modifier: Modifier = Modifier` parameter, first among the optional ones, and apply it to the root element once.
- Pass state down and events up. A child composable receives values and lambdas, never the view model.
- Call a `@Composable` function only from a composable body. Inside a `LazyColumn` builder, read the value into a `val` above the builder and use the `val` inside.
- Give every `items(...)` call a stable `key`, such as `key = Note::id`.
- Wrap a derived value that depends on fast-changing state in `remember { derivedStateOf { } }`.
- Keep a composable under about 60 lines. Extract a private composable for each visual part.
- Use Material 3 components and stable APIs. Reach for an `@OptIn(Experimental...)` API only when no stable overload does the job, and keep the opt-in on the smallest function.
- Apply `Scaffold` padding to the content. The app draws edge to edge on Android and under the safe area on iOS.

## Resources

- Every user-facing string lives in `shared/src/commonMain/composeResources/values/strings.xml` and is read with `stringResource(Res.string.key)`. A string literal in a composable fails review.
- Set `compose.resources { packageOfResClass = "<base package>.resources" }` so imports are stable.
- A translation goes in `values-<lang>/strings.xml` with the same keys.
- Images go in `composeResources/drawable` as vector XML or SVG and are read with `painterResource(Res.drawable.key)`.
- A view model never calls `stringResource`. It exposes an enum or a key, and the screen maps it to a string.

## Navigation

Destinations are `@Serializable` types, and the graph lives in `App.kt`. Details and patterns for tabs, back handling and deep links are in [references/navigation.md](references/navigation.md).

```kotlin
@Serializable
data object NotesDestination

@Serializable
data class NoteDetailDestination(val id: String)

NavHost(navController, startDestination = NotesDestination) {
    composable<NotesDestination> {
        NotesRoute(onOpenNote = { id -> navController.navigate(NoteDetailDestination(id)) })
    }
    composable<NoteDetailDestination> { entry ->
        NoteDetailRoute(id = entry.toRoute<NoteDetailDestination>().id, onBack = { navController.popBackStack() })
    }
}
```

- Pass an id through a destination, never a whole object.
- Only `App.kt` touches `NavController`. A route receives lambdas.
- Use the JetBrains navigation library. A hand-written back stack loses state restoration and the iOS back swipe.

## One layout, three window sizes

- Read the window size class with `currentWindowAdaptiveInfoV2()` from `org.jetbrains.compose.material3.adaptive:adaptive` and branch on it: a single pane when compact, list and detail side by side when expanded.
- Never branch on the platform to choose a layout. A desktop window can be phone sized, and a tablet can be desktop sized.
- Cap the width of reading content at about 600 dp on wide windows.
- A desktop user has a mouse and a keyboard. Every action reachable by touch is reachable by click and by Tab, and a hover state comes with Material components by default.

## Closing check

Render the changed screen in a `runComposeUiTest` test with a plain state value, following {{ skill_link("kmp-testing") }}. `./gradlew :shared:jvmTest` exits 0, then the screen is opened once on a device following {{ skill_link("kmp-qa") }}.

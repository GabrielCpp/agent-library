# Navigation patterns

The library is `org.jetbrains.androidx.navigation:navigation-compose`. It runs on Android, iOS and desktop with one graph.

## Destinations

- One `@Serializable` type per destination, declared next to the graph in `App.kt` or in the feature's `ui` package.
- `data object` for a destination with no argument, `data class` for one with arguments.
- Arguments are ids and small primitives. The detail screen loads its data from the repository by id.

## Reading arguments

- In the graph: `entry.toRoute<NoteDetailDestination>().id`.
- In a view model: `savedStateHandle.toRoute<NoteDetailDestination>()`, or pass the id as a Koin parameter with `koinViewModel { parametersOf(id) }`.

## Bottom bar or navigation rail

- Keep one `NavHost`. Each tab is a top-level destination.
- Switch tabs with this call so each tab keeps its own back stack and state:

```kotlin
navController.navigate(destination) {
    popUpTo(navController.graph.findStartDestination().id) { saveState = true }
    launchSingleTop = true
    restoreState = true
}
```

- Show a bottom bar on a compact window and a navigation rail on a wider one. `NavigationSuiteScaffold` from `org.jetbrains.compose.material3:material3-adaptive-navigation-suite` does this switch.

## Back

- `navController.popBackStack()` behind every visible back arrow.
- Android system back and the iOS edge swipe work with no extra code.
- Desktop has no system back. Every non-root screen shows a back arrow, and Escape maps to it through `onKeyEvent` on the root.
- Intercept back for unsaved input with the handler from `org.jetbrains.androidx.navigationevent:navigationevent-compose`. `BackHandler` from `ui-backhandler` still compiles and is deprecated in its favor.

## Results and one-off navigation

- A screen returns a result by writing to the repository or to the previous entry's `savedStateHandle`.
- Navigation after an async action is state: the view model sets a field, the route reacts in `LaunchedEffect(field)` and then tells the view model the navigation happened.

## Deep links

- Declare `deepLinks = listOf(navDeepLink<Destination>(basePath = "https://example.com/notes"))` on the destination.
- Android delivers the link through the activity intent. iOS delivers it through `onOpenURL` in Swift, which calls a shared function that forwards the URL to the navigation controller.

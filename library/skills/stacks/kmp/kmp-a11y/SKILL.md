---
name: kmp-a11y
description: "Compose Multiplatform accessibility: TalkBack, VoiceOver, content descriptions, roles, semantics, touch targets, font scaling. Load when building or reviewing an interactive composable, icon button, form field, screen title or test finder."
applyTo: '**/ui/**/*.kt,**/designsystem/**/*.kt'
tags: [kmp, mobile, standards]
---

# Accessibility

The contract is {{ skill_link("ui-accessibility") }}. Compose semantics are the one surface that feeds TalkBack on Android, VoiceOver on iOS, the desktop accessibility bridge, UI tests and Maestro. A node that a screen reader cannot name is a node that a test cannot find.

## Rules

- Prefer a Material component over a custom one. `Button`, `IconButton`, `Checkbox`, `Switch` and `TextField` carry a role, a state and a touch target already.
- Give every `Icon` and `Image` a decision: `contentDescription = stringResource(...)` when it carries meaning, `contentDescription = null` when the text next to it says the same thing.
- An `IconButton` with no text always has a content description that names the action, such as "Delete note".
- Make a custom row clickable with a role:

```kotlin
ListItem(
    headlineContent = { Text(note.title) },
    modifier = Modifier.clickable(role = Role.Button, onClickLabel = openLabel, onClick = onClick),
)
```

- Use `Modifier.toggleable` or `Modifier.selectable` with `Role.Switch`, `Role.Checkbox`, `Role.RadioButton` or `Role.Tab` for a custom toggle. The reader then announces the state.
- A clickable parent merges its children into one node. For a non-clickable group that should read as one item, add `Modifier.semantics(mergeDescendants = true) { }`.
- Mark each screen title and section title with `Modifier.semantics { heading() }`.
- Describe a state that is shown by color or position alone with `stateDescription`.
- Announce a change that appears away from focus, such as an inline error, with `liveRegion = LiveRegionMode.Polite`.
- Give a `TextField` a `label`. A placeholder alone disappears when the user types.

## Size, contrast and scaling

- Keep every touch target at least 48 dp. Material components do this. A custom one adds `Modifier.minimumInteractiveComponentSize()`.
- Express text size in `sp` through the theme typography, and let containers grow with the text. A fixed height on a text container clips at 200 percent font scale.
- Take colors from `MaterialTheme.colorScheme` pairs, such as `onPrimary` on `primary`. The design system holds the contrast, as in {{ skill_link("kmp-design-system") }}.

## Desktop keyboard

- Every action is reachable with Tab and activates with Enter or Space. Material components do this. A custom clickable built on `pointerInput` does not, so use `clickable`.
- Keep focus order equal to reading order. Fix a wrong order with layout order first and `focusProperties` second.
- Show a visible focus indicator. Material components do, so never remove `indication`.

## Semantics in tests

- Find a node by text, content description or role: `onNodeWithText`, `onNodeWithContentDescription`, `onNode(hasRole(Role.Button))`.
- Use `Modifier.testTag` only for a node with no user-visible name, such as a chart canvas. A screen that needs many test tags has missing semantics.
- Maestro reads the same tree, so a flow taps by the visible text or the content description.

## Closing check

One UI test per changed screen asserts the node by its accessible name and performs the action through it, following {{ skill_link("kmp-testing") }}. `./gradlew :shared:jvmTest` exits 0.

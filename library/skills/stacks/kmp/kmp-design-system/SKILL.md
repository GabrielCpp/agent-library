---
name: kmp-design-system
description: "Kotlin Multiplatform design system: AppTheme, MaterialTheme, color schemes, spacing and shape tokens, typography, shared components. Load when changing the theme, a token, a font or a shared component, or a screen has a hard-coded color."
applyTo: '**/designsystem/**,**/*Theme*.kt'
tags: [kmp, mobile, standards]
---

# Design System

The methodology is {{ skill_link("ui-design-system") }}. This skill states where each part lives in a Kotlin Multiplatform app.

## Location

```text
shared/src/commonMain/kotlin/<base package>/designsystem/
  AppTheme.kt        color schemes, typography, the AppTheme composable
  AppTokens.kt       AppSpacing, AppShapes, AppElevation
  components/        AppButton.kt, AppTextField.kt, one file per component
```

The package imports Compose and nothing from any `feature` package. Every target shares this one copy.

## Theme

```kotlin
@Composable
fun AppTheme(
    dark: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (dark) DarkColors else LightColors,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}
```

- `App()` wraps the navigation graph in `AppTheme` once. Tests wrap the screen under test in the same `AppTheme`.
- Define a full light and a full dark `ColorScheme`. Each role that the app uses is set in both.
- Keep the same brand theme on all three targets. Android dynamic color is an opt-in product decision, added in `androidMain` behind a parameter.
- Load a brand font from `composeResources/font` with `Font(Res.font.name)`. `Font` is composable there, so build `Typography` inside a composable and `remember` it.

## Tokens

```kotlin
object AppSpacing {
    val small = 8.dp
    val medium = 16.dp
    val large = 24.dp
}
```

| A screen needs | It reads | It never writes |
|---|---|---|
| A color | `MaterialTheme.colorScheme.<role>` | `Color(0xFF...)` |
| A text style | `MaterialTheme.typography.<role>` | `fontSize = 14.sp` |
| A gap or padding | `AppSpacing.<step>` | `12.dp` |
| A corner | `MaterialTheme.shapes.<size>` | `RoundedCornerShape(8.dp)` |

- A raw `Color(`, `.sp` or spacing `.dp` literal appears only inside `designsystem/`. Sizes that belong to one component, such as an avatar diameter, live as a private `val` in that component file.
- Add a token when two screens need the same value. A value used once stays local to its component.

## Components

- A shared component is a stateless composable with a `modifier` parameter, a slot or plain values in, and lambdas out.
- Create one when the same Material call with the same parameters appears in a second feature. Features then call `AppButton`, and one edit restyles every screen.
- A component carries its own semantics so every use is accessible by default. See {{ skill_link("kmp-a11y") }}.
- Give each component a `@Preview` function in light and dark. Previews render in the IDE for common code.

## Closing check

```bash
grep -rnE 'Color\(0x|[0-9]\.sp\b' shared/src/commonMain/kotlin --include='*.kt' | grep -v '/designsystem/'
```

Empty output closes the step. Then one screen is opened in light and in dark mode following {{ skill_link("kmp-qa") }}.

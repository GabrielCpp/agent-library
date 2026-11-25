---
name: flutter-design-system
description: "Flutter design system: token classes under lib/core/config/theme/, design_system.dart barrel, AppTheme.light/dark, component themes. Load when standing up or restructuring a Flutter design system or its tokens."
applyTo: 'app/lib/core/config/theme/**/*.dart'
tags: [flutter, mobile, standards]
---

# Design System in a Flutter App

This is the **Flutter-specific concretization** of
{{ skill_link("ui-design-system") }}.
Read that first for the token taxonomy, provenance, and "extend, don't inline"
discipline. For day-to-day token *usage* (which token to read in a widget, dark-mode
rules, Material 3 component conventions) see
{{ skill_link("flutter-theme") }}.
This file is about **how the system is built and structured**, with a token
layer under `lib/core/config/theme/` as the worked example.

## What "the design system" *is* here

In Flutter there is no single theme literal — the system is **a folder of token
classes plus a `ThemeData` builder**, exposed through one barrel:

- **Token classes**, one file per concern, each an `abstract final class` of named
  `static const` values:
  - `app_colors.dart` — `AppColors` (raw brand colors) **and** the
    `lightColorScheme` / `darkColorScheme` `ColorScheme`s.
  - `app_typography.dart` — `AppTypography` `TextStyle`s (the type scale).
  - `app_spacing.dart` — `AppSpacing` on a 4/8px grid (`xs`, `sm`, `md`, …).
  - `app_radius.dart` — `AppRadius`.
  - `app_shadows.dart` — `AppShadows`.
  - `app_durations.dart` — `AppDurations` (motion).
- **A barrel** `design_system.dart` that `export`s all of the above, so any widget
  imports the whole system with one line.
- **`app_theme.dart`** — `AppTheme.light()` / `AppTheme.dark()` that build
  `ThemeData` **from** those tokens via a single private `_buildTheme(ColorScheme)`.

A widget never defines a design value; it reads a token class or
`Theme.of(context)`.

## The two-tier color model (the key Flutter move)

Split colors by whether they flip with the theme — this is what makes dark mode
work without per-widget branching:

- **Constant brand colors** → plain `static const Color` on `AppColors`
  (`AppColors.primary`). Same in light and dark. Fine to read directly.
- **Theme-variant colors** (surface, background, text, border/outline, disabled)
  → defined inside `lightColorScheme` / `darkColorScheme` and read at call sites as
  `Theme.of(context).colorScheme.surface` / `.onSurface` / `.outline`. These adapt
  automatically when the mode changes.

Creating the system means filling **both** schemes from the reference up front;
retrofitting a dark scheme onto value-named colors later is the painful path.

## Build `ThemeData` from tokens, theme components centrally

`_buildTheme(ColorScheme)` sets `useMaterial3: true`, wires the `ColorScheme` and
`AppTypography` into `ThemeData`, and configures **every component theme in one
place** — `cardTheme`, `elevatedButtonTheme`/`filledButtonTheme`, `inputDecoration`,
`dividerTheme`, `navigationBarTheme`, `dialogTheme`, etc. (a full `app_theme.dart`
configures about 30 of them). The point: a `Card` or `FilledButton` looks right by
default, so widgets never override component themes inline.

```dart
abstract final class AppTheme {
  static ThemeData light() => _buildTheme(AppColors.lightColorScheme);
  static ThemeData dark()  => _buildTheme(AppColors.darkColorScheme);
  static ThemeData _buildTheme(ColorScheme scheme) => ThemeData(
        useMaterial3: true,
        colorScheme: scheme,
        // typography from AppTypography, component themes from the token classes…
      );
}
```

## Creating / extending the token layer

- **Add to the existing file for the concern** — a new spacing step goes in
  `app_spacing.dart`, a new radius in `app_radius.dart`. **Do not create new token
  files** for one-off values, and do not scatter `Color(0xFF…)` / bare numbers in
  widgets.
- **New color:** theme-variant → add to both `ColorScheme`s; constant brand →
  `static const` on `AppColors`.
- **Trace each token to its source** in a doc comment (mockup, reference screen,
  brand spec).

## Done means

Every visual value lives in a token class under `lib/core/config/theme/`; widgets
read tokens or `Theme.of(context)` with **no** inline `Color(0xFF…)`, font sizes,
spacing numbers, or radii; both `ColorScheme`s are populated; component themes are
central in `app_theme.dart`; and the whole system imports via `design_system.dart`.

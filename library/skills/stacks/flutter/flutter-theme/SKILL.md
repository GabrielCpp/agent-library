---
name: flutter-theme
description: "Flutter theming: AppColors, AppTypography, AppSpacing, AppRadius, AppTheme, ColorScheme, Material 3. Load when replacing a hardcoded colour, size or radius with a token, adding a token, or checking dark mode."
applyTo: 'app/lib/**/*.dart'
tags: [flutter, mobile, standards]
---

# Flutter App — Theming & Styling

## Design tokens

All visual values come from the token constants in `lib/core/config/theme/`. Never hardcode colours, font sizes, spacing values, or border radii.

| Concern | Token class | Example |
|---|---|---|
| Colours | `AppColors` | `AppColors.primary` |
| Typography | `AppTypography` | `AppTypography.headlineMedium` |
| Spacing | `AppSpacing` | `AppSpacing.md` |
| Border radius | `AppRadius` | `AppRadius.card` |

```dart
// Correct
Padding(
  padding: EdgeInsets.all(AppSpacing.md),
  child: Text('Hello', style: AppTypography.bodyLarge),
)

// Wrong
Padding(
  padding: EdgeInsets.all(16),
  child: Text('Hello', style: TextStyle(fontSize: 16)),
)
```

**Never** hardcode `Color(0xFF...)` values inline — always use `AppColors` or `Theme.of(context).colorScheme`.
**Never** hardcode numeric spacing or font size values.

## Dark mode

The app supports both light and dark themes via `AppTheme.light()` and `AppTheme.dark()`. Widgets that need theme-aware colours must use `Theme.of(context).colorScheme` rather than `AppColors` constants directly, so they respond to theme changes.

```dart
// Theme-aware (preferred for surface/background/text colours)
color: Theme.of(context).colorScheme.surface

// Token-based (OK for brand colours that are the same in both themes)
color: AppColors.primary
```

Always visually check new UI in both light and dark mode.

## Material 3

The app uses Material 3 (`useMaterial3: true`). Use Material 3 components (`FilledButton`, `Card`, `NavigationBar`) over their Material 2 equivalents. Component themes are configured centrally in `AppTheme._buildTheme` — do not override component themes inline.

**Never** set `ThemeData.useMaterial3 = false` anywhere.

## Adding new tokens

Add new spacing, radius, or typography values to the appropriate existing file (`app_spacing.dart`, `app_radius.dart`, `app_typography.dart`). Do not create new token files.

Add new colours to `app_colors.dart` as part of a `ColorScheme` if they are theme-variant, or as a standalone constant if they are brand colours that do not change with theme.

**Standing up a design system from scratch** (no token layer yet, or building one for a new surface) is a different task from adding a token to the existing one — see {{ skill_link("flutter-design-system") }} for how the token classes, `design_system.dart` barrel, and `AppTheme.light/dark` builder are structured (which itself builds on the generic design-system methodology).

## Scope boundaries

This file covers design tokens, dark mode usage, Material 3 conventions, and how to add new tokens. It does **not** cover layout structure or widget composition — see {{ skill_link("flutter-architecture") }}.


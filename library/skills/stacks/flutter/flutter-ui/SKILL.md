---
name: flutter-ui
description: "Flutter UI widget rules: context.colors, AppSpacing, AppRadius, context.textTheme, Material 3, dark mode, i18n. Load when writing or reviewing a widget or screen layout, user-facing text, or responsive behaviour."
applyTo: 'app/**/*.dart'
tags: [flutter, mobile, standards]
---

# Flutter UI & Design System Instructions

**CRITICAL: LLM Contract for Writing Flutter UI**

Apply these rules strictly when implementing widgets and UI components. Source of truth: `app/docs/MATERIAL_UX_DESIGN_SYSTEM.md`.

---

## Rule 1: Design Tokens & Theming

**ENFORCE:** Use semantic tokens from `Theme.of(context)` and `design_system.dart`. NEVER hardcode raw values.

### Color Tokens

**REJECT:** `Colors.red`, `Color(0xFF...)`, `Colors.grey[200]`
**ENFORCE:** `context.colors.*` (Semantic extensions) or `Theme.of(context).colorScheme.*`

```dart
// ✅ CORRECT
Container(color: context.colors.surfaceContainerHighest);
Text('Error', style: TextStyle(color: context.colors.error));

// ❌ WRONG
Container(color: Colors.grey[200]);
Text('Error', style: TextStyle(color: Colors.red));
```

### Spacing & Layout

**REJECT:** Hardcoded numbers for padding/sizing (e.g., `16.0`, `8.0`).
**ENFORCE:** `AppSpacing.*` or `AppRadius.*` tokens.

```dart
// ✅ CORRECT
Padding(
  padding: EdgeInsets.all(AppSpacing.md),
  child: Gap(AppSpacing.sm),
)

// ❌ WRONG
Padding(
  padding: EdgeInsets.all(16),
  child: SizedBox(height: 10),
)
```

### Typography

**REJECT:** Manually defining `TextStyle` with `fontSize`.
**ENFORCE:** `context.textTheme.*` (e.g., `headlineSmall`, `bodyMedium`). Use `.copyWith()` ONLY for color/weight tweaks.

```dart
// ✅ CORRECT
Text('Title', style: context.textTheme.titleMedium);
Text('Alert', style: context.textTheme.bodyMedium?.copyWith(color: context.colors.error));

// ❌ WRONG
Text('Title', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500));
```

---

## Rule 2: Component Guidelines

**ENFORCE:** Follow these specific Material 3 patterns.

1. **Text Fields**: ALWAYS use `OutlineInputBorder`. NEVER use filled backgrounds (looks disabled).
2. **Buttons**: Use semantic variants (`FilledButton`, `OutlinedButton`, `TextButton`).
3. **Loading States**: Use Shimmer or Skeleton loaders, never just a blank screen.
4. **Empty States**: Use illustrative empty states with actions, never empty lists.
5. **Touch Targets**: Minimum 48x48dp for tappable areas.

```dart
// ✅ CORRECT: Outlined Input
TextFormField(
  decoration: InputDecoration(
    border: OutlineInputBorder(borderRadius: AppRadius.inputRadius),
    filled: false,
  ),
);
```

---

## Rule 3: Dark Mode & Responsiveness

**ENFORCE:**

- All UI must work in both Light and Dark modes.
- Avoid checking `Brightness` manually; trust the `ColorScheme`.
- Text must scale (avoid fixed height containers on text).

**REJECT:**

- `color: Colors.black` (Invisible in dark mode)
- `color: Colors.white` (Blinding in light mode)

---

## Rule 4: Internationalization (i18n)

**ENFORCE:** All user-facing text MUST live in ARB files (`l10n/`).

**REJECT:** Hardcoded strings in widgets.

```dart
// ✅ CORRECT
Text(context.l10n.welcomeMessage(name));

// ❌ WRONG
Text('Welcome, $name!');
```


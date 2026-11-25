---
name: flutter-a11y
description: "Flutter accessibility: semantics tree, semantic labels, focus traversal, text scaling, tap targets, a11y widget tests. Load when writing or reviewing a Flutter widget's semantics, labels, focus order or tap targets."
applyTo: 'app/**/*.dart'
tags: [flutter, mobile, standards]
---

# Accessibility in a Flutter App

The universal obligations — role, name, keyboard, focus, perceivable state — are defined once in
the `ui-accessibility` skill. **Read that first.** In Flutter the contract surface is the
**semantics tree**: what TalkBack/VoiceOver announce, what `flutter_test`'s semantics matchers
assert, and what a semantics dump (`debugDumpSemanticsTree()`) shows are all the *same* tree. A
control that isn't in that tree, or is in it without a role and label, does not exist for assistive
tech — no matter how it renders.

## Role — material widgets carry semantics; a tappable Container does not

- **`GestureDetector`/`InkWell` wrapped around a `Container` is this stack's clickable `div`.**
  It adds a tap handler and *no semantics* — no role, no focusability, no keyboard activation.
  Use the real widget (`FilledButton`/`OutlinedButton`/`TextButton`/`IconButton`, `Checkbox`,
  `Switch`, `Slider`, `ListTile(onTap:)`) — each carries role, focus, and keyboard activation for
  free. When a custom gesture surface is genuinely unavoidable, wrap it in
  `Semantics(button: true, label: …, onTap: …)` **and** a `FocusableActionDetector` (or
  `InkWell(canRequestFocus: true)`) so keyboard and switch-access users can reach and fire it.
- **Structure is semantic too:** mark headings with `Semantics(header: true)`; group a composite
  row so it announces as one item with `MergeSemantics`; hide decorative layers with
  `ExcludeSemantics`/`Semantics(excludeSemantics: true)`. A screen built from bare `Container`s
  reads as an undifferentiated pile of text.

## Name — every control announces its purpose

- Icon-only controls: `IconButton(tooltip: …)` (the tooltip doubles as the semantic label) or
  `Semantics(label: …)`. `Icon(semanticLabel: …)` names a meaningful icon; omit it (default) for a
  decorative one so it stays silent.
- Text fields: `InputDecoration(labelText: …)` — a persistent label. **`hintText` is a
  placeholder, not a label** — it vanishes on input, exactly like HTML's placeholder.
- Images that carry meaning get `Image(semanticLabel: …)`; decorative ones
  `ExcludeSemantics`/empty label.

## Keyboard and focus — desktop/web are first-class, mobile has switch access

- Custom interactive widgets need focus + activation wiring: `FocusableActionDetector` (focus,
  hover, `ActivateIntent` for Enter/Space) — real buttons get all of it free.
- Traversal order follows reading order: group panes with `FocusTraversalGroup`, don't rely on
  build order accidents. No focus traps outside intentional modals.
- Dialogs: `showDialog` traps and restores focus for you — don't rebuild that by hand. After a
  navigation or async completion, move focus deliberately (`autofocus` on the primary control of
  the new route, or `FocusNode.requestFocus`) so assistive tech knows the context changed.
- Never disable the focus highlight without an equally visible replacement.

## Perceivable state — announced, scaled, and reachable

- State lives in semantics flags, not colors: `Semantics(selected: …, toggled: …, checked: …)` —
  material widgets set these from their own state; hand-rolled "highlighted row" styling needs the
  flag set alongside, or the state is color-only.
- **Async and pushed state must be announced:** `SemanticsService.announce(…)` (this stack's
  `aria-live`) for background updates, or route the message through a widget whose semantics
  update (e.g. a status `Text` inside `Semantics(liveRegion: true)`).
- **Text scaling:** respect `MediaQuery.textScaler` — no fixed-height boxes that clip at 1.3×,
  no `textScaleFactor: 1.0` overrides to "fix" layout.
- **Tap targets ≥ 48dp** (`kMinInteractiveDimension`; don't shrink `materialTapTargetSize`), and
  contrast per WCAG AA — use theme tokens (see `flutter-design-system`), check custom colors
  against their real background.

## Verification — the semantics tree is testable

- **Widget tests, mechanical:** enable semantics and assert the built-in guidelines —
  ```dart
  final handle = tester.ensureSemantics();
  await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
  await expectLater(tester, meetsGuideline(iOSTapTargetGuideline));
  await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
  await expectLater(tester, meetsGuideline(textContrastGuideline));
  handle.dispose();
  ```
- **Pin tests close the analyzer's blind spot:** the analyzer never flags a semantics-less
  `GestureDetector` (the delegation-blind-spot twin from the universal skill). Pin load-bearing
  controls by finding them semantically — `find.bySemanticsLabel(…)`,
  `tester.getSemantics(find.byKey(…))` asserting `isButton`/`hasEnabledState` — so a regression to
  a bare gesture surface fails a test, not a user.
- **Manual smoke:** drive the touched screen with TalkBack/VoiceOver once and with keyboard only
  (desktop/web targets); `debugDumpSemanticsTree()` is the quick "what does AT actually see" scan.

## Done means

Everything in the universal contract's "Done means", plus, specific to this stack: no interactive
`GestureDetector`/`InkWell` without button semantics and focusability; every icon-only control has
a tooltip or semantic label; composite rows are merged and announce as one; async/pushed state is
announced via `SemanticsService.announce`/a live-region semantics node; layouts survive 1.3× text
scale; and the four `meetsGuideline` checks pass in widget tests with semantics enabled.

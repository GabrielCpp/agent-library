---
name: react-native-a11y
description: "React Native accessibility: accessibilityRole/Label/State, Pressable, icon buttons, screen-reader focus, font scaling, hit targets, RNTL. Load when adding touchables, icon buttons or lists, reviewing screen readers, or fixing a11y lint."
applyTo: '{{ template.react_native_path | default("app") }}/src/**/*.ts,{{ template.react_native_path | default("app") }}/src/**/*.tsx'
tags: [react-native, mobile, standards]
---

# Accessibility in a React Native App

The universal obligations — role, name, keyboard, focus, perceivable state — are defined once in
the `ui-accessibility` skill. **Read that first.** There is no DOM here: the contract surface is
the `accessibility*` prop family, which feeds TalkBack/VoiceOver, React Native Testing Library's
role/label queries, and any automated scan alike. A touchable with no `accessibilityRole` is this
stack's clickable `div` — it may respond to taps, but for a screen-reader user it's either
invisible or an unnamed "double tap to activate" mystery.

## Role — every touchable declares what it is

- **`Pressable`/`TouchableOpacity` around a `View` announces nothing by itself.** Give every
  interactive element `accessibilityRole` (`"button"`, `"link"`, `"checkbox"`, `"switch"`,
  `"tab"`, `"radio"`, `"imagebutton"`, `"adjustable"` for sliders). Prefer components that set it
  for you (`Button`, `Switch`) where they fit.
- **Structure:** section titles get `accessibilityRole="header"` — screen-reader users navigate by
  headers. Lists come from `FlatList`/`SectionList` (index/count semantics free), not a mapped
  column of `View`s.
- **Group composite rows** with `accessible={true}` on the row container so its children merge into
  one announced element (the `MergeSemantics` twin) — otherwise a row reads as four disconnected
  fragments. Mark purely decorative elements `importantForAccessibility="no-hide-descendants"` /
  `accessibilityElementsHidden`.

## Name — labels are explicit, placeholders are not labels

- Icon-only controls need `accessibilityLabel` ("Close", "Refresh workers") — there is no text
  child to read. Add `accessibilityHint` only when the outcome isn't obvious from the label.
- `TextInput` needs `accessibilityLabel` (or a visible, associated label component) — **a
  `placeholder` is not a label**; it vanishes on input, same as everywhere else.
- Meaningful images get `accessibilityLabel` on the `Image`/`accessibilityRole="image"`;
  decorative ones stay unlabeled and hidden from AT.

## Focus — screen-reader focus is the "where am I" model

- **After navigation or a modal opens**, move screen-reader focus deliberately:
  `AccessibilityInfo.setAccessibilityFocus(findNodeHandle(ref))` on the new screen's header (or
  rely on the navigator/`Modal`'s built-in focus behavior where it exists — verify it, don't
  assume). A route change with focus left behind didn't happen for an AT user.
- Modals trap AT focus while open (`Modal` handles iOS; verify Android) and return focus to the
  trigger on close — never leave it stranded.
- Tablets/external keyboards: keep custom touchables focusable (`focusable={true}` on Android) and
  activation working, not just tap.

## Perceivable state — announced, scaled, and hittable

- **State is `accessibilityState`, not styling:**
  `accessibilityState={% raw %}{{ selected, disabled, checked, expanded, busy }}{% endraw %}` wherever a conditional
  style marks the active tab, selected row, or collapsed section — a highlight without the state
  prop is color-only state. Sliders/steppers expose `accessibilityValue`.
- **Async and pushed state must be announced:**
  `AccessibilityInfo.announceForAccessibility(…)` (cross-platform) or
  `accessibilityLiveRegion="polite"` on the status view (Android) — a spinner or toast only a
  sighted user notices is not an announcement. Errors that demand attention announce assertively
  (announce + move focus to the error).
- **Font scaling:** leave `allowFontScaling` on (default); no fixed heights that clip at large
  text; test the touched screen at 1.3× system font.
- **Hit targets ≥ 44pt/48dp** — pad small icons via `hitSlop`, don't shrink below the platform
  minimums. Contrast per WCAG AA using the app's theme tokens, checked against the real background.

## Linting and testing this stack — what the gate runs

- **Static:** `eslint-plugin-react-native-a11y` (recommended config) in the repo's lint target —
  it catches touchables with no role, missing labels on icon buttons, and misused
  `accessibilityState` shapes at write time.
- **Pin tests (close the static blind spot):** a custom pressable composed through wrappers can
  evade the lint rule — pin load-bearing controls with RNTL semantic queries:
  `getByRole("button", { name: "Refresh workers" })`, `getByLabelText(…)`, and assert
  `accessibilityState` for stateful controls. If a control can't be found by role+name in a test,
  a screen reader can't find it either — same fact, two consumers.
- **Manual smoke:** drive the touched screen once with TalkBack and once with VoiceOver — every
  control reachable, named, and its state announced; every async result announced without looking.

## Done means

Everything in the universal contract's "Done means", plus, specific to this stack: no interactive
`Pressable`/`Touchable*` without `accessibilityRole`; every icon-only control has
`accessibilityLabel`; composite rows merge via `accessible={true}`; stateful controls carry
`accessibilityState`/`accessibilityValue`; async/pushed updates are announced via
`AccessibilityInfo`; layouts survive 1.3× font scale; hit targets meet 44pt/48dp; and the touched
controls are locatable by RNTL `getByRole(role, { name })`.

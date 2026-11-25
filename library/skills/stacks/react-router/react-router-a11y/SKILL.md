---
name: react-router-a11y
description: "Accessibility in a React Router + MUI app: semantic HTML, ARIA, accessible names, keyboard, focus, contrast. Load when building or reviewing interactive web UI such as dialogs, forms, menus and buttons, or fixing screen-reader problems."
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.ts,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.tsx'
tags: [react-router, web, standards]
---

# Accessibility in a React Router + MUI App

This is a distinct concern from
{{ skill_link("react-router-design-system") }}:
the design system governs what the app *looks* like; this skill governs who else can *use* it —
screen-reader users, keyboard-only users, low-vision users — and, as a side effect, any
deterministic tool that reads the same DOM signals (a `getByRole` test query, an axe scan, a
DOM-role-based visual-fidelity check such as `ostler vet`). Accessibility is the actual goal;
tool-legibility is a consequence of doing it right, not the reason to do it.

## Semantic HTML and ARIA roles first, not last

- Prefer native elements (`<table>`, `<button>`, `<nav>`, `<label>`, `<ul>/<li>`) over a `<div>`
  soup with visual styling — native elements carry their accessible role for free. Reach for an
  explicit `role`/`aria-*` attribute only when no native element fits (a card grid acting as a
  list, a custom disclosure widget), and even then prefer MUI components that already wire the
  role (`List`/`ListItem`, `Accordion`) over hand-rolled `div`s.
- **Concrete incident this rule comes from:** a DOM scan of a live MUI `Table` found the
  `<table>` element itself and every `<tr>` row carrying **no explicit `role` attribute**. A
  screen reader falls back to the browser's implicit table semantics here, which is usually
  fine for a real `<table>` — but the same gap is much worse the moment a "table" is actually
  built from `Box`/`Grid` divs styled to look tabular: there is no implicit role to fall back
  to, so a screen reader announces an undifferentiated pile of text with no row/column
  relationships at all. A DOM-role-based visual-fidelity tool (`ostler vet`) hit the identical
  gap: every row landed in its `unlabeled` bucket, indistinguishable from a stray unlabeled
  wrapper `div`, because it also has nothing but the explicit `role` attribute to key off. Same
  DOM fact, same blind spot, two different consumers. **Fix:** use a real `<table>` (MUI
  `Table`/`TableRow`/`TableCell`, not a div grid dressed up with CSS) whenever content is
  tabular, and if a custom widget structurally *is* a table/list/grid but can't use the native
  element, give it the matching ARIA roles explicitly (`role="table"`/`"row"`/`"cell"`,
  `role="list"`/`"listitem"`) rather than leaving it role-less.
- Never leave a functionally interactive element (something with an `onClick`) with no
  accessible role — a clickable `<div>` or `<span>` is invisible to a screen reader and to
  keyboard navigation. Use a real `<button>`/`<a>`, or add `role="button"` + keyboard handling
  if a native element genuinely can't be used.
- **Widget state is ARIA state, not `className`/`sx` alone.** A toggle exposes `aria-pressed`
  (MUI `ToggleButton` wires it), a disclosure `aria-expanded` (`Accordion` wires it), the
  selected row/tab `aria-selected` or `aria-current`. When you hand-roll a highlighted state —
  a `selected` class, a conditional `sx` background — set the matching ARIA state attribute in
  the same place; highlight-without-announcement is color-only state by another name.

## Every interactive element needs an accessible name

- Icon-only controls (`IconButton`, icon-only toggle) need `aria-label` — there is no visible
  text for a screen reader to read. A decorative icon that duplicates adjacent visible text
  should be `aria-hidden` instead, not labeled twice.
- Every form field needs a programmatically associated label: MUI's `TextField`/`FormControl` +
  `InputLabel` pairing (which wires `htmlFor`/`id` for you), or `aria-label` as a fallback for a
  field with no visible label. **A placeholder is not a label** — it disappears the moment the
  user types, and most screen readers don't announce it as one.
- Why this is the cheapest, highest-value fix: without an accessible name, a screen reader
  announces bare "button" / "textbox" with no purpose attached. This is the single most common
  accessibility failure in the wild and the easiest one to prevent at write time.

## Keyboard operability

- Everything reachable/operable with a mouse must be reachable/operable with a keyboard alone:
  Tab order follows visual/reading order, and a custom clickable element gets `tabIndex={0}` plus
  Enter/Space handling — or, better, is a real `<button>`, which gets this for free.
- No keyboard traps: a user must always be able to Tab (or Escape) out of any widget that isn't
  an intentional modal focus trap (see Focus management below).
- Why: motor-impaired users, screen-reader users, and plenty of power users never touch a mouse.
  A `div onClick` with no keyboard handler doesn't just degrade for them — it doesn't exist.

## Focus management

- **Never suppress the focus outline** (`outline: none`/`:focus { outline: 0 }`) without
  supplying an equally visible replacement. MUI's default focus ring is already a theme-driven
  affordance — don't strip it for aesthetics.
- **Dialogs, modals, drawers:** on open, move focus into the dialog (its first focusable element,
  or the dialog container itself); trap Tab/Shift+Tab inside it while open; on close, **return
  focus to the element that triggered it** (the button that opened the dialog), not to
  `document.body`. MUI's `Dialog`/`Modal` already do this via their built-in focus trap — don't
  pass `disableEnforceFocus`/`disableAutoFocus`/`disableRestoreFocus` unless you are replacing
  that behavior yourself.
- **After a React Router client-side navigation**, move focus to the new page's main heading or
  main landmark. An SPA route change never reloads the document, so nothing tells assistive tech
  "you are now somewhere else" unless the app does it explicitly — a screen reader user can be
  left thinking they're still on the old page.
- **After an async action completes** (save, delete, submit, a validation error appears), move
  focus to the resulting message and put that message in an `aria-live="polite"` region (`
  "assertive"` for errors that need immediate attention) — don't rely on a visual-only toast/snackbar
  to be noticed.
- Why this is worth calling out on its own: a sighted user gets an unmistakable visual cue the
  instant a modal opens, a page changes, or a save completes. A screen-reader user's entire model
  of "where am I" is wherever focus currently sits — if focus doesn't move (or moves to the wrong
  place, or gets dropped to `<body>`), the transition effectively didn't happen for them, even
  though the page rendered correctly and every automated visual check passed.

## Color and contrast

- Use theme palette tokens (see
  {{ skill_link("react-router-design-system") }})
  rather than inventing custom colors — MUI's default palette is tuned to meet WCAG AA contrast.
  When adding a **custom** palette role (a status/severity color, a new surface), check its
  contrast against the background it's actually used on before committing to it.
- Never convey state (error, required, success, disabled) through color alone — pair it with an
  icon, text, or `aria-invalid`/`aria-describedby` so a color-blind or non-visual user gets the
  same information.

## Loading and async states are perceivable, not just visible

- The loading/error/data three-state shape already required by
  {{ skill_link("react-router-architecture") }}
  needs a non-visual channel too: an `aria-live` region announcing "Loading…" or the error text,
  not a spinner only a sighted user can see.

## Done means

- Every element that carries meaning has a role and an accessible name a screen reader (or a
  test's `getByRole`) can discover — not because a tool demands it, but because that is what
  "accessible" means.
- Focus is always somewhere deliberate: never dropped to `document.body`, always moved on modal
  open/close, route change, and async completion.
- The touched page is fully operable with a keyboard alone, and every control's purpose is
  announced by a screen reader alone — verify both; correct visual rendering proves neither.

## Verification

- Automated: run an accessibility scan on the touched page/component — `jest-axe` /
  `@axe-core/playwright`, or Playwright's `page.accessibility.snapshot()` — as part of the
  story's QA. This catches missing names/roles/contrast mechanically and cheaply.
- Manual smoke: Tab through the touched page/dialog without touching the mouse — confirm every
  control is reachable, operable, and its purpose is clear from focus alone.

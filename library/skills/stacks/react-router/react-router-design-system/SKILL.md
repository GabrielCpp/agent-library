---
name: react-router-design-system
description: "MUI mechanics for a React Router app: single `createTheme`, palette augmentation, `styleOverrides`, `sx`, `styled`, `useTheme()`. Load when creating the theme, adding a palette role or token, or finding inline hex or pixel values."
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/app/root.tsx,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/theme*.ts,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/theme*.tsx,{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*theme*.ts,{{ template.react_router_path | default("advisor-dashboard") }}/app/theme-augmentation.d.ts'
tags: [react-router, web, standards]
---

# Design System in a React Router + MUI App

This is the **MUI-specific concretization** of
{{ skill_link("ui-design-system") }}.
Read that first for the token taxonomy, provenance, and "extend, don't inline"
discipline — this file says what each of those becomes in a React Router app whose
UI kit is MUI/Emotion. For day-to-day component styling (the `sx` token-vs-literal
rules), see the Styling section of
{{ skill_link("react-router-architecture") }}.

## What "the design system" *is* here

In an MUI app the design system is **one `createTheme(...)` object** — commonly
exported from `root.tsx` (or a dedicated `app/theme.ts`) and handed to a single
`<ThemeProvider>` at the document root. It is not a CSS file, not a set of
constants components import ad hoc. The `Theme` object *is* the source of truth;
`sx`, `styled`, and `useTheme()` are the only ways components read it.

The token layers MUI gives you, and what goes in each:

- **`palette`** — brand (`primary`/`secondary`), semantic (`error`/`warning`/
  `info`/`success`), `text`, `background`, `divider`, `action`, plus **custom
  neutral/role groups** (see augmentation below). This is where surface and border
  greys live — the #1 thing components otherwise inline.
- **`typography`** — `fontFamily`, the weight constants, and the variant scale
  (`h1…h6`, `subtitle*`, `body1/2`, `button`, `caption`, `overline`). Map the
  reference type scale onto these variants; don't invent `fontSize` at call sites.
- **`spacing`** — the base unit behind the numeric spacing API. MUI defaults to an
  8px factor, so `p: 2` = 16px. Keep it; don't pass `"10px"` strings.
- **`shape.borderRadius`** — the base radius. Reference via `borderRadius: 1`
  (= 1× shape) etc., not hardcoded pixel radii.
- **`shadows`** — MUI's elevation array; reference by elevation level, not a
  hand-written `box-shadow`.
- **`components`** — per-component default props and `styleOverrides`: the
  recurring "this is how a Card/Paper/Button looks" rules, set **once** centrally.

## Custom palette roles: module augmentation (the key MUI move)

When the design needs a role MUI's palette doesn't ship — neutral border greys, a
footer color group, an on-brand surface — **add a typed custom palette key** rather
than inlining the hex. This is the MUI-native way to "create a token":

```ts
// app/theme-augmentation.d.ts — makes the custom keys type-safe everywhere
import "@mui/material/styles";
declare module "@mui/material/styles" {
  interface Palette {
    neutral: { border: string; surface: string };
  }
  interface PaletteOptions {
    neutral?: { border?: string; surface?: string };
  }
}
```

```ts
// root.tsx — define the values once, traced to their source
export const theme = createTheme({
  palette: {
    neutral: {
      border: "#e7e7e7",  // <-- was inlined as `1px solid #e7e7e7` in AppLayout
      surface: "#f8f8f8",
    },
  },
});
```

Now components reference the role, and the literal exists in exactly one place:

{% raw %}
```tsx
// Before (forks the design system):
<Box sx={{ bgcolor: "#f8f8f8", borderBottom: "1px solid #e7e7e7", py: "10px" }} />
// After (uses it):
<Box sx={{ bgcolor: "neutral.surface", borderBottom: 1, borderColor: "neutral.border", py: 1.25 }} />
```
{% endraw %}

Augment `Theme`/`ThemeOptions`, `TypographyVariants`, or component prop
interfaces the same way when you add custom typography variants or component
variants.

## Central component look: `components.styleOverrides`

A recurring component appearance is a theme override, not a repeated `sx`. An app can
encode a legacy `.box` panel as an outlined `MuiPaper` override (white bg, 1px
neutral border, no shadow) so every `<Paper variant="outlined">` inherits it.
Reach for `defaultProps` + `styleOverrides` whenever you catch yourself pasting
the same `sx` onto N instances.

## Wiring checklist (MUI specifics)

- **One `ThemeProvider` at the root**, one `<CssBaseline />` under it.
- **SSR/CSS-in-JS:** with React Router framework mode + Emotion, the theme's
  styles must survive document hydration — see
  {{ skill_link("react-router-ssr") }}.
  A correct theme that gets dropped on hydration is still a broken design system.
- **Dark mode:** if supported, build two themes (or a `colorSchemes` config) and
  keep variant colors as palette roles so components flip automatically; never
  branch on mode inside a component with literals.
- **Type safety:** every custom palette/typography/variant key must be declared in
  the augmentation `.d.ts`, or {% raw %}`sx={{ color: "neutral.border" }}`{% endraw %} is untyped and
  silently typo-prone.

## Done means

`createTheme` holds every color/space/radius/shadow the app uses; custom roles are
typed via augmentation; components read them through `sx`/`styled`/`useTheme()`
with zero inline hex or `"<n>px"` literals; and recurring component looks live in
`components.styleOverrides`, not duplicated across call sites.

# Deck mechanics

How `deck.html` is built and checked. Read before the first write of a deck and before any
diagram.

## The file

- One self-contained HTML file: inline CSS, inline JS, inline SVG. No external fonts,
  scripts or images, so it opens offline on the presenting laptop.
- Dark theme. Size type and spacing in `vw`/`vh` with `clamp()`, so the same file fits a
  projector and a laptop.
- Each slide is a `<section>`. Arrow keys and space move between slides, `F` toggles
  fullscreen, and the URL hash holds the slide number so a reload lands on the same slide.
- Zero comments in the HTML, CSS and JS. A hook blocks them.
- A multi-column slide gets `max-width: 80vw`. A `ch`-based max width squeezes the columns
  at 1280x720.

## Diagrams

Draw diagrams as inline SVG with a fixed `viewBox` and CSS classes for each role (a warm box,
a good box, a removed box, a link, a label). A class per role keeps the colours consistent
across slides.

- **Direction is unambiguous.** Each arrow starts at a dot and ends at an arrowhead large
  enough to read from the back of the room.
- **Labels state the relationship in full.** "Execution plan for the current story feeds
  into the grill session for the next story", not "feeds".
- **What went away looks removed.** Draw the boxes for a step that no longer happens in red
  with a dashed border.
- **Rows carry plain names.** A row label says what that item does, on two short lines if
  needed. A ticket key alone tells the audience nothing.

## Rendering and screenshots

Playwright blocks `file://` URLs, so serve the folder:

```bash
python3 -m http.server 8791 --bind 127.0.0.1
```

Run it in the background, then open `http://127.0.0.1:8791/deck.html#N`. Playwright MCP
saves screenshots only inside the session's repo, so delete its `.playwright-mcp` folder
when done.

When Playwright's browser is missing, headless Chrome takes the same screenshot:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new \
  --window-size=1280,720 --screenshot=<scratchpad>/slide-N.png \
  "http://127.0.0.1:8791/deck.html#N"
```

Stop the server when the check is done.

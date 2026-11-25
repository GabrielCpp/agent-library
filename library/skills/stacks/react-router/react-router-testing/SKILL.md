---
name: react-router-testing
description: "Component tests for the React Router + MUI app with Vitest, jsdom and Testing Library: service fakes, router, act, fake timers, Strict Mode. Load when writing or reviewing a `*.test.tsx`, when a component test hangs, or jsdom vs browser"
applyTo: '{{ template.react_router_path | default("advisor-dashboard") }}/app/**/*.test.tsx'
tags: [react-router, web, tests]
---

# React Router web: component tests in jsdom

This skill is the Vitest and jsdom mechanics for {{ skill_link("testing-component") }}, which owns
the line against end-to-end specs, the state matrix and held answers. Its held-answer example is
written for this stack. {{ skill_link("react-router-playwright") }} owns browser specs.

Run the tests with `{{ template.react_router_test_command | default("cd " ~ (template.react_router_path | default("advisor-dashboard")) ~ " && npm test") }}`.

The Vitest config sets `globals: true`, and Testing Library's automatic cleanup depends on it.

## Mount the screen with its real router

Fake at the service context. `ServicesProvider` takes the fake, so the component's own hook runs and
no module is patched. Give the fake only the methods the screen calls. A call to any other method
throws a `TypeError` that names it.

```tsx
function renderScreen(api: Partial<Services["api"]>, url = "/projects/1") {
  const services = { api } as Services;
  return render(
    <ServicesProvider value={services}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/projects/:id" element={<ProjectPage />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </ServicesProvider>,
  );
}

function LocationProbe() {
  return <output>{useLocation().pathname}</output>;
}
```

Assert a navigation by reading the probe with `getByRole("status")`. A `useNavigate` mock proves the
call happened, and the probe proves the route resolved.

A route with a `loader` needs `createRoutesStub`, and under jsdom it fails with `TypeError:
RequestInit: Expected signal to be an instance of AbortSignal`. Node's `Request` rejects jsdom's
`AbortSignal`. Stub `Request` in that test file so it drops the signal. The loader's
`request.signal` then never aborts, so test abort behaviour in a browser spec.

```tsx
const RealRequest = globalThis.Request;
vi.stubGlobal(
  "Request",
  class extends RealRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      const { signal: _signal, ...rest } = init ?? {};
      super(input, rest);
    }
  },
);
```

## Settle with `act`, and assert absence after it

`await act(async () => answer.resolve(value))` is the settle. It flushes the promise chain at any
depth we tried, up to 100 hops. A real timer inside the chain is not flushed, so move that timer onto
the fake clock below. A test never awaits a real `setTimeout`. `findBy*` and `waitFor` wait on the
condition.

Resolve every answer inside `act`. A late answer resolved outside it has not rendered yet, so with
the concurrency rule removed these both stay green:

- `queryByText` straight after the resolve.
- `waitFor(() => expect(...).not.toBeInTheDocument())`, which passes on its first poll.

Use `findBy*` for what appears and `queryBy*` after a settle for what must stay absent. A "not
wrapped in act" warning in a new test means a resolve escaped the settle.

## Hold answers by call, under Strict Mode

Under `StrictMode`, a screen that fetches in an effect calls the service twice on mount and aborts the
first call. An app whose entry renders in `StrictMode` runs that case with
`configure({ reactStrictMode: true })`, and resets it to `false` in `afterEach`.

A `mockReturnValueOnce` sequence breaks in that mode. The double effect takes the first answer, and
that answer is dropped. Record each call and settle the one the test means:

```tsx
const calls: ReturnType<typeof held<Project>>[] = [];
const getProject = vi.fn(() => {
  const answer = held<Project>();
  calls.push(answer);
  return answer.promise;
});

await act(async () => calls.at(-1)!.resolve(project));
```

## Fake only the clock you need

`vi.useFakeTimers()` freezes `setTimeout`, and both `userEvent` and `findBy*` use it to drain. Under
Vitest they hang until the test times out, because Testing Library looks for a global named `jest`
to advance. `advanceTimers` alone does not fix it.

| The component uses | Setup |
| --- | --- |
| `Date` or `setInterval` | `vi.useFakeTimers({ toFake: ["Date", "setInterval", "clearInterval"] })`, which leaves `setTimeout` real |
| `setTimeout`, for debounce or backoff | The block below |

```tsx
vi.useFakeTimers();
vi.stubGlobal("jest", { advanceTimersByTime: vi.advanceTimersByTime });
const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

await user.type(screen.getByRole("searchbox"), "ab");
expect(search).not.toHaveBeenCalled();
await act(async () => vi.advanceTimersByTime(300));
expect(search.mock.calls).toEqual([["ab"]]);
```

Restore in `afterEach` with `vi.useRealTimers()` and `vi.unstubAllGlobals()`. Leave
`shouldAdvanceTime` out of ordering tests, because it lets real time move the clock.

## Drive it with `userEvent`, and scope role queries

`userEvent` respects `pointer-events`, focus and disabled state. `fireEvent` skips all three, so it
can pass on a control the user cannot reach.

MUI's disabled button sets `pointer-events: none`, so a second `user.click` throws once the button
has disabled itself. A double-submit test turns that check off and counts requests:

```tsx
const user = userEvent.setup({ pointerEventsCheck: PointerEventsCheckLevel.Never });
await user.click(saveButton);
await user.click(saveButton);
expect(save).toHaveBeenCalledTimes(1);
```

Role queries get slow on large screens. On a page with 300 MUI buttons, `getByRole` over the document
took about 1.3 s, and `within(region).getByRole` took 16 ms. Vitest's default test timeout is 5 s, so
a screen test that times out with no hung promise often just needs its queries scoped.

## MUI in jsdom

- **Select:** click the `combobox`, then click `await findByRole("option", { name })`.
- **Dialog:** while it is open, everything behind it is `aria-hidden`, so a role query cannot find it
  without `{ hidden: true }`. That matches what a screen reader gets.
- **Closing a dialog:** it stays in the DOM through its transition. Use
  `waitForElementToBeRemoved` before asserting it is gone.
- **Tooltip:** a string `title` is the child's accessible name, so query the icon button by it.

## What jsdom cannot see

jsdom has no layout engine, and imported stylesheets are not applied.

- Every size and rect is 0.
- A class that hides an element through an imported stylesheet leaves it visible to role queries.
  Inline styles are applied.
- `matchMedia`, `ResizeObserver`, `IntersectionObserver` and `scrollIntoView` are undefined. Stub one
  in the test that mounts a component calling it, and treat the stub as a statement that layout is
  outside this test.

Defects in responsive layout, overflow, stylesheet visibility and virtualized rendering stay on the
component side of the line and leave jsdom. They go in a browser spec with the backend faked, as
{{ skill_link("react-router-playwright") }} describes for the mocked suite. Every other state stays
in jsdom, which costs a fraction of a booted browser.

## Review checklist

- [ ] The fake enters through `ServicesProvider`, with no `vi.mock` on the service module.
- [ ] Navigation is asserted through a real router and a location probe.
- [ ] Every held answer resolves inside `act`.
- [ ] Every absence assertion is a `queryBy*` after a settle, outside `waitFor`.
- [ ] In an app rendered in `StrictMode`, a screen that fetches in an effect has a test with
  `reactStrictMode` on.
- [ ] Fake timers are limited to the clock the component uses, and restored in `afterEach`.
- [ ] The test runs with no "not wrapped in act" warning.

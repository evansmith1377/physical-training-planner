# CLAUDE.md

Guidance for AI assistants and contributors working in this repo.

## Project

Physical Training Planner: a static marathon and half-marathon planner hosted on GitHub Pages. `index.html` holds all HTML, CSS, and JS; `assets/` holds the link-preview image. See README.md for features and the plan rules.

```
index.html              the whole app
assets/og-image.png     link-preview image (deployed)
docs/                   README screenshots (not deployed)
scripts/csp_hash.py     keeps the CSP script hash in sync
scripts/screenshots.py  regenerates og-image and screenshots
tests/                  pytest + Playwright suite
.github/workflows/      ci.yml (PRs), deploy.yml (main → Pages)
.github/rulesets/       main.json (branch ruleset; import in repo settings)
```

## Hard constraints

- **No dependencies or network requests in the page.** No frameworks, CDNs, external fonts, analytics, or polyfills from other origins. The CSP `<meta>` enforces this (`default-src 'none'`), and the footer promises it to users.
- **CSP hash.** The inline script is allowed by its SHA-256 hash. After any edit inside `<script>`, run `python scripts/csp_hash.py`, or the page breaks and CI fails. Don't add inline event handlers or a second `<script>`.
- **Never put raw user input into `innerHTML`.** Settings can arrive through the page address (`?miles=…`), so treat every field as untrusted. Parse to numbers, dates or known options first (`setField`, `parsePace`, `parseClock`, `parseISODate`) and render only formatted values.
- **Internal units are fixed:** miles, kg, and minutes per mile. Convert only at the edges: `readCfg` on the way in, `makeUnits()` (`U.D`, `U.pace`, …) on the way out. Daily distances round to 0.5 mi or whole km, and weekly totals are the sum of the displayed values (a test checks this).
- **Medical-safety tone.** Effort comes before pace, and the page never prescribes calorie targets. Warnings must be visible; never silently change a visitor's input.

## Code map (inside the `<script>`)

1. Constants and helpers, then `GOALS` (everything that differs between marathon, half, and durability) and `RANGES`.
2. `makeUnits` (all display formatting) and date helpers (local dates; Monday = 0 to match `DAY_NAMES`).
3. Pace model: Daniels/Gilbert equations; `computePaces(cfg, G)`.
4. `assignDays(cfg)` gives each weekday a role (long, quality, easy, medium, prelong, recovery, rest, off) and picks strength days. `moveRaceDay` adjusts race week when the race date isn't the long-run day.
5. `generatePlan(cfg, U, G)`: week-by-week progression, phases, warnings and notes.
6. `buildWeekDays(...)`: the text for each day cell. `computeCalendar(cfg)` combines everything. It's the single source for the calendar, the summary, and `buildICS`.
7. Form state: `FIELDS` (field name → kind and default), `readCfg`, unit and goal switching, `localStorage` (`ptp.settings.v1`, `ptp.done.v1` for checkmarks), and links that carry settings in the page address.
8. `render()` → `renderHints()`, `renderSummary()`; actions (copy link, `.ics` download, reset/undo, checkmarks); toggletips (`initTips`).

To add a setting: add it to `FIELDS` and the form markup, read it in `readCfg`, and use it in `computeCalendar`/`render`. It will be saved and included in shared links automatically. To add a goal, add a `GOALS` entry and a radio option.

## Front-end conventions

- Use Google's modern-web-guidance (`npx -y modern-web-guidance@latest search "<topic>"`) before adding UI patterns. Prefer Baseline Widely Available features, and give anything newer a fallback.
- Labels go above fields. Short options use radio "pills". Hints are linked with `aria-describedby`, and errors appear on `:user-invalid`. Tap targets are at least 44px and inputs at least 16px (to stop iOS zoom).
- Explanations: anything needed to fill in a field correctly is a visible hint. Background "why" goes in an ⓘ toggletip. No hover-only tooltips.
- Colors come from CSS custom properties: light by default, dark under `prefers-color-scheme`, and print forces light.
- Layout: `.cal-wrap` is a size container. Below 46rem (screen only) the table becomes stacked cards; print always uses the table. Portrait print tightening lives under `body.print-portrait`.
- Print pagination: each guide topic is wrapped in `<div class="topic">` (heading plus its content), which print keeps on one page. Wrap any new topic the same way. Phase rows don't break from the week after them.

## Review lenses

Design, build, test and review every change through each lens that applies, not only the obvious one. Name the lenses you used in the PR, and say what each one changed or caught.

**Engineering and operations**

| Lens | Asks |
|---|---|
| Principal engineer / systems architect | Is this the simplest change at the right layer? Does it keep `computeCalendar` the single source of truth, internal units fixed, and `index.html` self-contained? |
| QA / test engineer | What would break it: edge values, both unit systems, all three goals, dates and time zones, odd links? Is there a test that fails without the change? |
| SecOps / AppSec | Can untrusted input (links, `localStorage`, pasted text) reach `innerHTML`, the CSP, or the `.ics` file? Are actions SHA-pinned, and is the workflow `permissions:` block least-privilege? |
| Supply chain | Is the new dependency (test-only) needed? Is it pinned and covered by Dependabot? Never add one to the page. |
| DevOps / release | Does CI stay fast and deterministic? Does the deploy still work on `main`? Will it roll back cleanly? |
| Cloud / site reliability | GitHub Pages hosting: caching of `index.html`, the `og:image` path, 404s, behavior on a slow or offline phone. |
| Privacy | Settings and checkmarks stay in the browser. No new storage keys without a migration plan. Shared links carry only plan settings. |
| Performance | No layout jank on input, no wasted renders, print still fast for long plans. |

**Design and content**

| Lens | Asks |
|---|---|
| UX / interaction designer | Is the next step obvious? Do defaults suit most people? Can a mistake be undone? |
| Accessibility specialist | Keyboard, screen reader, contrast in light/dark/print, 44px targets, axe checks pass. |
| Content designer | Plain language, short labels, visible hints, consistent terms (see the glossary). |
| Visual / print designer | Phone width, dark mode, Letter and A4 in both orientations, no awkward page breaks. |
| Localization | Miles and km, Sunday and Monday week starts, paper sizes, local dates. |

**People**

| Lens | Asks |
|---|---|
| User voice | What did users actually report (issues, quoted feedback)? Does the change solve their problem in their words? |
| Personas | Walk the change through each persona below. |
| Running coach / certified trainer | Is the progression conservative (weekly and long-run growth, cutbacks, taper) and the effort guidance sound? |
| Sports medicine / physiotherapy | Are injury, illness and heat warnings visible? Does anything push through pain or ignore a red flag? |
| Sports dietitian | No calorie targets, no restriction messaging; fueling advice matches the cited position stands. |
| Exercise physiologist | Do the pace equations, intensity zones and taper match the sources in the guide? |

The expert lenses are for checking, not a stand-in for a real professional. Any change to plan rules, safety warnings, or nutrition text must cite a source in the PR. It must also be flagged for review by a qualified person before merge.

**Personas**

- **Emily (the defaults):** 25 mi a week, 13 mi long run, stepping up from the half to a first marathon in 22 weeks, 5 run days, 2 strength days. Resetting to defaults should always bring back her plan.
- **New runner:** 12–15 mi a week, aiming at a first half. Needs reassurance, clear effort cues, and no jargon without an explanation.
- **High-mileage runner:** 50–70 mi a week, according to Strava. Needs wide input ranges, and doesn't want to be talked down to.
- **Returning or older runner:** coming back from injury or a break. Needs conservative ramps, visible red flags, and an easy way to repeat a week.
- **Metric runner abroad:** km, Monday weeks, A4 paper.
- **Phone-only runner:** opens a shared link on a phone and ticks off workouts there.
- **Keyboard / screen-reader user:** the whole flow works without a mouse or sight.
- **Coach or friend sharing a plan:** sends a link and prints a copy, expecting the recipient to see exactly the same plan.

## Workflow for every change

1. **Scope.** Start from the issue. Restate the user's problem, and pick the lenses and personas that apply.
2. **Design.** Choose the smallest change that solves the problem. Check modern-web-guidance before new UI patterns.
3. **Build.** Work on a branch, run `python scripts/csp_hash.py` after script edits, and add or update tests.
4. **Verify.** Run `pytest -q`. For UI work, check phone width, dark mode and print. Run `python scripts/screenshots.py` if the UI changed noticeably.
5. **Review.** Run `/simplify`, then `/code-review`. Fix what's real, and note what you skipped and why. Use `/security-review` when a change touches input handling, storage, links, the CSP, or workflows.
6. **PR.** Fill in the template, link the issue (`Closes #n`), and list the lenses used.
7. **Loop.** Wait for CI. Fix failures at their root cause and answer every review thread. Repeat until CI is green and nothing is open.
8. **Merge.** Squash-merge once CI is green and no threads remain open, then confirm the Pages deploy succeeded.

## Verifying changes

Run `pytest -q` (see README → Development for setup). CI runs the same suite on every PR and before each deploy.

Tests can't judge visual polish. For layout changes, also look at the page at phone width, in dark mode, and in print preview. If the UI changed noticeably, run `python scripts/screenshots.py`.

Add a test for any new behavior. The `make_page(now=...)` fixture freezes the browser clock for date logic.

In tests, wait with Playwright's `expect(...)` assertions, not `page.wait_for_function("...")`: the page's CSP blocks the `eval` that string-based waits need. Popover `toggle` events are async, so assert popover state and `aria-expanded` with `expect`.

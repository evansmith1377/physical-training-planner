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

Design, build, test and review every change through each lens that applies, not only the obvious one. Each lens adds questions on top of the Hard constraints above.

**Engineering and operations**
- **Principal engineer / systems architect:** is this the simplest change, at the right layer, with no duplicated logic?
- **QA / test engineer:** what breaks it (edge values, both unit systems, all three goals, dates and time zones, odd links)? Does a test fail without the change?
- **SecOps / supply chain:** can untrusted input reach markup, the CSP or the `.ics` file? Are actions SHA-pinned, workflow `permissions:` least-privilege, and any new test dependency pinned and covered by Dependabot?
- **DevOps / cloud ops:** CI stays fast and deterministic; the GitHub Pages deploy, caching, `og:image` path and rollback still work.
- **Privacy:** no new storage keys without a migration plan; shared links should carry plan settings only, never personal data such as body weight.
- **Performance:** no jank on input, no wasted renders, print stays fast for long plans.

**Design and content**
- **UX / interaction designer:** is the next step obvious, do defaults suit most people, can a mistake be undone?
- **Accessibility specialist:** keyboard and screen reader, contrast in light, dark and print, axe checks pass.
- **Content designer:** plain language, short labels, consistent terms (see the glossary).
- **Visual / print designer and localization:** phone width, dark mode, miles and km, Sunday and Monday weeks, Letter and A4 in both orientations.

**People and domain experts**
- **User voice:** what did users actually report? Solve their problem in their words.
- **Running coach / exercise physiologist:** is the progression conservative (weekly and long-run growth, cutbacks, taper), and do the paces and zones match the guide's sources?
- **Sports medicine / physiotherapy:** are injury, illness and heat warnings visible? Does anything push through pain or ignore a red flag?
- **Sports dietitian:** no restriction messaging; fueling advice matches the cited position stands.

The expert lenses are for checking, not a stand-in for real professionals. Changes to plan rules, safety warnings or nutrition text must cite a source and be flagged in the PR for review by a qualified person before merge.

**Personas** (walk each change through the ones it affects)
- **Emily (the defaults):** 25 mi a week, 13 mi long run, stepping up from the half to a first marathon in 22 weeks, 5 run days, 2 strength days. Resetting to defaults always brings back her plan.
- **New runner:** 12–15 mi a week, aiming at a first half. Needs reassurance, clear effort cues, and no unexplained jargon.
- **High-mileage runner:** 50–70 mi a week, according to Strava. Needs wide input ranges, and doesn't want to be talked down to.
- **Returning or older runner:** coming back from injury or a break. Needs conservative ramps, visible red flags, and an clear guidance on repeating a week.
- **Phone-only runner:** opens a shared link on a phone and ticks off workouts there.
- **Coach or friend sharing a plan:** sends a link and prints a copy, expecting the recipient to see exactly the same plan.

## Workflow for every change

1. Start from the issue, if there is one. Restate the user's problem, and pick the lenses and personas that apply.
2. Build the smallest change that solves it on a branch, following the conventions above. Verify it as described in *Verifying changes*.
3. Run `/simplify`, then `/code-review`. Fix what's real, and note what you skipped and why. Also run `/security-review` when a change touches input handling, storage, links, the CSP or workflows.
4. Open a PR from the template, with `Closes #n` if there's an issue. Request a reviewer for any expert-review flag: the ruleset doesn't require approvals, so that gate is on you.
5. Loop on CI and review threads until CI is green and every thread is answered and resolved. The ruleset in `.github/rulesets/main.json` requires the `test` check and resolved threads before merge.
6. Squash-merge, then confirm the Pages deploy succeeded.

## Verifying changes

Run `pytest -q` (see README → Development for setup). CI runs the same suite on every PR and before each deploy.

Tests can't judge visual polish. For layout changes, also look at the page at phone width, in dark mode, and in print preview. If the UI changed noticeably, run `python scripts/screenshots.py`.

Add a test for any new behavior. The `make_page(now=...)` fixture freezes the browser clock for date logic.

In tests, wait with Playwright's `expect(...)` assertions, not `page.wait_for_function("...")`: the page's CSP blocks the `eval` that string-based waits need. Popover `toggle` events are async, so assert popover state and `aria-expanded` with `expect`.

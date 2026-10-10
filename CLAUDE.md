# CLAUDE.md

Guidance for AI assistants and contributors working in this repo.

## Project

A static, single-file marathon training planner: `index.html` holds all HTML, CSS, and JS. It is meant for public hosting (for example, GitHub Pages). See README.md for features and the plan rules.

## Hard constraints

- **Single file, zero dependencies.** No build step, frameworks, CDNs, external fonts, or polyfills loaded from other origins. The page must make no network requests; the footer promises this to users.
- **Never put raw user input into `innerHTML`.** Settings can arrive through the page address (`?miles=…`), so treat every field as untrusted. Parse text to numbers or enums first (`parsePace`, `parseClock`, `setField` option checks) and render only formatted values.
- **Internal units are fixed:** miles, kg, and minutes per mile. Convert only at the edges: `readCfg` on the way in, `makeUnits()` (`U.D`, `U.pace`, …) on the way out. Daily distances round to 0.5 mi or whole km. Weekly totals are the sum of the displayed values.
- **Medical-safety tone.** Effort comes before pace, and the page never prescribes calorie targets. Warnings must be visible; never silently change a visitor's input.

## Code map (inside the `<script>`)

1. Constants and helpers, then `makeUnits`, which handles all display formatting.
2. Pace model: Daniels/Gilbert equations; `computePaces(cfg)`.
3. `assignDays(cfg)`: assigns each weekday a role (long, quality, easy, medium, prelong, recovery, rest, off) and picks the strength days.
4. `generatePlan(cfg, U)`: week-by-week progression, phases, warnings and notes.
5. `buildWeekDays(...)`: the text for each day cell.
6. Form state: `FIELDS` (field name → kind and default), `readCfg`, unit switching, `localStorage` (`marathonCalendar.v2`), and links that carry settings in the page address.
7. `render()`: the calendar, summary, warnings, dynamic hints and the status message.
8. Toggletips (`initTips`): native `popover` positioned by script, with a click fallback when the Popover API is missing.

To add a setting: add it to `FIELDS` and the form markup, read it in `readCfg`, and use it in `render`. It will be saved and included in shared links automatically.

## Front-end conventions

- Use Google's modern-web-guidance (`npx -y modern-web-guidance@latest search "<topic>"`) before adding UI patterns. Prefer Baseline Widely Available features, and give anything newer a fallback.
- Labels go above fields. Short options use radio "pills". Hints are linked with `aria-describedby`, and errors appear on `:user-invalid`. Tap targets are at least 44px and inputs at least 16px (to stop iOS zoom).
- Explanations: anything needed to fill in a field correctly is a visible hint. Background "why" goes in an ⓘ toggletip. No hover-only tooltips.
- Colors come from CSS custom properties: light by default, dark under `prefers-color-scheme`, and print forces light.
- Layout: `.cal-wrap` is a size container. Below 46rem (screen only) the table becomes stacked cards; print always uses the table. Portrait print tightening lives under `body.print-portrait`.

## Verifying changes

There is no test suite. Before committing:

1. Open `index.html`, change several inputs, and check the browser console has no errors.
2. Check widths of 320, 375, and 1280px: no horizontal scroll, and the week headers stay sticky on mobile.
3. Print preview in landscape and portrait: the header row repeats, the reference guide starts on a new page, and the guide disappears when its box is unchecked.
4. Switch units back and forth: the values should round-trip.
5. Turn on dark mode.
6. Try a shared link with odd parameters, for example `?miles=abc&goal=<x>`. It should ignore the bad values safely.

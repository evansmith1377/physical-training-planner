# Marathon Training Calendar

A single-page, printable marathon training planner. Enter your current mileage and how you like to train, and it builds a week-numbered calendar (Week 1, Week 2, … no fixed dates) that you can print or save as a PDF in landscape or portrait.

It's one self-contained `index.html` file with no build step, no dependencies, and no network requests.

## Features

- **Readiness-based plan.** Four phases: Stabilize, Build durability, Marathon-specific, and Taper. Each phase starts with the "readiness gate" a runner should meet before moving on. Because weeks are numbered rather than dated, repeating a week is expected, not a failure.
- **Two goals.** "Marathon at end" builds through a taper to race week. "Build durability" builds a base (capped at 35 mi/week and a 16 mi long run) with no race.
- **Your week, your way.**
  - 4, 5, or 6 running days.
  - Saturday or Sunday long run, and any rest day.
  - 0–2 strength sessions placed on easy days.
  - Cutbacks every 3rd or 4th week, and a 2- or 3-week taper.
- **US or metric units.** Switching converts the values you've already entered.
- **Optional pace guidance.** From a recent race result, a known easy pace, or a goal marathon pace, the calendar shows suggested easy, tempo, steady and marathon paces next to the effort cues.
- **Print-ready.** Choose landscape or portrait, US Letter or A4. The calendar header row repeats on each printed page, and each day has a checkbox for ticking off.
  - An optional reference guide prints after the calendar, covering effort, nutrition, strength exercises, hydration, safety and sources.
- **Works on phones.** On narrow screens each week becomes a stacked card with a sticky header. Supports light and dark mode.
- **Shareable.** "Copy link to this plan" puts all settings in the page address.
- **Private.** Settings are saved only in the visitor's browser (`localStorage`). Nothing is sent anywhere.

## Usage

Open `index.html` in a browser. To host it, upload the file to any static host. For GitHub Pages: **Settings → Pages → Deploy from a branch → `main` / root**.

## How the plan is built

All distances are calculated internally in miles and converted for display.

| Rule | Value |
|---|---|
| Phase 1 (Stabilize) | 3 weeks at your current distance and long run (long run up to 55% of the week) |
| Weekly build | +8% per build week (min 1.5 mi, max 3 mi), up to the peak |
| Long run | +1 mi per build week at most, kept to ≤ 50% of the week; alternates between the peak and about 85% of it once reached |
| Cutback weeks | About 25% less distance and about 28% shorter long run, every 3rd or 4th week |
| Marathon-specific block | Up to 16 weeks including taper (warning below 14) |
| Taper | 3 weeks: 80% → 65% of peak → race week (2 weeks: 72% → race week) |
| Quality | Strides in Phase 1 and cutbacks; progressive tempo in Phase 2; alternating tempo and marathon-effort sessions in Phase 3 |

The page warns instead of silently adjusting when inputs conflict. Examples: a plan too short for a marathon block, a rest day on the long-run day, a peak below your current mileage, or a projected base that misses the readiness gate.

**Paces** use the Daniels/Gilbert race-equivalency equations: easy covers about 62–70% of aerobic capacity, tempo about 88%, and the marathon range is the predicted pace plus a 15 s/mi buffer. These formulas tend to be optimistic for first marathons, and the page says so.

## Browser support

Current versions of Chrome, Edge, Firefox, and Safari. The ⓘ info bubbles use the native Popover API, with a script fallback for older browsers.

## Disclaimer

General fitness guidance only. This is not medical advice, and it does not replace an individualized plan from a coach, clinician, or sports dietitian.

## License

Released into the public domain under [the Unlicense](LICENSE).

"""End-to-end checks for index.html. Run with: pytest -q"""
import importlib.util
import re
import struct
from datetime import datetime
from pathlib import Path

import pytest
from playwright.sync_api import expect
from axe_playwright_python.sync_playwright import Axe

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 10, 10, 12, 0)  # a Saturday; fixes "weeks until race" math


def settle(page):
    """Renders run on the next animation frame."""
    page.wait_for_timeout(120)


def pick(page, name, value):
    page.check(f'input[name="{name}"][value="{value}"]')
    settle(page)


def fill(page, selector, value):
    page.fill(selector, value)
    settle(page)


def values(page, *ids):
    return [page.input_value(f"#{i}") for i in ids]


def column(page, day):
    """Index (1-based, including the Week column) of a weekday in the calendar header."""
    heads = page.locator("#calHead th").all_inner_texts()
    return heads.index(day) + 1


def cell_text(page, week, day):
    return page.inner_text(f'tr.week[data-week="{week}"] > :nth-child({column(page, day)})')


# ---------------------------------------------------------------- static checks

def test_csp_hash_is_current():
    spec = importlib.util.spec_from_file_location("csp_hash", ROOT / "scripts" / "csp_hash.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert f"script-src '{mod.expected_hash(html)}'" in html, "Run: python scripts/csp_hash.py"


def test_preview_image_exists_with_og_size():
    png = (ROOT / "assets" / "og-image.png").read_bytes()
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (1200, 630)
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'content="https://evansmith1377.github.io/physical-training-planner/assets/og-image.png"' in html


# ---------------------------------------------------------------- defaults & layout

def test_defaults_render_marathon_plan(page):
    assert page.title().startswith("Physical Training Planner")
    assert page.inner_text("h1") == "Physical Training Planner"
    assert page.inner_text("#summary").startswith("22-week plan · marathon in Week 22")
    assert page.locator("#calHead th").all_inner_texts()[1] == "Sunday"
    assert page.locator("tr.week").count() == 22
    assert "RACE · 26.2 mi" in cell_text(page, 22, "Saturday")
    peak = page.evaluate("() => { const c = computeCalendar(readCfg()); return [c.plan.maxL, Math.round(c.plan.maxM)]; }")
    assert peak == [18, 38]


@pytest.mark.parametrize("query,unit", [
    ("", "mi"),
    ("?units=metric&miles=40&longrun=21&peakMiles=61&peakLong=29", "km"),
    ("?goal=half&days=4", "mi"),
    ("?units=metric&goal=half&days=6&miles=40&longrun=21&peakMiles=48&peakLong=21", "km"),
])
def test_week_totals_equal_sum_of_days(make_page, query, unit):
    page = make_page(query)
    for row in page.locator("tr.week").all():
        total = float(re.match(r"([\d.]+)", row.locator(".tot").inner_text()).group(1))
        days = sum(float(m) for m in re.findall(rf"· ([\d.]+) {unit}", " ".join(row.locator("td:not(.race) .t").all_inner_texts())))
        assert abs(total - days) < 0.01, row.locator(".n").inner_text()


@pytest.mark.parametrize("width", [320, 375, 768, 1280])
def test_no_horizontal_scroll(make_page, width):
    page = make_page(width=width, mobile=width < 800)
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_week_header_sticks_on_mobile(make_page):
    page = make_page(width=375, mobile=True)
    page.evaluate("""() => { const r = document.querySelector('tr.week td.day:nth-child(6)').getBoundingClientRect(); scrollBy(0, r.top - 100); }""")
    assert page.evaluate("Math.round(document.querySelector('tr.week th.wkcell').getBoundingClientRect().top)") == 0


@pytest.mark.parametrize("width", [320, 375, 1280])
def test_checkbox_never_overlaps_text(make_page, width):
    page = make_page("?raceTime=1%3A50%3A00", width=width, mobile=width < 800)
    overlaps = page.evaluate("""() => [...document.querySelectorAll('td.day')].filter(td => {
        const box = td.querySelector('.done'); if (!box) return false;
        const b = box.getBoundingClientRect();
        return [...td.querySelectorAll(':scope > div > div')].some(el => {
            const r = el.getBoundingClientRect();
            return r.right > b.left + 1 && r.left < b.right && r.bottom > b.top && r.top < b.bottom;
        });
    }).length""")
    assert overlaps == 0


def test_dark_mode_changes_colors(make_page):
    light = make_page().evaluate("getComputedStyle(document.body).backgroundColor")
    dark = make_page(dark=True).evaluate("getComputedStyle(document.body).backgroundColor")
    assert light != dark


# ---------------------------------------------------------------- inputs, units, links

def test_units_round_trip(page):
    pick(page, "units", "metric")
    assert values(page, "miles", "longrun", "peakMiles", "peakLong") == ["40", "21", "61", "29"]
    assert page.locator("tr.week .tot").first.inner_text().endswith("km")
    pick(page, "units", "us")
    assert values(page, "miles", "longrun", "peakMiles", "peakLong") == ["25", "13", "38", "18"]


def test_hostile_link_params_are_ignored(make_page):
    page = make_page("?miles=abc&goal=%3Cimg%20src=x%20onerror=alert(1)%3E&weeks=99"
                     "&anchorDate=%3Cb%3E&raceTime=%3Cscript%3E&units=metric")
    assert page.locator("main img, main script, main b").count() == 0
    assert page.evaluate("document.querySelector('input[name=goal]:checked').value") == "marathon"
    assert values(page, "weeks", "anchorDate") == ["30", ""]
    assert page.evaluate("document.querySelector('input[name=units]:checked').value") == "metric"


def test_shared_link_restores_settings(page, make_page):
    pick(page, "goal", "half")
    fill(page, "#anchorDate", "2027-04-11")
    pick(page, "orientation", "portrait")
    url = page.evaluate("shareUrl()")
    other = make_page("?" + url.split("?", 1)[1])
    assert other.evaluate("snapshot()") == page.evaluate("snapshot()")


def test_reset_and_undo(page):
    pick(page, "units", "metric")
    fill(page, "#weight", "70")
    page.click("#resetBtn")
    settle(page)
    assert values(page, "miles", "peakMiles", "peakLong", "weight") == ["25", "38", "18", ""]
    page.click("#undoBtn")
    settle(page)
    assert values(page, "miles", "peakMiles", "peakLong", "weight") == ["40", "61", "29", "70"]


def test_rest_day_cannot_match_long_day(page):
    assert page.evaluate("[...document.getElementById('restDay').options].filter(o => o.disabled).map(o => o.text)") == ["Saturday"]
    pick(page, "longDay", "6")  # Sunday long run while rest day is Sunday
    assert page.evaluate("document.getElementById('restDay').selectedOptions[0].text") == "Monday"
    assert "moved to Monday" in page.inner_text("#warnings")


def test_toggletip_opens_and_closes(page):
    # expect() polls from outside the page: the popover's toggle event is async, and the CSP blocks
    # the eval that wait_for_function would need.
    btn, tip = page.locator('button[popovertarget="tipCut"]'), page.locator("#tipCut")
    btn.click()
    expect(tip).to_be_visible()
    expect(btn).to_have_attribute("aria-expanded", "true")
    page.keyboard.press("Escape")
    expect(tip).to_be_hidden()
    expect(btn).to_have_attribute("aria-expanded", "false")


# ---------------------------------------------------------------- goals

def test_half_marathon_plan(page):
    pick(page, "goal", "half")
    assert values(page, "weeks", "peakMiles", "peakLong") == ["16", "30", "13"]
    visible = page.evaluate("[...document.querySelectorAll('input[name=taper]')].filter(i => i.closest('label').checkVisibility()).map(i => i.value)")
    assert visible == ["1", "2"]
    assert page.evaluate("document.querySelector('input[name=taper]:checked').value") == "2"
    assert page.inner_text("#summary").startswith("16-week plan · half marathon in Week 16")
    assert "RACE · 13.1 mi" in cell_text(page, 16, "Saturday")
    assert "Phase 3 · Half-specific" in page.inner_text("#calBody")
    assert "Half-marathon effort" in page.inner_text("#calBody")


def test_goal_switch_keeps_custom_values(page):
    fill(page, "#peakMiles", "33")
    pick(page, "goal", "half")
    assert values(page, "peakMiles") == ["33"]


def test_durability_build(page):
    pick(page, "goal", "base")
    assert values(page, "peakMiles", "peakLong") == ["35", "16"]
    assert "RACE" not in page.inner_text("#calBody")
    assert page.is_hidden("#taperField")
    fill(page, "#peakMiles", "45")
    assert "cap weekly distance at 35 mi" in page.inner_text("#summary")


@pytest.mark.parametrize("query,expect", [
    ("?goal=half&taper=3", "uses a 1 or 2-week taper"),
    ("?miles=100", "was outside the allowed range, so it's set to 45"),
    ("?weeks=99", "was outside the allowed range, so it's set to 30"),
])
def test_link_adjustments_are_announced(make_page, query, expect):
    page = make_page(query)
    assert expect in page.inner_text("#warnings")
    fill(page, "#longrun", "12")  # notices clear once the visitor edits something
    assert expect not in page.inner_text("#warnings")


def test_typed_weeks_below_minimum_warns(page):
    pick(page, "goal", "base")
    fill(page, "#weeks", "3")
    assert "needs at least 6 weeks" in page.inner_text("#warnings")
    assert page.locator("tr.week").count() == 6


def test_switching_race_and_durability_clears_the_date(make_page):
    page = make_page(now=NOW)
    fill(page, "#anchorDate", "2027-03-13")
    pick(page, "goal", "base")
    assert values(page, "anchorDate") == [""]
    assert "Cleared the race date" in page.inner_text("#warnings")


def test_goal_switch_reports_every_adjustment(make_page):
    page = make_page("?goal=base&taper=3&anchorDate=2026-10-14", now=NOW)
    pick(page, "goal", "half")
    warnings = page.inner_text("#warnings")
    assert "Taper set to 2 weeks" in warnings and "Cleared the start date" in warnings


@pytest.mark.parametrize("typed", ["0", ""])
def test_empty_or_zero_weeks_warns(page, typed):
    fill(page, "#weeks", typed)
    assert "Plan length isn't set, so this calendar uses 22 weeks" in page.inner_text("#warnings")


def test_clamp_notice_uses_clean_label(make_page):
    page = make_page("?weight=9999")
    assert "Body weight (lb) was outside the allowed range" in page.inner_text("#warnings")


def test_too_few_weeks_warns_and_uses_minimum(page):
    fill(page, "#weeks", "8")
    assert "needs at least 10 weeks" in page.inner_text("#warnings")
    assert page.locator("tr.week").count() == 10


def test_plan_invariants_across_settings(page):
    """Every combination stays sane: right length, race last, long run within caps, no NaN text."""
    problems = page.evaluate("""() => {
      const bad = [];
      for (const goal of ['marathon', 'half', 'base']) for (const days of [4, 5, 6]) for (const cutEvery of [3, 4])
      for (const longDay of [5, 6]) for (const weeks of [10, 16, 24]) for (const start of [[12, 4], [25, 13], [45, 20]]) {
        const G = GOALS[goal];
        const cfg = { units: 'us', startMiles: start[0], startLong: start[1], peakMiles: G.defaults.us[0], peakLong: G.defaults.us[1],
          goal, weeks, cutEvery, taper: G.defTaper || 0, days, longDay, restDay: longDay === 6 ? 0 : 6, strength: 2,
          raceDist: 21097.5, weekStart: 'sun', anchor: null };
        const cal = computeCalendar(cfg), label = JSON.stringify({ goal, days, cutEvery, longDay, weeks, start });
        if (cal.weeks.length !== weeks) bad.push('length ' + label);
        if (G.race && !cal.weeks[weeks - 1].wk.race) bad.push('race not last ' + label);
        for (const { wk, cells } of cal.weeks) {
          if (wk.long > Math.max(G.capL, start[1]) + 0.01) bad.push(`long ${wk.long} wk${wk.n} ` + label);
          const runs = cells.filter(c => c.workout && c.cls !== 'off').length;
          if (!wk.race && runs !== days) bad.push(`runs ${runs} wk${wk.n} ` + label);
          if (cells.some(c => /NaN|undefined/.test(c.t + c.det + c.pace + c.s))) bad.push(`text wk${wk.n} ` + label);
        }
      }
      return bad.slice(0, 10);
    }""")
    assert problems == []


def test_suggested_paces(page):
    page.click("#paceDetails summary")
    fill(page, "#raceTime", "1:50:00")
    summary = page.inner_text("#summary")
    assert "Marathon effort 8:41–8:56/mi" in summary and "Tempo ~8:08/mi" in summary
    pick(page, "goal", "half")
    assert "Equivalent half marathon ≈ 1:50" in page.inner_text("#summary")


# ---------------------------------------------------------------- dates & calendar export

def test_race_date_sets_week_dates_and_race_day(make_page):
    page = make_page(now=NOW)
    fill(page, "#anchorDate", "2027-03-14")  # a Sunday; long runs default to Saturday
    assert page.locator("#calHead th").all_inner_texts()[1] == "Monday"  # weeks end on race day
    assert page.evaluate("[...document.querySelectorAll('input[name=weekStart]')].every(i => i.disabled)")
    assert "RACE · 26.2 mi" in cell_text(page, 22, "Sunday")
    assert "Mar 14" in cell_text(page, 22, "Sunday")
    assert "Race day is a Sunday" in page.inner_text("#summary")
    assert page.inner_text("#matchWeeksBtn") == "Use 23 weeks (starts this week)"
    page.click("#matchWeeksBtn")
    settle(page)
    assert values(page, "weeks") == ["23"]
    assert page.inner_text('tr.week[data-week="1"] .dates') == "Oct 5 – Oct 11"


@pytest.mark.parametrize("days", ["4", "5", "6"])
@pytest.mark.parametrize("race,day", [
    ("2027-03-08", "Monday"), ("2027-03-09", "Tuesday"), ("2027-03-10", "Wednesday"),
    ("2027-03-11", "Thursday"), ("2027-03-12", "Friday"), ("2027-03-13", "Saturday"), ("2027-03-14", "Sunday"),
])
def test_race_week_sharpening_is_at_least_3_days_out(make_page, race, day, days):
    page = make_page(f"?days={days}", now=NOW)
    fill(page, "#anchorDate", race)  # long runs default to Saturday
    weeks = int(values(page, "weeks")[0])
    heads = page.locator("#calHead th").all_inner_texts()[1:]
    assert heads[-1] == day and "RACE" in cell_text(page, weeks, day)  # race day ends the week
    sharpen = [d for d in heads if "at least 3 days before the race" in cell_text(page, weeks, d)]
    assert len(sharpen) == 1 or "no room for the short sharpening session" in page.inner_text("#summary")
    assert len(sharpen) <= 1
    for d in sharpen:
        assert heads.index(day) - heads.index(d) >= 3
    before = cell_text(page, weeks, heads[-2])  # the day before the race is a shakeout or a day off
    assert before.startswith(("Shakeout", "Rest", "Off")), before


def test_past_race_date_warns(make_page):
    page = make_page(now=NOW)
    fill(page, "#anchorDate", "2026-01-04")
    assert "already passed" in page.inner_text("#warnings")


def test_start_date_for_durability_build(make_page):
    page = make_page(now=NOW)
    pick(page, "goal", "base")
    fill(page, "#anchorDate", "2026-10-14")  # Wednesday; weeks start Sunday
    assert page.inner_text('tr.week[data-week="1"] .dates') == "Oct 11 – Oct 17"


def unfold(ics):
    return re.sub(r"\r\n ", "", ics).split("\r\n")


def test_ics_export(make_page):
    page = make_page(now=NOW)
    fill(page, "#anchorDate", "2027-03-14")
    with page.expect_download() as dl:
        page.click("#icsBtn")
    assert dl.value.suggested_filename == "training-plan.ics"
    ics = Path(dl.value.path()).read_bytes().decode("utf-8")
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert "\n" not in ics.replace("\r\n", ""), "bare line feeds"
    assert max(len(line.encode()) for line in ics.split("\r\n")) <= 75
    lines = unfold(ics)
    assert lines.count("BEGIN:VEVENT") == page.locator("input[data-done]").count()
    uids = [l for l in lines if l.startswith("UID:")]
    assert len(uids) == len(set(uids))
    race = lines.index("SUMMARY:RACE · 26.2 mi")
    assert "DTSTART;VALUE=DATE:20270314" in lines[race - 3:race]
    assert "downloaded with" in page.inner_text("#actionStatus")


def test_ics_events_match_calendar_and_escape_text(make_page):
    page = make_page(now=NOW)
    fill(page, "#anchorDate", "2027-03-13")
    with page.expect_download() as dl:
        page.click("#icsBtn")
    lines = unfold(Path(dl.value.path()).read_bytes().decode("utf-8"))
    events, ev = [], {}
    for line in lines:
        if line == "BEGIN:VEVENT":
            ev = {}
        elif line == "END:VEVENT":
            events.append(ev)
        elif ":" in line:
            k, v = line.split(":", 1)
            ev[k] = v
    # Every event lands on the date of the calendar cell it came from.
    cells = page.evaluate("""() => { const cal = computeCalendar(readCfg()); const out = {};
        for (const { wk, cells } of cal.weeks) cells.forEach((c, d) => { if (c.workout) out[ymd(cal.dateOf(wk.n, d))] = c.t; });
        return out; }""")
    got = {e["DTSTART;VALUE=DATE"]: e["SUMMARY"].replace("\\,", ",").replace("\\;", ";") for e in events}
    assert got == cells
    # Text values never contain unescaped separators.
    for e in events:
        for key in ("SUMMARY", "DESCRIPTION"):
            assert not re.search(r"(?<!\\)[;,]", e[key]), e[key]
    assert any("\\;" in e["DESCRIPTION"] for e in events)
    # Re-exporting the same plan gives the same UIDs; a different plan gives different ones.
    uids = {e["UID"] for e in events}
    with page.expect_download() as dl2:
        page.click("#icsBtn")
    assert uids == {l[4:] for l in unfold(Path(dl2.value.path()).read_bytes().decode("utf-8")) if l.startswith("UID:")}
    fill(page, "#miles", "30")
    with page.expect_download() as dl3:
        page.click("#icsBtn")
    assert not uids & {l[4:] for l in unfold(Path(dl3.value.path()).read_bytes().decode("utf-8")) if l.startswith("UID:")}


def test_ics_needs_a_date(page):
    page.click("#icsBtn")
    assert "Add a race date first" in page.inner_text("#actionStatus")
    assert page.evaluate("document.activeElement.id") == "anchorDate"


def test_checkmarks_persist_and_clear(page):
    boxes = page.locator('tr.week[data-week="1"] input[data-done]')
    boxes.nth(0).check()
    boxes.nth(1).check()
    assert page.inner_text('tr.week[data-week="1"] .prog') == "2/5 done"
    page.reload()
    page.wait_for_selector("#calBody tr.week")
    assert page.locator("input[data-done]:checked").count() == 2
    assert page.locator("td.is-done").count() == 2
    page.once("dialog", lambda d: d.accept())
    page.click("#clearDoneBtn")
    settle(page)
    assert page.locator("input[data-done]:checked").count() == 0
    assert page.is_hidden("#clearDoneBtn")


def test_checkmarks_follow_the_workout_not_the_grid(make_page):
    page = make_page(now=NOW)
    long_box = f'tr.week[data-week="1"] > :nth-child({column(page, "Saturday")}) input[data-done]'
    page.check(long_box)
    pick(page, "goal", "half")  # week 1 Saturday is still the long run: tick stays
    assert page.is_checked(long_box)
    pick(page, "longDay", "6")  # Saturday is no longer the long run: no tick on whatever is there now
    assert page.locator("input[data-done]:checked").count() == 0
    assert page.is_hidden("#clearDoneBtn")  # nothing ticked on screen
    pick(page, "longDay", "5")  # back again: the tick returns
    assert page.is_checked(long_box)


def test_undated_ticks_move_onto_dates_when_a_date_is_added(make_page):
    page = make_page(now=NOW)
    sat = f'tr.week[data-week="1"] > :nth-child({column(page, "Saturday")}) input[data-done]'
    page.check(sat)
    fill(page, "#anchorDate", "2027-03-13")  # week 1 now has real dates; the long run tick stays
    assert page.is_checked(f'tr.week[data-week="1"] > :nth-child({column(page, "Saturday")}) input[data-done]')
    assert page.evaluate("JSON.parse(localStorage.getItem('ptp.done.v1'))")[0].endswith(":long")


def test_dated_checkmarks_survive_plan_length_changes(make_page):
    page = make_page(now=NOW)
    fill(page, "#anchorDate", "2027-03-13")
    race_box = f'tr.week[data-week="22"] > :nth-child({column(page, "Saturday")}) input[data-done]'
    page.check(race_box)
    fill(page, "#weeks", "20")  # race moves to week 20 but keeps its date
    assert page.is_checked(f'tr.week[data-week="20"] > :nth-child({column(page, "Saturday")}) input[data-done]')
    assert page.locator("input[data-done]:checked").count() == 1


# ---------------------------------------------------------------- print

@pytest.mark.parametrize("orientation,size", [("landscape", "792 612"), ("portrait", "612 792")])
def test_print_page_size(page, orientation, size):
    pick(page, "orientation", orientation)
    page.emulate_media(media="print")
    pdf = page.pdf(prefer_css_page_size=True, print_background=True)
    assert f"/MediaBox [0 0 {size}]".encode() in pdf
    assert page.is_hidden("#planForm") and page.is_visible("#calendar")


def test_guide_hidden_in_print_when_unchecked(page):
    page.uncheck("#includeGuide")
    settle(page)
    page.emulate_media(media="print")
    assert page.evaluate("getComputedStyle(document.querySelector('.guide')).display") == "none"


# ---------------------------------------------------------------- accessibility

@pytest.mark.parametrize("mobile,dark", [(False, False), (True, True)])
def test_no_serious_accessibility_violations(make_page, mobile, dark):
    page = make_page(width=375 if mobile else 1280, mobile=mobile, dark=dark, now=NOW)
    page.click("#paceDetails summary")
    fill(page, "#raceTime", "1:50:00")
    fill(page, "#anchorDate", "2027-03-14")
    page.locator("input[data-done]").first.check()
    violations = Axe().run(page).response["violations"]
    serious = [f"{v['id']}: {v['help']} ({len(v['nodes'])})" for v in violations if v["impact"] in ("serious", "critical")]
    assert serious == []

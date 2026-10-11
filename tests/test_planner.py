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
    ("?days=6&miles=70&longrun=20&peakMiles=75&peakLong=20", "mi"),
    ("?goal=base&miles=1&longrun=1&peakMiles=15&peakLong=6&days=4", "mi"),
    ("?units=metric&goal=base&miles=2&longrun=2&peakMiles=24&peakLong=10&days=5", "km"),
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


def test_shared_link_leaves_out_body_weight(page):
    """The weight hint promises it stays in the browser, so links never carry it."""
    fill(page, "#weight", "150")
    fill(page, "#miles", "30")
    url = page.evaluate("shareUrl()")
    assert "miles=30" in url and "weight" not in url


@pytest.mark.parametrize("stored,query,expected", [
    ({"units": "us", "weight": "150"}, "?units=metric&miles=40&weight=99", ["metric", "40", "68"]),  # own 150 lb in kg
    ({"units": "us", "weight": "150"}, "?units=foo&miles=30", ["us", "30", "150"]),  # bad units: no conversion
    ({"weight": "150"}, "?miles=30", ["us", "30", "150"]),  # saved settings without units mean US
    ({"units": "metric", "weight": "70"}, "?miles=30", ["us", "30", "154"]),  # a link without units means US
])
def test_opening_a_link_keeps_own_weight(page, base_url, stored, query, expected):
    page.evaluate("s => localStorage.setItem('ptp.settings.v1', JSON.stringify(s))", stored)
    page.goto(base_url + query)
    page.wait_for_selector("#calBody tr.week")
    units = "metric" if page.is_checked('input[name="units"][value="metric"]') else "us"
    assert [units, *values(page, "miles", "weight")] == expected
    assert "weight" not in page.url  # an older link's weight is taken out of the address bar


def fuel_line(page):
    return next((l for l in page.inner_text("#summary").split("\n") if l.startswith("Fuel & fluids")), "")


def test_fuel_ranges_from_weight_and_sweat_test(page):
    """Issue #21: optional inputs unlock carb/protein ranges and a drink plan, never a calorie target."""
    assert fuel_line(page) == ""
    fill(page, "#weight", "150")  # 68 kg
    line = fuel_line(page)
    assert "Carbs about 340–475 g a day on most training days" in line and "protein about 80–110 g a day" in line
    assert "kcal" not in line and "calorie" not in line.lower()
    page.click("#fuelDetails summary")
    fill(page, "#sweatLoss", "2")     # 2 lb + 16 fl oz in an hour = about 1.38 L/h
    fill(page, "#sweatDrink", "16")
    line = fuel_line(page)
    assert "You sweat about 47 fl oz an hour" in line and "drink about 23–37 fl oz an hour" in line
    pick(page, "units", "metric")
    assert values(page, "weight", "sweatLoss", "sweatDrink") == ["68", "0.9", "473"]
    assert "You sweat about 1350 ml an hour" in fuel_line(page) and "drink about 700–1100 ml an hour" in fuel_line(page)
    assert "sweat" not in page.evaluate("shareUrl()")  # personal data stays out of links


@pytest.mark.parametrize("loss,drink,warns", [
    ("-1", "40", True),
    ("-1", "", True),       # a gain alone is the red flag, even without the drink amount
    ("-0.2", "30", False),  # within scale noise
])
def test_sweat_test_weight_gain_warns_about_overdrinking(page, loss, drink, warns):
    page.click("#fuelDetails summary")
    fill(page, "#sweatLoss", loss)
    fill(page, "#sweatDrink", drink)
    assert ("over-drinking can cause dangerous hyponatremia" in page.inner_text("#warnings")) == warns


def test_sweat_test_out_of_range_is_ignored_with_a_warning(page):
    page.click("#fuelDetails summary")
    fill(page, "#sweatLoss", "12")
    fill(page, "#sweatDrink", "20")
    assert "outside the expected range, so no drink plan is shown" in page.inner_text("#warnings")
    assert "You sweat" not in fuel_line(page)


@pytest.mark.parametrize("units,loss,drink", [("metric", "-2.5", "3000"), ("metric", "4.8", "0"), ("us", "10.6", "101"), ("us", "-5.5", "0")])
def test_sweat_test_edges_survive_unit_switches(page, units, loss, drink):
    pick(page, "units", units)
    page.click("#fuelDetails summary")
    fill(page, "#sweatLoss", loss)
    fill(page, "#sweatDrink", drink)
    pick(page, "units", "us" if units == "metric" else "metric")
    pick(page, "units", units)
    assert "outside the expected range" not in page.inner_text("#warnings")
    assert page.locator("#sweatLoss:invalid, #sweatDrink:invalid").count() == 0


def test_long_run_shows_total_carbs_with_a_known_pace(make_page):
    page = make_page("?easyPace=10:30")
    longs = page.locator("td.long").all_inner_texts()
    assert any("fuel 30–60 g carbs/hr (about 55–110 g after the first half hour)" in t for t in longs)  # ~2:20 run


def test_reset_and_undo(page):
    pick(page, "units", "metric")
    fill(page, "#weight", "70")
    page.click("#resetBtn")
    settle(page)
    assert values(page, "miles", "peakMiles", "peakLong", "weight") == ["25", "38", "18", ""]
    page.click("#undoBtn")
    settle(page)
    assert values(page, "miles", "peakMiles", "peakLong", "weight") == ["40", "61", "29", "70"]


def current_preset(page):
    return page.locator('[data-preset][aria-current="true"]').evaluate_all("bs => bs.map(b => b.dataset.preset)")


def test_preset_applies_training_settings_and_undoes(page):
    assert current_preset(page) == ["emily"]  # the defaults are Emily's starting point
    fill(page, "#weight", "150")
    page.click('[data-preset="sofa"]')
    assert values(page, "miles", "longrun", "weeks", "peakMiles", "peakLong", "weight") == ["1", "1", "20", "15", "6", "150"]
    assert page.is_checked('input[name="goal"][value="base"]') and page.is_checked('input[name="days"][value="4"]')
    assert current_preset(page) == ["sofa"]
    expect(page.locator("#actionStatus")).to_have_text('Applied "Sofa Starter". Fine-tune anything below.')
    fill(page, "#miles", "13")  # any edit means no preset matches any more
    assert current_preset(page) == []
    page.click('[data-preset="emily"]')
    assert values(page, "miles", "longrun", "weeks", "peakMiles", "peakLong") == ["25", "13", "22", "38", "18"]
    page.click("#undoBtn")
    assert values(page, "miles", "weeks") == ["13", "20"]


def test_presets_keep_units_and_convert(page):
    pick(page, "units", "metric")
    page.click('[data-preset="maven"]')
    assert page.is_checked('input[name="units"][value="metric"]')
    assert values(page, "miles", "longrun", "peakMiles", "peakLong") == ["64", "26", "80", "32"]
    assert current_preset(page) == ["maven"]


def test_preset_that_changes_race_goal_clears_date_with_notice(make_page):
    page = make_page("?anchorDate=2027-04-18", now=NOW)
    page.click('[data-preset="comeback"]')
    assert page.input_value("#anchorDate") == ""
    assert "Cleared the race date" in page.inner_text("#warnings")


def test_undo_after_several_presets_restores_own_settings(page):
    fill(page, "#miles", "31")
    page.click('[data-preset="sofa"]')
    page.click('[data-preset="monster"]')
    page.click("#undoBtn")
    settle(page)
    assert values(page, "miles") == ["31"]


def test_preset_keeps_plan_length_that_fits_race_date(make_page):
    page = make_page("?anchorDate=2027-01-02&weeks=13", now=NOW)
    page.click('[data-preset="weekend"]')
    assert values(page, "weeks", "miles") == ["13", "22"]
    expect(page.locator("#actionStatus")).to_contain_text("Kept your 13-week plan to fit your race date.")


def test_emily_restores_her_whole_plan(make_page):
    assert current_preset(make_page("?miles=25.0")) == ["emily"]  # 25.0 is the same as 25
    page = make_page("?taper=2&longDay=6&restDay=0")
    assert current_preset(page) == []
    page.click('[data-preset="emily"]')
    assert page.is_checked('input[name="taper"][value="3"]') and page.is_checked('input[name="longDay"][value="5"]')
    assert current_preset(page) == ["emily"]


@pytest.mark.parametrize("units", ["us", "metric"])
def test_every_preset_builds_a_clean_plan(page, units):
    pick(page, "units", units)
    presets = page.locator("[data-preset]").evaluate_all("bs => bs.map(b => b.dataset.preset)")
    assert len(presets) == 6
    for preset in presets:
        page.click(f'[data-preset="{preset}"]')
        assert page.inner_text("#warnings") == "", preset
        assert current_preset(page) == [preset]


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


def test_no_calorie_target_explanation_is_optional(page):
    """The 'why no calorie target' reasoning is a toggletip: hidden until asked for, and sourced in the guide."""
    tip = page.locator("#tipNoCalories")
    expect(tip).to_be_hidden()
    page.click("#fuelDetails summary")
    page.click('button[popovertarget="tipNoCalories"]')
    expect(tip).to_be_visible()
    expect(tip).to_contain_text("Why no calorie target?")
    expect(tip).to_contain_text("RED-S")
    expect(page.locator(".guide")).to_contain_text("Relative Energy Deficiency in Sport")


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
    ("?miles=150", "was outside the allowed range, so it's set to 99"),
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


def test_clamp_notice_uses_clean_label(page):
    """Weight is the one optional number field; links can't carry it, so use saved settings."""
    page.evaluate("localStorage.setItem('ptp.settings.v1', JSON.stringify({ weight: '9999' }))")
    page.reload()
    page.wait_for_selector("#calBody tr.week")
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
      for (const longDay of [5, 6]) for (const weeks of [10, 16, 24]) for (const start of [[1, 1, 15], [12, 4], [25, 13], [45, 20], [70, 20, 85]]) {
        const G = GOALS[goal];
        const cfg = { units: 'us', startMiles: start[0], startLong: start[1], peakMiles: start[2] ?? G.defaults.us[0], peakLong: G.defaults.us[1],
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


def test_couch_start_builds_with_run_walk_and_walk_days(page):
    """From 1 mi a week: weeks hold the planned volume (no 2 mi floors), spare days are walks, and
    until the build passes LOW_MI runs are run/walk, never longer than the long run, with no tempo.
    Tempo then starts at the gentlest step, and a later cutback doesn't bring run/walk back."""
    low_mi = page.evaluate("LOW_MI")
    weeks, first_tempo = page.evaluate("""() => [computeCalendar({ ...readCfg(), goal: 'base', startMiles: 1, startLong: 1, peakMiles: 20,
        peakLong: 8, weeks: 30, cutEvery: 3, days: 4, strength: 1 }).weeks.map(w => ({ miles: w.wk.miles, long: w.wk.long,
        low: w.wk.low, total: w.total, texts: w.cells.map(c => c.t + ' ' + c.det) })), TEMPO[0].text]""")
    assert weeks[0]["total"] == 1
    assert sum("Walk · 20–30 min" in t for t in weeks[0]["texts"]) == 2
    for w in weeks:
        runs = [float(m) for t in w["texts"] for m in re.findall(r"^(?:Easy|Recovery) · ([\d.]+) mi", t)]
        assert any("Run/walk is fine" in t for t in w["texts"]) == w["low"], w
        if w["low"]:
            assert w["total"] <= w["miles"] + 0.5, w  # no padding up to 2 mi a run day
            assert not any(t.startswith("Tempo") for t in w["texts"]) and all(r <= max(w["long"], 2) for r in runs), w
    tempos = [t for w in weeks for t in w["texts"] if t.startswith("Tempo")]
    assert tempos and first_tempo in tempos[0]
    assert not weeks[23]["low"] and weeks[23]["miles"] < low_mi  # the week-24 cutback stays out of run/walk
    miles = [w["miles"] for w in weeks]
    assert all(m <= max(miles[:i]) * 1.5 + 0.01 for i, m in enumerate(miles) if i), miles  # no doubling from a tiny base


@pytest.mark.parametrize("query,peak", [
    ("?days=6&miles=70&longrun=20&peakMiles=70&peakLong=20", "70 mi/week"),
    ("?units=metric&days=6&miles=110&longrun=32&peakMiles=115&peakLong=32", "115 km/week"),
])
def test_high_mileage_runners_are_supported(make_page, query, peak):
    """Issue #13: "Strava says I'm running 50-70 miles a week." Up to 99 mi (160 km) is accepted as entered."""
    page = make_page(query)
    assert f"Peak ~{peak}" in page.inner_text("#summary")
    assert page.inner_text("#warnings") == ""
    assert page.get_attribute("#miles", "max") == page.get_attribute("#peakMiles", "max") == ("160" if "metric" in query else "99")


@pytest.mark.parametrize("query,advice", [
    ("?days=4&miles=70&longrun=20&peakMiles=70&peakLong=20", "Add a running day, or lower your usual or peak weekly distance."),
    ("?days=6&miles=99&longrun=20&peakMiles=99&peakLong=20", "split long easy days into two runs"),
    ("?units=metric&days=5&miles=130&longrun=32&peakMiles=130&peakLong=32", "Add a running day"),
])
def test_easy_runs_longer_than_long_run_warn(make_page, query, advice):
    warnings = make_page(query).inner_text("#warnings")
    assert "some easy runs come out longer than the long run" in warnings and advice in warnings


def test_long_easy_run_warning_only_at_high_volume(page):
    """Beginners and typical plans never see it: a minimum-length tempo beside a short long run is fine."""
    hits = page.evaluate("""() => {
      const hits = [];
      for (const units of ['us', 'metric']) for (const goal of ['marathon', 'half', 'base']) for (const days of [4, 5, 6])
      for (const weeks of [8, 10, 16, 22]) for (const [m, l] of [[12, 4], [15, 5], [25, 13], [35, 10], [45, 16]]) {
        if (days === 4 && m > 25) continue;  // 35+ on 4 days really does spread too much into easy days
        const G = GOALS[goal];
        const cfg = { units, startMiles: m, startLong: l, peakMiles: G.defaults.us[0], peakLong: G.defaults.us[1], goal, weeks,
          cutEvery: 4, taper: G.defTaper || 0, days, longDay: 5, restDay: 6, strength: 2, raceDist: 21097.5, weekStart: 'sun', anchor: null };
        if (computeCalendar(cfg).longWeekday) hits.push(JSON.stringify({ units, goal, days, weeks, m, l }));
      }
      return hits;
    }""")
    assert hits == [], "\n".join(hits)


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


def test_print_keeps_sections_together(page):
    """Each guide topic (heading plus its table, list or checklist) stays on one page,
    and a phase's readiness gate isn't left at the foot of a page without its first week."""
    page.emulate_media(media="print")
    topics = page.evaluate("""[...document.querySelectorAll('.guide h3')].map(h =>
        h.parentElement.matches('.topic') ? getComputedStyle(h.parentElement).breakInside : 'no topic')""")
    assert topics and set(topics) == {"avoid"}
    assert page.evaluate("getComputedStyle(document.querySelector('#calBody tr.phase-row')).breakAfter") == "avoid"


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

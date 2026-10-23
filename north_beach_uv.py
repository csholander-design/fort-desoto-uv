#!/usr/bin/env python3
"""North Beach UV planner: fetch Open-Meteo hourly UV and publish a static briefing.

Requires Python 3.10+ and uses only the standard library.
"""
from __future__ import annotations

import argparse
import html
import json
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

LATITUDE = 27.643
LONGITUDE = -82.742
TIMEZONE = "America/New_York"
UV_LIMIT = 4.0
EVENING_LIMIT = 3.0
API_BASE = "https://api.open-meteo.com/v1/forecast"


def api_url() -> str:
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "uv_index,uv_index_clear_sky",
        "daily": "sunrise,sunset",
        "timezone": TIMEZONE,
        "forecast_days": 4,
    }
    return f"{API_BASE}?{urlencode(params)}"


def get_forecast() -> dict:
    request = Request(api_url(), headers={"User-Agent": "NorthBeachUVPlanner/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=25) as response:
        return json.load(response)


def time_label(hour: int) -> str:
    return datetime(2000, 1, 1, hour).strftime("%-I %p") if hour else "12 AM"


def dt_label(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p").lstrip("0")


def interval_label(before: dict, after: dict) -> str:
    return f"{time_label(before['hour'])}–{time_label(after['hour'])}"


def parse_days(payload: dict) -> list[dict]:
    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    uv = hourly.get("uv_index", [])
    clear = hourly.get("uv_index_clear_sky", [])
    if not times or len(times) != len(uv) or len(times) != len(clear):
        raise ValueError("Missing or misaligned hourly time/UV arrays")

    by_day: dict[str, list[dict]] = {}
    for t, u, c in zip(times, uv, clear):
        if u is None or c is None:
            continue
        local = datetime.fromisoformat(t)
        by_day.setdefault(local.date().isoformat(), []).append({
            "hour": local.hour, "uv": float(u), "clear": float(c)
        })

    daily = payload.get("daily", {})
    solar = {
        date: {"sunrise": rise, "sunset": sunset}
        for date, rise, sunset in zip(
            daily.get("time", []), daily.get("sunrise", []), daily.get("sunset", [])
        )
    }
    result = []
    for date, hours in sorted(by_day.items()):
        daylight = [r for r in hours if 7 <= r["hour"] <= 20]
        if not daylight:
            continue
        # Failing closed avoids declaring "all day below 4" from incomplete data.
        expected_hours = set(range(7, 20))
        observed_hours = {r["hour"] for r in daylight}
        if not expected_hours.issubset(observed_hours):
            raise ValueError(f"Incomplete daytime hourly data for {date}")
        result.append({"date": date, "hours": hours, **solar.get(date, {})})
    if not result:
        raise ValueError("No usable daylight UV data")
    return result


def find_morning_crossing(hours: list[dict], key: str = "uv") -> tuple[dict, dict] | None:
    """First bracketing interval where UV rises from < 4 to >= 4."""
    daytime = [h for h in hours if 7 <= h["hour"] <= 15]
    for prev, current in zip(daytime, daytime[1:]):
        if prev[key] < UV_LIMIT <= current[key]:
            return prev, current
    return None


def find_evening_safe(hours: list[dict], key: str = "uv") -> dict | None:
    """First <=3 hourly observation after the LAST >=4 (avoid temporary cloudy dips)."""
    afternoon = [h for h in hours if 12 <= h["hour"] <= 20]
    last_over = next((i for i in reversed(range(len(afternoon))) if afternoon[i][key] >= UV_LIMIT), None)
    if last_over is None:
        return None
    return next((h for h in afternoon[last_over + 1:] if h[key] <= EVENING_LIMIT), None)


def summarize_day(day: dict) -> dict:
    hours = day["hours"]
    daytime = [h for h in hours if 7 <= h["hour"] <= 19]
    if not daytime:
        raise ValueError("No daylight data for " + day["date"])
    maximum = max(h["uv"] for h in daytime)
    maximum_clear = max(h["clear"] for h in daytime)
    morning = find_morning_crossing(hours)
    clear_morning = find_morning_crossing(hours, "clear")
    evening = find_evening_safe(hours)
    clear_evening = find_evening_safe(hours, "clear")

    if maximum < UV_LIMIT:
        morning_text = "Expected UV forecast stays below 4 throughout the day"
        if maximum_clear >= UV_LIMIT and clear_morning:
            clear_start = datetime.fromisoformat(f"{day['date']}T{clear_morning[0]['hour']:02d}:00")
            departure = (
                "For extra caution if clouds clear, aim to leave by "
                f"{dt_label(clear_start - timedelta(minutes=30))}–"
                f"{dt_label(clear_start - timedelta(minutes=15))}"
            )
        else:
            departure = "No UV-4 departure deadline predicted"
        evening_text = "Expected UV remains below 4; check clear-sky hourly readings"
    elif morning:
        before, after = morning
        morning_text = f"UV first reaches 4 during {interval_label(before, after)}"
        # To maintain a buffer even if crossing occurs just after the earlier forecast point:
        start_dt = datetime.fromisoformat(f"{day['date']}T{before['hour']:02d}:00")
        departure = (
            f"Aim to leave by {dt_label(start_dt - timedelta(minutes=30))}–"
            f"{dt_label(start_dt - timedelta(minutes=15))}"
        )
        evening_text = (
            f"UV is 3 or below by {time_label(evening['hour'])}"
            if evening else "No verified UV ≤3 evening hour after peak"
        )
    else:
        morning_text = "UV reaches 4, but first morning crossing is not bracketed"
        departure = "Check detailed hourly readings"
        evening_text = (
            f"UV is 3 or below by {time_label(evening['hour'])}"
            if evening else "No verified UV ≤3 evening hour after peak"
        )

    sunset = day.get("sunset")
    sunrise = day.get("sunrise")
    return {
        "date": day["date"],
        "daily_max": round(maximum, 2),
        "daily_clear_sky_max": round(maximum_clear, 2),
        "sunrise": sunrise,
        "sunset": sunset,
        "morning_uv4_interval": interval_label(*morning) if morning else None,
        "morning_uv4_clear_sky_interval": interval_label(*clear_morning) if clear_morning else None,
        "morning_summary": morning_text,
        "suggested_departure": departure,
        "evening_first_uv3_hour": time_label(evening["hour"]) if evening else None,
        "evening_first_clear_sky_uv3_hour": time_label(clear_evening["hour"]) if clear_evening else None,
        "evening_summary": evening_text,
        "hourly": [h for h in hours if 8 <= h["hour"] <= 19],
    }


def render_text(summaries: list[dict], generated: str, source: str, grid: str) -> str:
    lines = [
        "FORT DE SOTO NORTH BEACH — HOURLY UV FORECAST",
        f"Generated (Eastern): {generated}",
        f"Data source: {source}",
        f"Requested coordinates: {LATITUDE}, {LONGITUDE}; forecast grid: {grid}",
        "Forecasts, not real-time measurements. UV <4 is a personal planning preference, not a safety guarantee.",
        "Use these values only if this report was updated recently; otherwise flag it as STALE.",
        "",
    ]
    for s in summaries:
        lines += [
            f"{s['date']}: expected max UV {s['daily_max']}; clear-sky max {s['daily_clear_sky_max']}",
            f" Morning: {s['morning_summary']}.",
            f" Suggested departure: {s['suggested_departure']}.",
            f" Clear-sky UV-4 interval: {s['morning_uv4_clear_sky_interval'] or 'not reached / not bracketed'}.",
            f" Evening: {s['evening_summary']}.",
            f" Clear-sky UV ≤3 by: {s['evening_first_clear_sky_uv3_hour'] or 'not determined'}.",
            f" Sunrise: {s['sunrise'] or 'unavailable'}; Sunset: {s['sunset'] or 'unavailable'}.",
            " Hourly Eastern time — expected UV / clear-sky UV:",
        ]
        lines += [f"  {time_label(h['hour'])}: {h['uv']:.2f} / {h['clear']:.2f}" for h in s["hourly"]]
        lines.append("")
    return "\n".join(lines) + "\n"


def render_html(report: str, generated: str, source: str) -> str:
    # Plain text in a styled <pre> remains easy for both people and automated readers.
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fort De Soto North Beach UV Forecast</title>
<style>body{{font:16px/1.6 system-ui,-apple-system,sans-serif;max-width:800px;margin:32px auto;padding:0 16px;color:#172331;background:#f7fafc}}
main{{background:white;padding:24px;border-radius:12px;box-shadow:0 2px 12px #0001}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.55 ui-monospace,Consolas,monospace}}a{{color:#145c9c}}
small{{color:#596979}}</style></head><body><main><h1>North Beach · UV Planner</h1>
<p><strong>Generated:</strong> {html.escape(generated)} Eastern</p>
<p><small>Source: <a href="{html.escape(source, quote=True)}">Open-Meteo</a>. Forecast values are not observed UV or a guarantee of safety.</small></p>
<pre>{html.escape(report)}</pre></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-json", type=Path, help="Use a saved JSON file instead of fetching fresh data (offline test)")
    parser.add_argument("--output-dir", type=Path, default=Path("site"))
    args = parser.parse_args()
    source = api_url() if args.input_json is None else f"LOCAL DEMO FILE: {args.input_json.name} (NOT LIVE)"
    payload = json.loads(args.input_json.read_text(encoding="utf-8")) if args.input_json else get_forecast()
    if args.input_json is None and payload.get("timezone") != TIMEZONE:
        raise ValueError("Unexpected API timezone; do not publish mismatched data")
    grid = f"{payload.get('latitude', 'unknown')}, {payload.get('longitude', 'unknown')}"
    summaries = [summarize_day(day) for day in parse_days(payload)]
    now = datetime.now(ZoneInfo(TIMEZONE)).strftime("%Y-%m-%d %I:%M %p %Z")
    report = render_text(summaries, now, source, grid)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "uv-brief.txt").write_text(report, encoding="utf-8")
    (args.output_dir / "index.html").write_text(render_html(report, now, source), encoding="utf-8")
    (args.output_dir / "uv-data.json").write_text(json.dumps({
        "generated_et": now, "source": source, "requested_coordinates": [LATITUDE, LONGITUDE],
        "grid_coordinates": [payload.get("latitude"), payload.get("longitude")],
        "days": summaries,
    }, indent=2), encoding="utf-8")
    print(report)
    print(f"Wrote {args.output_dir / 'index.html'}, uv-brief.txt and uv-data.json")


if __name__ == "__main__":
    main()

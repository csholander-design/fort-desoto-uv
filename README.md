# Fort De Soto North Beach UV Planner

A beginner-friendly Python automation for hourly UV forecasts at Fort De Soto **North Beach**, Florida (approx. 27.643° N, 82.742° W).

The script uses Open-Meteo's API to calculate:
- When UV first reaches 4 in the morning;
- A conservative departure buffer for family beach outings;
- When UV returns to 3 or lower in the evening, avoiding misleading temporary cloudy dips;
- Expected and clear-sky UV forecasts for the next four days.

The script produces a web page, a plain-text briefing for ChatGPT, and a JSON data file. It uses Python's standard library only.

## Run locally

Requires Python 3.10 or newer:

```bash
python3 -m unittest discover -s tests -v
python3 north_beach_uv.py
```

Open `site/index.html` in a browser. Check `site/uv-brief.txt` for the full text and `site/uv-data.json` for structured values.

To use a saved Open-Meteo JSON response for an offline experiment:

```bash
python3 north_beach_uv.py --input-json saved_forecast.json
```

Offline reports are explicitly marked as **LOCAL DEMO FILE (NOT LIVE)**.

## Set up automatic publishing

1. Open this repository's **Settings → Pages**.
2. Under **Build and deployment**, select **GitHub Actions** as the source.
3. Open **Actions → Publish North Beach UV forecast → Run workflow** and start a run on the `main` branch.
4. Check that the run succeeds and the published site opens:
   https://csholander-design.github.io/fort-desoto-uv/
5. Review the report's **Generated (Eastern)** timestamp; do not rely on stale data.

The workflow is set to run daily at **5:17 a.m. America/New_York**. GitHub scheduled jobs can be delayed or occasionally skipped.

### Retrieve the report through ChatGPT's connected GitHub app

Each successful workflow now commits updated output to:
- [data/uv-brief.txt](data/uv-brief.txt) — human-readable UV forecast for ChatGPT.
- [data/uv-data.json](data/uv-data.json) — structured data for more advanced tooling.

This is a fallback for when ChatGPT cannot fetch the public GitHub Pages site. The first run after enabling this feature is required before those two files exist.

In your scheduled briefing, tell ChatGPT to use its connected GitHub app to read `data/uv-brief.txt` from `csholander-design/fort-desoto-uv`, confirm its Generated timestamp and date coverage, and incorporate the UV threshold intervals. If the file is stale or inaccessible, disclose that limitation. The regular public webpage continues to work independently.

### Incorporate into your ChatGPT daily briefing

Once the published report can be read from ChatGPT, add this instruction to your Fort De Soto Daily Briefing prompt:

> For North Beach UV data, first read https://csholander-design.github.io/fort-desoto-uv/uv-brief.txt. Verify that the Generated (Eastern) timestamp is current and the forecast dates cover the planned visit. Use the hourly expected and clear-sky UV forecasts, morning UV-4 bracket, conservative departure buffer, and evening return to UV 3 or lower. If the report is unavailable or stale, say so; do not invent threshold times. Independently research weather, water quality, red tide, access, news, and events.

Test whether a scheduled ChatGPT task can access the published page before relying on automated delivery.

## Cautions

- UV values are *forecasts*, not measurements, and the model grid may differ slightly from the requested North Beach coordinates.
- UV below 4 is a personal planning preference, not a guarantee of safety; protect skin and eyes, especially for children.
- The script reports hourly threshold **ranges**, not precise minute-by-minute crossing times.
- A failed GitHub Actions run may leave an older report published. Always check freshness.
- The live API hasn't yet been validated from a GitHub Actions run; the first manual run tests this integration.
- This repository only handles UV. The ChatGPT briefing still researches park access, other weather conditions, tides, bacteria, red tide, events, and news.

References: [Open-Meteo API](https://open-meteo.com/en/docs), [GitHub Pages](https://docs.github.com/en/pages), [GitHub Actions](https://docs.github.com/en/actions).

# Delivery status

Built on November 3, 2026 using public historical January–March 2025 TLC data.

## Published website

[Open NYC Taxi Intelligence](https://nyc-taxi-demand-maaz.gggfherjgh.chatgpt.site)

Private deployment succeeded on November 3, 2026 at 2:40 p.m. America/Toronto.
Source commit: `03615cabfa636fe6c286b74c8b844db8d17ac425`.
Site sharing remains owner-private. The local delivery ZIP includes this publication record; the website's download pack was prepared immediately before publication.

## Executed and verified

- Downloaded all three monthly source files and official lookup/boundaries with checksums.
- Processed all 11,198,026 source records; reconciled 11,137,151 accepted pickups.
- Trained, validated, and evaluated the day-ahead forecasting model.
- Passed six Python checks, including origin-level feature leakage checks.
- Executed the PostgreSQL schema twice, loaded all 567,817 hourly aggregate rows plus all predictions into PGlite PostgreSQL 18.6, ran five analytical queries and reconciled totals/scores.
- Generated a three-page Power BI project; 33 PBIP/PBIR files passed official JSON schema validation. One official schema filename alias was resolved; details are in the verification JSON.
- Opened all four Streamlit pages without runtime exceptions.
- Browser-tested the website at desktop and mobile widths. Checked forecast zone/date selection, snapshot mode, the 168-cell heatmap, and a Queens filter producing 962,726 pickups. Fixed hidden-date-filter behavior in snapshot mode.
- Saved a real dashboard screenshot in `docs/dashboard-preview.png`.

## Remaining external requirements

- Native PostgreSQL: an authenticated connection to a dedicated project database is required for the full trip-fact load. No credentials were changed. Sandbox restrictions prevented initializing another native server.
- Power BI Desktop: Windows is required to refresh the generated model, inspect visual rendering, finish the shape map/drill-through enhancements, and save PBIX if desired.
- Portfolio sharing: the new hosted Site starts owner-private. A private link cannot be used as a publicly accessible résumé demo until its sharing settings are deliberately changed.
- GitHub publishing is part of the current handoff: https://github.com/maazxs9/nyc-taxi-intelligence. The final chat confirms publication after verification.

The project does not contain a live demand feed, calibrated prediction intervals, a Claude API integration, or evidence of actual operational savings. Those are not prerequisites for the historical portfolio case study.

## Verification evidence

See `data/exports/sql_verification.json`, `powerbi_schema_verification.json`, `model_metrics.json`, `quality.json`, and the automated checks in `tests/`.

## November 3 website update

Published a complete dark theme across all four pages, an original SVG route logo, Muaz Shakeel header attribution, and the Muaz Shakeel Study footer. Renamed the geographic filter to Area and displayed Newark Airport (NJ) explicitly. Removed all website download links and the hosted project ZIP. Verified desktop/mobile layouts and the live page. Source commit: `1cc997c32378c4b92840c48c42dfe5d3972063f9`.

# NYC Taxi Demand & Revenue Intelligence

**Question:** How do recorded taxi pickups and fares vary across NYC neighborhoods, and can a simple machine learning model improve day-ahead pickup forecasts over a seasonal baseline?

**Stack:** Python, DuckDB, PostgreSQL SQL, scikit-learn, Power BI project assets, Streamlit, and an interactive JavaScript website.

## Scope and measured results

- Processed 11,198,026 official Yellow Taxi records from January–March 2025.
- Accepted 11,137,151 pickups using explicit data-quality rules; retained demand observations independently of financial eligibility.
- Built a complete 567,817-row zone-hour aggregate and reconciled its totals in embedded PostgreSQL.
- Evaluated 3,360 held-out zone-hour forecasts across 20 training-selected zones and seven complete dates.
- Reduced MAE from 26.27 to 21.89 pickups per zone-hour, a 16.69% improvement over the same-hour previous-week baseline.
- Achieved model WAPE of 13.47% on that short historical test window.

## Three findings

1. Midtown Center led the quarter's accepted pickup volume, with about 511,700 pickups. The dashboard lets readers inspect how rankings change with date and borough filters.
2. Average metered fare among financially eligible trips was about $18.48. Separating fare, total charges and financial denominators prevents misleading revenue comparisons.
3. Historical lags and calendar features improved average forecast error over a seasonal baseline, but evaluation after DST exclusions covered only seven days. Additional seasons and holiday periods are needed before operational use.

## Recommendation

Use the zone/hour views to identify candidate staffing or dispatch review periods. Treat them as observational evidence; they do not establish optimal dispatch decisions without driver-supply, travel-time, unmet-request, and cost information. Extend the backtest before making business commitments.

## Engineering decisions worth explaining in interviews

- Source checksums and source-row keys prevent repeated ingestion from creating duplicates without guessing a trip's natural identifier.
- Full hourly grids make zero observations visible, while coverage caveats avoid claiming unknown vendor completeness.
- Financial validity is separated from pickup validity so disputed or invalid amounts do not automatically change the demand target.
- Forecast features remain unchanged when all counts at and after the forecast origin are altered—a direct leakage check.
- Chronological validation, a frozen test model, and a seasonal baseline make reported performance interpretable.
- Prepared aggregates keep the website lightweight and independent of a live database or AI API key.

## Honest implementation status

The data pipeline, measured forecasts, interactive website, and embedded PostgreSQL aggregate verification have run. Native PostgreSQL loading still requires an authenticated connection. Power BI source is generated and structurally checked; refresh and visual review in Windows Desktop remain. Do not claim those pending steps as completed deployments.

## Résumé bullets

- Built a Python and SQL analytics pipeline processing 11.2M NYC TLC taxi records into validated zone-hour reporting datasets, with source checksums and reconciliation checks.
- Developed day-ahead pickup forecasts for 20 NYC zones, reducing held-out MAE by 16.7% versus a previous-week seasonal baseline across 3,360 predictions over seven test days.
- Created an interactive taxi-demand portfolio website and Power BI project assets covering geographic demand, fare metrics, and transparent forecast evaluation.

Add your deployed website and repository URLs when sharing. Do not describe this observational case study as generating actual company revenue or cost savings.

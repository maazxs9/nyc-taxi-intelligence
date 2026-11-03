# Methodology and limitations

This historical case study uses official NYC TLC Yellow Taxi records for January–March 2025. It measures accepted completed pickups, a proxy for observed demand. It cannot measure unmet requests, vehicle availability, driver earnings, or profit.

## Data and cleaning

The three source files contain 11,198,026 records. The pipeline accepts 11,137,151 pickups and excludes 60,875 records. Each source file has a recorded SHA-256 checksum. Financial metrics use 10,427,978 eligible trips; invalid financial records do not automatically remove a pickup from demand analysis.

The first applicable exclusion determines a row's reason: missing timestamp; pickup outside its source month; unknown pickup zone (valid IDs 1–263); nonpositive or greater-than-six-hour duration; missing/nonfinite/negative/greater-than-200-mile distance; nonexistent local DST hour. Zero-distance trips remain eligible. Missing passenger counts do not trigger exclusion. Unknown dropoff zones remain visible rather than removing valid pickups.

Financial eligibility additionally requires finite fare in $0–$1,000, total charges in $0–$1,500, and payment type 0, 1, or 2. These are explicit analysis choices rather than TLC rules. Refunds, voids, disputes, extreme amounts, and ineligible payment types are excluded from financial totals. The clean fact retains the original recorded fields for investigation. Passenger counts and speed are not used as forecasting features.

Fare revenue is the sum of `fare_amount` on financially eligible trips. Total charges use `total_amount`; cash tips are not recorded. These totals are not driver take-home income or profit. Average fare uses the eligible financial trip count as denominator.

Monthly source coverage is checked for continuity. Every valid zone is expanded to the complete local-hour grid and absent counts become zero. This assumes source-file completeness; vendor reporting completeness is unknown. Genuine zero demand cannot be independently distinguished from unreported trips. Identical-looking trips are preserved because TLC does not supply a reliable trip identifier. Source-file plus source-row keys prevent repeat ingestion from duplicating records.

## Time handling

TLC timestamps are interpreted as naive America/New_York wall-clock times, without an invented UTC offset. The March 9, 2025 02:00 hour does not exist and is omitted, leaving 2,159 hourly bins. The repeated autumn hour cannot be separated without original offsets and would be combined into a single wall-clock bin. Naive durations spanning clock changes can be distorted; this is a source limitation.

For forecasting, clock-key joins implement 24-, 168-, and 336-hour lags. Training, validation, and evaluation exclude DST transition dates and the following 14 days conservatively, including the day where the midnight offset changes. This preserves exact daily horizons and avoids comparing shifted clock windows. The evaluation is correspondingly short.

## Forecast design

The top 20 pickup zones are selected using only data before the February 24 validation boundary. The first 14 days establish feature history. Training feature rows begin January 15. Model settings are selected by validation MAE; no test targets are used to select zones or settings. Candidates have 15 and 31 maximum leaves, 150 boosting iterations, Poisson loss, and a fixed random seed. Random train/test splits and random internal early stopping are disabled.

Each midnight origin predicts 24 individual zone-hour counts. Inputs include zone, cyclical hour/weekday, weekend, counts at 24/168/336 hours before the target, the mean over target-minus-47 through target-minus-24 hours, and the week-over-week historical count difference. Even at the 24th lead, those observations occur strictly before the midnight origin. The tests mutate every observation at and after an origin to confirm its 24 forecast feature vectors do not change.

The nominal test boundary is March 14. DST exclusions leave March 25–31 as the effective test window: seven origins × 24 hours × 20 zones = 3,360 predictions. The evaluation model is fitted to eligible train+validation rows and remains fixed during the test. At successive origins, newly observed prior-day counts may enter features, as in an operational daily forecast. There is no test-period fitting.

The seasonal baseline uses the observed count at the same local hour seven days earlier. MAE is the mean absolute error per zone-hour. WAPE is total absolute error divided by total actual counts; it is undefined when total actual count is zero. These are count forecast metrics, not percentage accuracy claims.

Measured test MAE is 21.8884 versus 26.2726 for the baseline, a 16.6873% reduction. Model WAPE is 13.4669% versus baseline WAPE of 16.1643%. This is a short historical backtest on busy zones, not a guarantee of generalization or a causal business outcome.

An April 1, 2025 snapshot forecast uses a separate model refitted on all eligible data through March 31. It is an archived snapshot forecast, not live data. Actual April 1 counts are not included. Prediction intervals are not supplied because their coverage has not been calibrated.

## Architecture and verification

Official Parquet → Python/DuckDB validation → clean Parquet → PostgreSQL fact/dimension schema and reporting views → Power BI and web exports.

The entire real-data cleaning and forecasting workflow has executed. The SQL schema, rerun behavior, all five analytical queries, all 567,817 hourly aggregate rows, and all held-out forecast scores were verified in PGlite's embedded PostgreSQL engine. This does not establish a successful load into the existing native PostgreSQL server. Native authentication was unavailable, and sandbox restrictions prevented a separate native server from initializing.

The hosted website consumes prepared aggregates. A separate Streamlit companion supports local Python exploration. Neither requires a running database to view the measured results. PostgreSQL source replacement is transactional per file and uses source checksum plus cleaning version for skip decisions.

Power BI report and semantic-model source, DAX measures, a theme, and prepared imports are included. JSON schema checks are distinct from opening, refreshing, and visually validating a report in Power BI Desktop on Windows. Do not describe the Power BI report as Desktop-validated until that step is complete.

## Sources

- [Official TLC trip records, lookup and zone boundaries](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [Yellow taxi field dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf)
- `data/source_manifest.json`: exact URLs, file sizes and checksums.
- `data/exports/quality.json` and `model_metrics.json`: machine-readable evidence.

TLC states that providers supplied the data and does not guarantee its accuracy. Weather, holidays, major events, service supply, policy changes, and future market shifts are not explicitly modeled. A stronger next iteration would expand the time window and assess performance across multiple seasons.

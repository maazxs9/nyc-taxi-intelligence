# Power BI handoff

The generated `NYCTaxi.pbip` project includes a semantic model, three report pages, 25 visuals, five tables, and 16 DAX measures. It has not been opened or refreshed in Power BI Desktop on this Mac. A `.pbix` binary is not included.

1. Use current Power BI Desktop on Windows. Copy the entire project, retaining `data/exports` and `powerbi` together. You may use an existing Windows VM if you have one; no VM was changed for this task.
2. Open `powerbi/NYCTaxi.pbip`. Enable Power BI Project/PBIR support if your Desktop build requests it.
3. In **Transform data → Edit parameters**, set `DataFolder` to the absolute Windows path of `data/exports`, for example `C:/NYCTaxi/data/exports`. If the initial import reports a missing path, edit the parameter and retry refresh. Alternatively change the `DataFolder` expression in `NYCTaxi.SemanticModel/model.bim` before opening.
4. Refresh all tables. Imports are `daily.csv`, `zones.csv`, `dates.csv`, `hourly_profile.csv`, and `predictions.csv`. No PostgreSQL password is needed for this export-backed model.
5. Import `theme.json` using **View → Themes → Browse for themes**. The theme file is supplied independently so the report does not depend on an unregistered theme resource.
6. In Model view, verify the one-to-many, single-direction relationships from Zones to Daily/Pattern/Forecast and from Dates to Daily/Forecast. Mark Dates as the date table using `date` if Desktop has not inferred it.
7. Check the three pages. The Patterns matrix uses weekday 0=Monday through 6=Sunday and hour 0–23. Add background color conditional formatting with pale green `#D8E5E0` through dark green `#1C504B` to make it a heatmap. Its means cover the full quarter; the date slicer does not filter Pattern because no date-grain facts exist in that aggregate.
8. On Executive, verify 11,137,151 pickups, $192,732,716.72 metered fare revenue, $283,594,223.55 total charges, and an average fare around $18.48 when no slicers are active.
9. On Forecast, verify unfiltered model MAE ≈21.9, baseline MAE ≈26.3, MAE improvement ≈16.7%, and model WAPE ≈13.5%. Selecting an out-of-test date range will correctly blank forecast cards. Tests cover March 25–31 only.
10. Finish report-specific formatting: limit the zone bar chart to top 10 by Pickups; sort descending; configure single-select zone slicers where useful; add a tooltip and a zone drill-through page. For a geographic report view, import the official taxi-zone boundaries into a supported shape-map visual and match by zone ID. The included geographic report page initially uses borough and neighborhood bar charts for offline compatibility.
11. Validate interactions and export screenshots. Save as PBIX if desired. Only then describe the report as fully validated in Power BI Desktop.

The web demo and Streamlit companion already provide geographic views; they are distinct from the Power BI report. Generated PBIR query roles and JSON syntax are checked against Microsoft's public schemas, but that does not prove Desktop renders each visual correctly.

## Optional native PostgreSQL connection

After loading the warehouse, replace CSV imports with PostgreSQL queries over `taxi.daily`, `taxi.zones`, `taxi.dates`, `taxi.hourly`/a weekday-hour aggregate, and `taxi.predictions`. Use Import mode initially. Preserve the table/measure names so the existing report bindings continue to work. Never put credentials into the model source.

## Publishing

Power BI publishing depends on your account, licensing, and tenant settings. Publish to web makes report data public. Use only these public source records, or share screenshots/video if public embedding is unavailable.

References: [PBIP report files](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report), [semantic model files](https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset), and [Power BI Desktop](https://learn.microsoft.com/en-us/power-bi/fundamentals/desktop-get-the-desktop).

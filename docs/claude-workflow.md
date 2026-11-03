# Use Claude as a project collaborator

No Claude API key is needed to run this project, and no API call was made during the build. AI-generated explanations are optional; SQL/Python/DAX own the numeric calculations.

Run `python scripts/prepare_brief.py`, then paste `docs/claude-brief-prompt.txt` into Claude. It contains only public-data summary evidence, not millions of trip records. Check every number against its evidence key before using the generated brief on your website.

Useful follow-up prompts:

> Review sql/schema.sql and scripts/load_postgres.py. Explain the fact-table grain, the source-file deduplication strategy, and what happens when a batch is rerun. Identify failure cases without claiming the native database was already loaded.

> Review scripts/forecast.py and tests/test_pipeline.py. Explain why lag24 is available for every hourly prediction in a midnight-origin 24-hour forecast. Look for leakage, splitting errors and weaknesses in DST handling.

> Use docs/portfolio-case-study.md to conduct a data analyst interview. Ask one question at a time about SQL, Python, DAX, model evaluation and limitations. Challenge unsupported claims.

> Walk me through powerbi/BUILD_GUIDE.md using my current Power BI Desktop UI. Help validate each page after refresh. Do not say the PBIP is validated until the report has opened, refreshed, and rendered successfully.

For a future Claude API integration, keep credentials in environment variables, send only calculated aggregate evidence, cache generated briefs, identify AI-generated text, and verify the output. The core website intentionally has no public API-key field or dependency on AI responses.

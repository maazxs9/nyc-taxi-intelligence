"""Create a small, auditable prompt payload for Claude; does not call an API."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
export=ROOT/'data/exports'
evidence={'data_quality':json.loads((export/'quality.json').read_text()),
          'model_evaluation':json.loads((export/'model_metrics.json').read_text())}
prompt='''You are reviewing a historical NYC Yellow Taxi portfolio analysis.
Use only the evidence JSON below. Write a concise executive brief with:
1. Three observations, citing the evidence key for every numeric claim.
2. Two possible follow-up analyses, explicitly labeled as proposals.
3. The main limitations: observed pickups are not unmet demand; metered fare
is not profit; the held-out evaluation covers seven dates and 20 busy zones.
Do not invent weather effects, causal explanations, financial returns,
statistical significance, prediction intervals, or operational savings.
Describe this as January–March 2025 historical data, never live activity.
If a requested claim is unsupported, say the evidence is insufficient.
'''
(ROOT/'docs/claude-brief-prompt.txt').write_text(prompt+'\nEVIDENCE JSON:\n'+json.dumps(evidence,indent=2))
print('Prepared docs/claude-brief-prompt.txt; no data was sent to an AI service.')

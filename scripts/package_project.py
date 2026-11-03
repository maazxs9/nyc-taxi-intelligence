"""Package original source and prepared exports; exclude cached data and secrets."""
from pathlib import Path
import argparse
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--skip-site-copy',action='store_true',help='Update only the local delivery ZIP, preserving the published website source.')
args=parser.parse_args()
OUTPUT=ROOT.parent/'nyc-taxi-intelligence.zip'
ignored={'.git','.venv','node_modules','__pycache__','.pytest_cache','.pbi'}
files=[]
for path in ROOT.rglob('*'):
    if not path.is_file():continue
    rel=path.relative_to(ROOT)
    if any(part in ignored for part in rel.parts):continue
    if rel.parts[:2] in [('data','raw'),('data','clean')]:continue
    if '.openai' in rel.parts:continue
    if path.suffix in ['.zip','.duckdb','.wal'] or path.name.startswith('.env') and path.name!='.env.example':continue
    files.append((path,rel))
with zipfile.ZipFile(OUTPUT,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
    for path,rel in sorted(files):archive.write(path,Path('nyc-taxi-intelligence')/rel)
assets=ROOT/'website/dist/assets'
if not args.skip_site_copy:
    shutil.copy2(ROOT/'data/exports/model_metrics.json',assets/'metrics.json')
    shutil.copy2(ROOT/'data/source_manifest.json',assets/'source_manifest.json')
print(f'{OUTPUT.name}: {OUTPUT.stat().st_size:,} bytes; {len(files)} files. Source/clean trip files and secrets excluded.')

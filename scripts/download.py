"""Download official TLC assets with atomic writes, checksums, and provenance."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import urllib.request
import ssl
import certifi
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://d37ci6vzurychx.cloudfront.net'

def download(url, folder):
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / url.rsplit('/', 1)[1]
    if not target.exists():
        request = urllib.request.Request(url, headers={'User-Agent': 'NYCTaxiPortfolio/1.0'})
        with urllib.request.urlopen(request, timeout=120, context=ssl.create_default_context(cafile=certifi.where())) as response, target.with_suffix(target.suffix + '.part').open('wb') as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        os.replace(target.with_suffix(target.suffix + '.part'), target)
    digest = hashlib.sha256()
    with target.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    print(f'{target.name}: {target.stat().st_size:,} bytes', flush=True)
    return {'file': target.name, 'url': url, 'bytes': target.stat().st_size,
            'sha256': digest.hexdigest()}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--months', nargs='+', default=['2025-01', '2025-02', '2025-03'])
    args = parser.parse_args()
    for month in args.months:
        datetime.strptime(month, '%Y-%m')
    urls = [f'{BASE}/trip-data/yellow_tripdata_{m}.parquet' for m in args.months]
    urls += [f'{BASE}/misc/taxi_zone_lookup.csv', f'{BASE}/misc/taxi_zones.zip']
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(lambda url: download(url, ROOT / 'data/raw'), urls))
    manifest = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'months': args.months,
                'source_page': 'https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page', 'files': records}
    (ROOT / 'data/source_manifest.json').write_text(json.dumps(manifest, indent=2))

if __name__ == '__main__':
    main()

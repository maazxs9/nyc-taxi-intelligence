"""Transactional source-file replacement; reruns skip matching checksum batches."""
import argparse
import json
import os
from pathlib import Path
import tempfile
import duckdb
import psycopg

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'data/exports'
PIPELINE_VERSION = 'clean-v1'

def copy_file(conn, table, path):
    with conn.cursor().copy(f'COPY taxi.{table} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)') as copy:
        with Path(path).open('rb') as source:
            while chunk := source.read(1024*1024):
                copy.write(chunk)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--database-url',default=os.getenv('DATABASE_URL','postgresql://taxi@localhost:55432/taxi'))
    args=parser.parse_args()
    manifest=json.loads((ROOT/'data/source_manifest.json').read_text())
    manifest_files={r['file']:r for r in manifest['files']}
    with psycopg.connect(args.database_url) as conn:
        conn.execute((ROOT/'sql/schema.sql').read_text())
        for table,filename in [('zones','zones.csv'),('dates','dates.csv')]:
            # Small dimensions upsert through a temporary staging table.
            conn.execute(f'CREATE TEMP TABLE staging_{table} (LIKE taxi.{table}) ON COMMIT DROP')
            with conn.cursor().copy(f'COPY staging_{table} FROM STDIN WITH (FORMAT CSV, HEADER TRUE)') as copy:
                copy.write((EXPORT/filename).read_bytes())
            key='zone_id' if table=='zones' else 'date'
            conn.execute(f'INSERT INTO taxi.{table} SELECT * FROM staging_{table} ON CONFLICT ({key}) DO NOTHING')
        conn.commit()
        db=duckdb.connect()
        for month in manifest['months']:
            source=f'yellow_tripdata_{month}.parquet'
            digest=manifest_files[source]['sha256']+':'+PIPELINE_VERSION
            existing=conn.execute('SELECT sha256 FROM taxi.ingestion_batches WHERE source_file=%s',(source,)).fetchone()
            conn.commit()
            if existing and existing[0]==digest:
                print(f'Skipped unchanged {source}',flush=True)
                continue
            clean=ROOT/f'data/clean/{month}.parquet'
            with tempfile.TemporaryDirectory(dir=ROOT/'data') as temp:
                csv=Path(temp)/'trips.csv'
                db.execute(f"COPY (SELECT * FROM read_parquet('{clean}')) TO '{csv}' (HEADER, FORMAT CSV)")
                with conn.transaction():
                    conn.execute('DELETE FROM taxi.trips WHERE source_file=%s',(source,))
                    copy_file(conn,'trips',csv)
                    count=conn.execute('SELECT count(*) FROM taxi.trips WHERE source_file=%s',(source,)).fetchone()[0]
                    conn.execute('INSERT INTO taxi.ingestion_batches(source_file,sha256,accepted_rows) VALUES(%s,%s,%s) ON CONFLICT(source_file) DO UPDATE SET sha256=excluded.sha256,accepted_rows=excluded.accepted_rows,loaded_at=now()',
                                 (source,digest,count))
                print(f'Loaded {count:,} facts from {source}',flush=True)
        # Exports represent a full snapshot; replace matching aggregate snapshot atomically.
        with conn.transaction():
            sources=[f'yellow_tripdata_{m}.parquet' for m in manifest['months']]
            conn.execute('DELETE FROM taxi.trips WHERE source_file <> ALL(%s)',(sources,))
            conn.execute('DELETE FROM taxi.ingestion_batches WHERE source_file <> ALL(%s)',(sources,))
            conn.execute('TRUNCATE taxi.hourly,taxi.predictions')
            copy_file(conn,'hourly',EXPORT/'hourly.csv')
            copy_file(conn,'predictions',EXPORT/'predictions.csv')
        fact=conn.execute('SELECT count(*) FROM taxi.trips').fetchone()[0]
        agg=conn.execute('SELECT sum(pickups) FROM taxi.hourly').fetchone()[0]
        expected=json.loads((EXPORT/'quality.json').read_text())['pickups']
        assert fact==agg==expected,(fact,agg,expected)
        result={'fact_rows':fact,'aggregate_pickups':agg,'expected_pickups':expected,'reconciled':True,
                'batches':conn.execute('SELECT count(*) FROM taxi.ingestion_batches').fetchone()[0]}
        (EXPORT/'warehouse_verification.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result),flush=True)

if __name__=='__main__':
    main()

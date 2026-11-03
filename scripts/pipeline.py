"""Memory-bounded Parquet cleaning, audited exports, and browser demo assets."""
import calendar
from datetime import datetime
import json
from pathlib import Path
import zipfile
import duckdb
import numpy as np
import pandas as pd
import shapefile
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'data/exports'

def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False))

def records(frame):
    return json.loads(frame.to_json(orient='records', date_format='iso'))

def main():
    EXPORT.mkdir(parents=True, exist_ok=True)
    clean_dir = ROOT / 'data/clean'
    clean_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'data/source_manifest.json').read_text())
    months = sorted(manifest['months'])
    expected = pd.period_range(months[0], months[-1], freq='M').astype(str).tolist()
    if months != expected:
        raise ValueError('Choose consecutive months: missing files are not zero demand.')
    calendar_hours = pd.date_range(f'{months[0]}-01',pd.Timestamp(f'{months[-1]}-01')+pd.offsets.MonthBegin(1),freq='h',inclusive='left')
    nonexistent = calendar_hours[calendar_hours.tz_localize('America/New_York',ambiguous=True,nonexistent='NaT').isna()]
    db = duckdb.connect(str(ROOT / 'data/taxi.duckdb'))
    db.execute("SET memory_limit='1GB'")
    db.execute('SET threads=4')
    db.register('nonexistent_hours',pd.DataFrame({'hour':nonexistent}))
    lookup = ROOT / 'data/raw/taxi_zone_lookup.csv'
    zones = pd.read_csv(lookup).rename(columns={'LocationID': 'zone_id', 'Borough': 'borough', 'Zone': 'zone'})
    zones = zones[['zone_id', 'borough', 'zone', 'service_zone']].fillna('Unknown')
    zones.to_csv(EXPORT / 'zones.csv', index=False)
    db.register('zone_frame', zones)
    db.execute('CREATE OR REPLACE TABLE zones AS SELECT * FROM zone_frame')
    reports = []
    outputs = []
    for month in months:
        file = ROOT / f'data/raw/yellow_tripdata_{month}.parquet'
        year, mo = map(int, month.split('-'))
        next_month = f'{year+1}-01-01' if mo == 12 else f'{year}-{mo+1:02d}-01'
        columns = set(db.execute('DESCRIBE SELECT * FROM read_parquet(?)', [str(file)]).df()['column_name'])
        required = {'tpep_pickup_datetime','tpep_dropoff_datetime','PULocationID','DOLocationID',
                    'trip_distance','fare_amount','total_amount','tip_amount','payment_type'}
        if not required.issubset(columns):
            raise ValueError(f'{month}: missing columns {required-columns}')
        # Source row numbers, rather than a guessed natural key, preserve identical legitimate trips.
        # Completed pickups are counted independently of financial validity.
        db.execute(f"""
          CREATE OR REPLACE TABLE staged AS
          SELECT *, CASE
            WHEN pickup_at IS NULL OR dropoff_at IS NULL THEN 'missing_timestamp'
            WHEN pickup_at < TIMESTAMP '{month}-01' OR pickup_at >= TIMESTAMP '{next_month}' THEN 'outside_source_month'
            WHEN zone_id NOT IN (SELECT zone_id FROM zones WHERE zone_id BETWEEN 1 AND 263) OR zone_id IS NULL THEN 'unknown_pickup_zone'
            WHEN dropoff_at <= pickup_at OR dropoff_at > pickup_at + INTERVAL '6 hours' THEN 'invalid_duration'
            WHEN trip_distance IS NULL OR NOT isfinite(trip_distance) OR trip_distance < 0 OR trip_distance > 200 THEN 'invalid_distance'
            WHEN date_trunc('hour',pickup_at) IN (SELECT hour FROM nonexistent_hours) THEN 'nonexistent_dst_hour'
            ELSE 'accepted' END AS quality_status,
            (fare_amount IS NOT NULL AND isfinite(fare_amount) AND fare_amount BETWEEN 0 AND 1000
             AND total_amount IS NOT NULL AND isfinite(total_amount) AND total_amount BETWEEN 0 AND 1500
             AND payment_type IN (0,1,2)) AS financial_valid
          FROM (SELECT row_number() OVER () AS source_row, '{file.name}' AS source_file,
            tpep_pickup_datetime::TIMESTAMP AS pickup_at, tpep_dropoff_datetime::TIMESTAMP AS dropoff_at,
            PULocationID::INTEGER AS zone_id, DOLocationID::INTEGER AS dropoff_zone_id,
            trip_distance::DOUBLE AS trip_distance, fare_amount::DOUBLE AS fare_amount,
            total_amount::DOUBLE AS total_amount, tip_amount::DOUBLE AS tip_amount,
            payment_type::INTEGER AS payment_type
            FROM read_parquet('{file}'))
        """)
        counts = dict(db.execute('SELECT quality_status, count(*) FROM staged GROUP BY 1').fetchall())
        financial_excluded = db.execute("SELECT count(*) FROM staged WHERE quality_status='accepted' AND NOT coalesce(financial_valid,false)").fetchone()[0]
        reports.append({'month': month, 'source_rows': sum(counts.values()), 'outcomes': counts,
                        'financial_excluded_from_accepted': financial_excluded})
        output = clean_dir / f'{month}.parquet'
        output.unlink(missing_ok=True)
        db.execute(f"COPY (SELECT * EXCLUDE(quality_status) FROM staged WHERE quality_status='accepted') TO '{output}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        outputs.append(str(output))
        print(f'{month}: {counts}', flush=True)
    parquet_list = '[' + ','.join("'"+p.replace("'", "''")+"'" for p in outputs) + ']'
    db.execute(f'CREATE OR REPLACE VIEW trips AS SELECT * FROM read_parquet({parquet_list})')
    agg = db.execute("""
      SELECT date_trunc('hour',pickup_at) AS hour, zone_id, count(*)::INTEGER AS pickups,
        count(*) FILTER(WHERE financial_valid)::INTEGER AS financial_trips,
        coalesce(sum(fare_amount) FILTER(WHERE financial_valid),0) AS fare_revenue,
        coalesce(sum(total_amount) FILTER(WHERE financial_valid),0) AS total_charges,
        sum(trip_distance) AS miles,
        sum(date_diff('second',pickup_at,dropoff_at))/60.0 AS duration_minutes
      FROM trips GROUP BY 1,2 ORDER BY 1,2
    """).df()
    start = pd.Timestamp(f'{months[0]}-01')
    end = (pd.Timestamp(f'{months[-1]}-01') + pd.offsets.MonthBegin(1))
    hours = pd.date_range(start, end, freq='h', inclusive='left')
    # TLC timestamps are naive NYC wall times. Omit nonexistent spring-forward hour;
    # fall-back repeated hours are aggregated into one wall-clock bin and flagged.
    localized = hours.tz_localize('America/New_York', ambiguous=True, nonexistent='NaT')
    hours = hours[~localized.isna()]
    index = pd.MultiIndex.from_product([hours, zones.loc[zones.zone_id.between(1,263),'zone_id']], names=['hour','zone_id'])
    agg = agg.set_index(['hour','zone_id']).reindex(index).fillna(0).reset_index()
    for c in ['pickups','financial_trips','zone_id']:
        agg[c] = agg[c].astype(int)
    agg.to_csv(EXPORT / 'hourly.csv', index=False)
    agg.to_parquet(EXPORT / 'hourly.parquet', index=False)
    daily = agg.assign(date=agg.hour.dt.strftime('%Y-%m-%d')).groupby(['date','zone_id'],as_index=False)[['pickups','financial_trips','fare_revenue','total_charges','miles','duration_minutes']].sum()
    daily.to_csv(EXPORT / 'daily.csv', index=False)
    dates = pd.DataFrame({'date':pd.date_range(start,end,freq='D',inclusive='left')})
    dates['date_key'] = dates.date.dt.strftime('%Y%m%d').astype(int)
    dates['year'] = dates.date.dt.year
    dates['month'] = dates.date.dt.month
    dates['weekday'] = dates.date.dt.dayofweek
    dates['weekday_name'] = dates.date.dt.day_name()
    dates['date'] = dates.date.dt.strftime('%Y-%m-%d')
    dates.to_csv(EXPORT / 'dates.csv', index=False)
    profile = agg.assign(weekday=agg.hour.dt.dayofweek,hod=agg.hour.dt.hour).groupby(['zone_id','weekday','hod'],as_index=False).agg(pickups=('pickups','sum'),observed_hours=('pickups','size'))
    profile['mean_pickups'] = profile.pickups/profile.observed_hours
    profile.to_csv(EXPORT / 'hourly_profile.csv', index=False)
    summary = {'start':str(start.date()),'end':str((end-pd.Timedelta(days=1)).date()),
               'pickups':int(agg.pickups.sum()),'financial_trips':int(agg.financial_trips.sum()),
               'fare_revenue':round(float(agg.fare_revenue.sum()),2),
               'total_charges':round(float(agg.total_charges.sum()),2),
               'source_rows':sum(r['source_rows'] for r in reports),'quality':reports,
               'source':'NYC TLC Yellow Taxi','timezone':'America/New_York',
               'observed_hours':len(hours), 'coverage_note':'File coverage verified; vendor completeness cannot be independently verified. Zero-filled hours assume no accepted records means zero observed pickups.',
               'dst_note':'NYC wall-clock timestamps; nonexistent spring hour omitted. Repeated fall hour cannot be separated without offsets and is combined. Forecast evaluation excludes DST transition days and lag windows affected by clock shifts.'}
    save_json(EXPORT / 'quality.json', summary)
    assets = ROOT / 'website/dist/assets'
    save_json(assets / 'data.json', {'summary':summary,'zones':records(zones), 'daily':records(daily.round(2)),
                                    'profile':records(profile.round(2))})
    with zipfile.ZipFile(ROOT / 'data/raw/taxi_zones.zip') as archive:
        # Read only expected shapefile components, without extracting paths.
        names = archive.namelist()
        shp = next(n for n in names if n.endswith('.shp') and not n.startswith('__MACOSX'))
        stem = shp[:-4]
        import io
        reader = shapefile.Reader(shp=io.BytesIO(archive.read(stem+'.shp')),
                                  shx=io.BytesIO(archive.read(stem+'.shx')),
                                  dbf=io.BytesIO(archive.read(stem+'.dbf')))
        transformer = Transformer.from_crs('EPSG:2263','EPSG:4326',always_xy=True)
        features = []
        for sr in reader.iterShapeRecords():
            attrs = sr.record.as_dict()
            geometry = sr.shape.__geo_interface__
            def convert(coords):
                if isinstance(coords[0],(int,float)):
                    x,y=transformer.transform(*coords)
                    return [round(x,5),round(y,5)]
                return [convert(part) for part in coords]
            features.append({'type':'Feature','properties':{'zone_id':int(attrs['LocationID']),'zone':attrs['zone']},
                             'geometry':{'type':geometry['type'],'coordinates':convert(geometry['coordinates'])}})
        save_json(assets / 'zones.geojson', {'type':'FeatureCollection','features':features})
    print(json.dumps({k:v for k,v in summary.items() if k!='quality'},indent=2),flush=True)
    db.close()

if __name__ == '__main__':
    main()

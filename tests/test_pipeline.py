import importlib.util
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('forecast',ROOT/'scripts/forecast.py')
forecast=importlib.util.module_from_spec(spec);spec.loader.exec_module(forecast)

@pytest.fixture(scope='module')
def panel():return pd.read_parquet(ROOT/'data/exports/hourly.parquet')

def test_source_rows_reconcile(panel):
    quality=json.loads((ROOT/'data/exports/quality.json').read_text())
    assert panel.pickups.sum()==quality['pickups']
    assert sum(sum(q['outcomes'].values()) for q in quality['quality'])==quality['source_rows']
    assert panel.financial_trips.sum()==quality['financial_trips']
    assert (panel.financial_trips<=panel.pickups).all()
    assert panel.fare_revenue.sum()==pytest.approx(quality['fare_revenue'],abs=.02)

def test_hour_coverage_and_primary_key(panel):
    assert not panel.duplicated(['hour','zone_id']).any()
    assert panel.hour.nunique()==2159
    assert not ((panel.hour.dt.strftime('%Y-%m-%d %H'))=='2025-03-09 02').any()
    assert (panel.pickups>=0).all()

def test_no_forecast_horizon_leakage(panel):
    block=panel[panel.zone_id==161][['hour','zone_id','pickups']].copy()
    original=forecast.feature_frame(block)
    origin=pd.Timestamp('2025-03-26')
    mutated=block.copy()
    mutated.loc[mutated.hour>=origin,'pickups']=9999999
    changed=forecast.feature_frame(mutated)
    target=original.hour.between(origin,origin+pd.Timedelta(hours=23))
    np.testing.assert_allclose(original.loc[target,forecast.FEATURES],changed.loc[target,forecast.FEATURES],equal_nan=True)

def test_metrics_and_complete_origins():
    predictions=pd.read_csv(ROOT/'data/exports/predictions.csv',parse_dates=['hour','origin'])
    metrics=json.loads((ROOT/'data/exports/model_metrics.json').read_text())
    actual=forecast.score(predictions.actual,predictions.prediction)
    assert actual['mae']==pytest.approx(metrics['model']['mae'])
    assert actual['wape']==pytest.approx(metrics['model']['wape'])
    assert (predictions.groupby(['origin','zone_id']).size()==24).all()
    assert (predictions.hour>=predictions.origin).all()
    assert (predictions.hour<predictions.origin+pd.Timedelta(hours=24)).all()
    assert predictions.origin.nunique()==7
    assert predictions.zone_id.nunique()==20
    assert forecast.score([0,0],[1,2])['wape'] is None

def test_training_only_zone_selection(panel):
    metrics=json.loads((ROOT/'data/exports/model_metrics.json').read_text())
    cutoff=pd.Timestamp(metrics['validation_start'])
    expected=panel[panel.hour<cutoff].groupby('zone_id').pickups.sum().nlargest(20).index.tolist()
    assert expected==metrics['zones']

def test_download_checksums():
    import hashlib
    manifest=json.loads((ROOT/'data/source_manifest.json').read_text())
    for source in manifest['files']:
        path=ROOT/'data/raw'/source['file']
        if not path.exists():continue
        assert hashlib.file_digest(path.open('rb'),'sha256').hexdigest()==source['sha256']

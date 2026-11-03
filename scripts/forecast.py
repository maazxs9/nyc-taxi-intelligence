"""Leakage-aware, day-ahead forecasts evaluated at daily rolling origins."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from threadpoolctl import threadpool_limits
import joblib

ROOT = Path(__file__).resolve().parents[1]
EXPORT = ROOT / 'data/exports'
FEATURES = ['zone_id','hour_sin','hour_cos','week_sin','week_cos','weekend',
            'lag24','lag168','lag336','mean24_to47','trend_week']

def feature_frame(panel):
    """At any midnight origin, all target lags refer strictly before origin."""
    frame = panel.sort_values(['zone_id','hour']).copy()
    group = frame.groupby('zone_id',sort=False)
    # Exact clock-key joins prevent a DST gap from turning row lags into wrong hours.
    for lag in [24,168,336]:
        lookup = frame[['zone_id','hour','pickups']].copy()
        lookup['hour'] += pd.Timedelta(hours=lag)
        lookup = lookup.rename(columns={'pickups':f'lag{lag}'})
        frame = frame.merge(lookup,on=['zone_id','hour'],how='left',validate='1:1')
    # Compute rolling history using a full wall-clock grid, preserving DST NaNs.
    rolling = []
    for zone, block in panel.groupby('zone_id'):
        series = block.set_index('hour').pickups.asfreq('h')
        rolling.append(series.shift(24).rolling(24,min_periods=24).mean().rename('mean24_to47').reset_index().assign(zone_id=zone))
    frame = frame.merge(pd.concat(rolling),on=['zone_id','hour'],how='left',validate='1:1')
    frame['hour_sin'] = np.sin(2*np.pi*frame.hour.dt.hour/24)
    frame['hour_cos'] = np.cos(2*np.pi*frame.hour.dt.hour/24)
    frame['week_sin'] = np.sin(2*np.pi*frame.hour.dt.dayofweek/7)
    frame['week_cos'] = np.cos(2*np.pi*frame.hour.dt.dayofweek/7)
    frame['weekend'] = (frame.hour.dt.dayofweek>=5).astype(int)
    frame['trend_week'] = frame.lag168-frame.lag336
    frame['origin'] = frame.hour.dt.normalize()
    # Shifted wall-clock weeks around DST differ from elapsed hours. Explicitly omit
    # transition dates and the 14 days after them from evaluation/training.
    days = pd.date_range(frame.hour.min().normalize()-pd.Timedelta(days=15),frame.hour.max().normalize(),freq='D')
    offsets = [d.tz_localize('America/New_York').utcoffset() for d in days]
    transitions = [days[i] for i in range(1,len(days)) if offsets[i]!=offsets[i-1]]
    frame['dst_affected'] = False
    for day in transitions:
        affected_start = day-pd.Timedelta(days=1)
        frame.loc[frame.origin.between(affected_start,day+pd.Timedelta(days=14)),'dst_affected'] = True
    return frame

def score(actual, predicted):
    actual = np.asarray(actual,dtype=float)
    error = np.abs(actual-np.asarray(predicted,dtype=float))
    denom = float(actual.sum())
    return {'mae':float(error.mean()),'wape':float(error.sum()/denom) if denom else None,
            'observations':len(actual),'actual_pickups':int(denom)}

def model(leaves):
    return HistGradientBoostingRegressor(loss='poisson',max_iter=150,max_leaf_nodes=leaves,
                learning_rate=0.08,l2_regularization=2,early_stopping=False,random_state=42,
                categorical_features=[True]+[False]*(len(FEATURES)-1))

def evaluate(m, frame):
    result = frame[['hour','zone_id','origin','pickups','lag168']].copy()
    result['prediction'] = np.maximum(m.predict(frame[FEATURES]),0)
    result = result.rename(columns={'pickups':'actual','lag168':'baseline'})
    result['horizon'] = result.hour.dt.hour+1
    return result

def main():
    panel = pd.read_parquet(EXPORT / 'hourly.parquet')
    start, end = panel.hour.min(), panel.hour.max()+pd.Timedelta(hours=1)
    days = (end.normalize()-start.normalize()).days
    val_start = start.normalize()+pd.Timedelta(days=int(days*.6))
    test_start = start.normalize()+pd.Timedelta(days=int(days*.8))
    top = panel[panel.hour<val_start].groupby('zone_id').pickups.sum().nlargest(20).index.tolist()
    subset = panel[panel.zone_id.isin(top)][['hour','zone_id','pickups']]
    features = feature_frame(subset)
    usable = features.dropna(subset=FEATURES+['pickups'])
    usable = usable[~usable.dst_affected].copy()
    # Evaluate complete 24-hour forecast blocks only, never partial days.
    sizes = usable.groupby(['zone_id','origin']).hour.transform('size')
    usable = usable[sizes==24]
    train = usable[usable.hour<val_start]
    validation = usable[(usable.hour>=val_start)&(usable.hour<test_start)]
    test = usable[usable.hour>=test_start]
    if min(len(train),len(validation),len(test))==0:
        raise ValueError('Insufficient complete days for chronological splits; expand the date range.')
    candidates = []
    with threadpool_limits(limits=4):
        for leaves in [15,31]:
            m = model(leaves).fit(train[FEATURES],train.pickups)
            candidates.append({'leaves':leaves,**score(validation.pickups,m.predict(validation[FEATURES]))})
        best = min(candidates,key=lambda x:x['mae'])['leaves']
        frozen = model(best).fit(pd.concat([train,validation])[FEATURES],pd.concat([train,validation]).pickups)
        predictions = evaluate(frozen,test)
        # Test uses a fixed model; observed prior days may enter features as they
        # would at each new daily origin. No fitting or tuning uses test outcomes.
        summary = {'train_start':str(train.hour.min()),'validation_start':str(val_start),'test_start':str(test_start),
                   'effective_test_start':str(test.hour.min()),'test_end':str(test.hour.max()),'zones':top,'validation_candidates':candidates,
                   'selected_max_leaf_nodes':best,'model':score(predictions.actual,predictions.prediction),
                   'baseline':score(predictions.actual,predictions.baseline),
                   'test_origins':int(predictions.origin.nunique()),'features':FEATURES,
                   'horizon':'24 hours from midnight NYC local time',
                   'baseline_definition':'Observed pickups at the same NYC wall-clock hour seven days earlier',
                   'dst_excluded_rows':int(features.dst_affected.sum())}
        summary['mae_improvement_pct'] = 100*(1-summary['model']['mae']/summary['baseline']['mae']) if summary['baseline']['mae'] else None
        by_zone = []
        for zone,block in predictions.groupby('zone_id'):
            by_zone.append({'zone_id':int(zone),'model':score(block.actual,block.prediction),
                            'baseline':score(block.actual,block.baseline)})
        summary['by_zone'] = by_zone
        predictions.to_csv(EXPORT / 'predictions.csv',index=False)
        # Refit for one archived-snapshot day-ahead forecast, not for test scores.
        production = model(best).fit(usable[FEATURES],usable.pickups)
        future = pd.DataFrame([(h,z,np.nan) for z in top for h in pd.date_range(end,periods=24,freq='h')],
                              columns=['hour','zone_id','pickups'])
        future_features = feature_frame(pd.concat([subset,future],ignore_index=True))
        future_features = future_features[future_features.hour>=end]
        future_features['prediction'] = np.maximum(production.predict(future_features[FEATURES]),0)
        future_features[['hour','zone_id','prediction']].to_csv(EXPORT / 'snapshot_forecast.csv',index=False)
    joblib.dump({'model':production,'features':FEATURES,'trained_through':str(end-pd.Timedelta(hours=1))},EXPORT / 'forecast_model.joblib')
    (EXPORT / 'model_metrics.json').write_text(json.dumps(summary,indent=2))
    assets = ROOT / 'website/dist/assets'
    assets.mkdir(parents=True,exist_ok=True)
    payload = {'metrics':summary,'predictions':json.loads(predictions.round(2).to_json(orient='records',date_format='iso')),
               'snapshot':json.loads(future_features[['hour','zone_id','prediction']].round(2).to_json(orient='records',date_format='iso'))}
    (assets / 'forecast.json').write_text(json.dumps(payload,separators=(',',':'),allow_nan=False))
    print(json.dumps({k:v for k,v in summary.items() if k not in ['by_zone','features']},indent=2),flush=True)

if __name__ == '__main__':
    main()

"""Local Streamlit companion; the hosted static demo lives in website/dist."""
from pathlib import Path
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT=Path(__file__).resolve().parent
EXPORT=ROOT/'data/exports'
st.set_page_config(page_title='NYC Taxi Intelligence',page_icon='🚕',layout='wide')
st.markdown('''<style>.stApp{background:#f5f6f5}h1,h2,h3{color:#152e3a}div[data-testid="stMetric"]{background:white;padding:20px;border:1px solid #dce2e1;border-radius:9px}</style>''',unsafe_allow_html=True)

@st.cache_data
def load():
    return (pd.read_csv(EXPORT/'daily.csv',parse_dates=['date']),pd.read_csv(EXPORT/'zones.csv'),
            pd.read_csv(EXPORT/'hourly_profile.csv'),pd.read_csv(EXPORT/'predictions.csv',parse_dates=['hour','origin']),
            json.loads((EXPORT/'model_metrics.json').read_text()),json.loads((EXPORT/'quality.json').read_text()))

daily,zones,profile,predictions,metrics,quality=load()
zone_names=zones.set_index('zone_id').zone.to_dict()
st.sidebar.title('↗ NYC TAXI')
page=st.sidebar.radio('Explore',['Overview','Demand patterns','Forecast lab','Methodology'])
st.sidebar.caption('Official TLC Yellow Taxi data · January–March 2025 · NYC local time')
st.title('Demand in motion.')
st.caption('Python + PostgreSQL + Power BI · A reproducible historical analytics project')

if page=='Overview':
    borough=st.sidebar.selectbox('Borough',['All boroughs']+sorted(zones[zones.zone_id<=263].borough.unique()))
    dates=st.sidebar.date_input('Date range',(daily.date.min().date(),daily.date.max().date()),min_value=daily.date.min().date(),max_value=daily.date.max().date())
    if len(dates)!=2:st.info('Select both dates.');st.stop()
    frame=daily[daily.date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))].merge(zones,on='zone_id')
    if borough!='All boroughs':frame=frame[frame.borough==borough]
    a,b,c,d=st.columns(4)
    a.metric('Observed pickups',f'{frame.pickups.sum():,}')
    b.metric('Metered fare revenue',f'${frame.fare_revenue.sum():,.0f}')
    c.metric('Total recorded charges',f'${frame.total_charges.sum():,.0f}')
    financial=frame.financial_trips.sum()
    d.metric('Average eligible fare',f'${frame.fare_revenue.sum()/financial:,.2f}' if financial else '—')
    totals=frame.groupby(['zone_id','zone'],as_index=False).pickups.sum()
    left,right=st.columns([1.4,1])
    geo=json.loads((ROOT/'website/dist/assets/zones.geojson').read_text())
    fig=px.choropleth(totals,geojson=geo,locations='zone_id',featureidkey='properties.zone_id',color='pickups',hover_name='zone',color_continuous_scale=['#d8e5e0','#1c504b'])
    fig.update_geos(fitbounds='locations',visible=False)
    fig.update_layout(margin=dict(l=0,r=0,t=15,b=0),height=450)
    left.plotly_chart(fig,width='stretch')
    right.subheader('Top pickup zones')
    right.dataframe(totals.sort_values('pickups',ascending=False).head(12)[['zone','pickups']],hide_index=True)
    metric=st.selectbox('Daily metric',['pickups','fare_revenue','total_charges'])
    trend=frame.groupby('date',as_index=False)[metric].sum()
    st.plotly_chart(px.line(trend,x='date',y=metric,color_discrete_sequence=['#284d49']),width='stretch')
    st.caption('Fare revenue is metered fare, not profit. Financial metrics exclude invalid charge records; pickups do not.')
elif page=='Demand patterns':
    zone=st.selectbox('Neighborhood',sorted(profile.zone_id.unique()),format_func=lambda z:zone_names[z],index=list(sorted(profile.zone_id.unique())).index(161))
    block=profile[profile.zone_id==zone]
    pivot=block.pivot(index='weekday',columns='hod',values='mean_pickups').reindex(range(7))
    pivot.index=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']
    st.subheader('Average hourly pickups')
    st.plotly_chart(px.imshow(pivot,labels={'x':'NYC local hour','y':'Weekday','color':'Mean pickups'},color_continuous_scale=['#d8e5e0','#1c504b']),width='stretch')
    st.caption('Full quarter averages. The nonexistent March 9, 02:00 hour is omitted.')
elif page=='Forecast lab':
    a,b,c,d=st.columns(4)
    a.metric('Held-out model MAE',f'{metrics["model"]["mae"]:.1f}')
    b.metric('Seasonal baseline MAE',f'{metrics["baseline"]["mae"]:.1f}')
    c.metric('MAE reduction',f'{metrics["mae_improvement_pct"]:.1f}%')
    d.metric('Model WAPE',f'{metrics["model"]["wape"]*100:.1f}%')
    mode=st.radio('Forecast view',['Held-out test','April 1 snapshot forecast'],horizontal=True)
    zone=st.selectbox('Neighborhood',sorted(metrics['zones']),format_func=lambda z:zone_names[z])
    fig=go.Figure()
    if mode=='Held-out test':
        origin=st.selectbox('Midnight forecast origin',sorted(predictions.origin.unique()))
        block=predictions[(predictions.zone_id==zone)&(predictions.origin==origin)]
        for col,label,color in [('actual','Observed','#152e3a'),('prediction','Model','#b79722'),('baseline','Seasonal baseline','#91a5a5')]:
            fig.add_trace(go.Scatter(x=block.hour,y=block[col],name=label,line={'color':color}))
        st.caption('The fixed model was evaluated at seven midnight origins on March 25–31. Headline scores cover all 20 zones and seven dates. Settings were selected on earlier validation data.')
    else:
        block=pd.read_csv(EXPORT/'snapshot_forecast.csv',parse_dates=['hour'])
        block=block[block.zone_id==zone]
        fig.add_trace(go.Scatter(x=block.hour,y=block.prediction,name='Snapshot forecast',line={'color':'#b79722'}))
        st.caption('Archived forecast for April 1, 2025 from data through March 31. This is not a current forecast; actual April 1 counts are not included.')
    fig.update_layout(yaxis_title='Observed pickups / predictions',xaxis_title='NYC local time')
    st.plotly_chart(fig,width='stretch')
else:
    st.markdown((ROOT/'docs/methodology.md').read_text())

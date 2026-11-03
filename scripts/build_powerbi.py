"""Generate an inspectable PBIP report + semantic model and supporting assets.

JSON structures follow Microsoft's published PBIR schemas. Desktop refresh and
visual validation are still required; generation is not a claim of PBIX validation.
"""
import json
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'powerbi'
SCHEMA='https://developer.microsoft.com/json-schemas/fabric/item/report/definition/'

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2))

def literal(value):
    if isinstance(value,bool): value='true' if value else 'false'
    elif isinstance(value,str):value="'"+value.replace("'","''")+"'"
    else:value=str(value)+'D'
    return {'expr':{'Literal':{'Value':value}}}

def projection(table,field,measure=False):
    kind='Measure' if measure else 'Column'
    return {'field':{kind:{'Expression':{'SourceRef':{'Entity':table}},'Property':field}},
            'queryRef':f'{table}.{field}','nativeQueryRef':field}

MEASURES={
 'Pickups':('SUM(Daily[pickups])','#,0'),
 'Fare Revenue':('SUM(Daily[fare_revenue])','$#,0.00'),
 'Total Charges':('SUM(Daily[total_charges])','$#,0.00'),
 'Eligible Financial Trips':('SUM(Daily[financial_trips])','#,0'),
 'Average Fare':('DIVIDE([Fare Revenue], [Eligible Financial Trips])','$0.00'),
 'Pickups Previous Week':('CALCULATE([Pickups], DATEADD(Dates[date], -7, DAY))','#,0'),
 'Pickups WoW Percent':('DIVIDE([Pickups] - [Pickups Previous Week], [Pickups Previous Week])','0.0%'),
 'Pickups 7 Day Mean':('AVERAGEX(DATESINPERIOD(Dates[date], MAX(Dates[date]), -7, DAY), [Pickups])','#,0.0'),
 'Pattern Mean Per Zone Hour':('DIVIDE(SUM(Pattern[pickups]), SUM(Pattern[observed_hours]))','0.0'),
 'Observed Pickups':('SUM(Forecast[actual])','#,0'),
 'Predicted Pickups':('SUM(Forecast[prediction])','#,0.0'),
 'Baseline Pickups':('SUM(Forecast[baseline])','#,0.0'),
 'Model MAE':('AVERAGEX(Forecast, ABS(Forecast[actual] - Forecast[prediction]))','0.0'),
 'Baseline MAE':('AVERAGEX(Forecast, ABS(Forecast[actual] - Forecast[baseline]))','0.0'),
 'Model WAPE':('DIVIDE(SUMX(Forecast, ABS(Forecast[actual] - Forecast[prediction])), SUM(Forecast[actual]))','0.0%'),
 'MAE Improvement':('DIVIDE([Baseline MAE] - [Model MAE], [Baseline MAE])','0.0%'),
}

def table_model(name,filename,types):
    columns=[{'name':col,'dataType':kind,'sourceColumn':col,'summarizeBy':'none' if kind!='double' else 'sum'} for col,kind in types.items()]
    mtypes={'int64':'Int64.Type','double':'type number','string':'type text','dateTime':'type datetime'}
    transforms=', '.join('{"'+c+'", '+mtypes[t]+'}' for c,t in types.items())
    expression=['let',f'    Source = Csv.Document(File.Contents(DataFolder & "/{filename}"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
                '    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
                f'    Typed = Table.TransformColumnTypes(Headers, {{{transforms}}}, "en-US")','in','    Typed']
    result={'name':name,'columns':columns,'partitions':[{'name':name,'mode':'import','source':{'type':'m','expression':expression}}]}
    if name=='Dates':
        result['columns'][0]['isKey']=True
        result['columns'][0]['formatString']='yyyy-MM-dd'
    if name=='Daily':
        result['measures']=[{'name':n,'expression':e,'formatString':f,'displayFolder':'KPIs' if 'MAE' not in n and 'WAPE' not in n else 'Forecast evaluation'} for n,(e,f) in MEASURES.items()]
    if name=='Forecast':
        result['columns'].append({'name':'date','dataType':'dateTime','type':'calculated','expression':'DATE(YEAR([hour]), MONTH([hour]), DAY([hour]))','formatString':'yyyy-MM-dd'})
    return result

def main():
    tables=[
      table_model('Daily','daily.csv',{'date':'dateTime','zone_id':'int64','pickups':'int64','financial_trips':'int64','fare_revenue':'double','total_charges':'double','miles':'double','duration_minutes':'double'}),
      table_model('Zones','zones.csv',{'zone_id':'int64','borough':'string','zone':'string','service_zone':'string'}),
      table_model('Dates','dates.csv',{'date':'dateTime','date_key':'int64','year':'int64','month':'int64','weekday':'int64','weekday_name':'string'}),
      table_model('Pattern','hourly_profile.csv',{'zone_id':'int64','weekday':'int64','hod':'int64','pickups':'int64','observed_hours':'int64','mean_pickups':'double'}),
      table_model('Forecast','predictions.csv',{'hour':'dateTime','zone_id':'int64','origin':'dateTime','actual':'int64','baseline':'double','prediction':'double','horizon':'int64'})]
    relationships=[{'name':f'{table}_Zones','fromTable':table,'fromColumn':'zone_id','toTable':'Zones','toColumn':'zone_id','crossFilteringBehavior':'oneDirection'} for table in ['Daily','Pattern','Forecast']]
    relationships += [{'name':f'{table}_Dates','fromTable':table,'fromColumn':'date','toTable':'Dates','toColumn':'date','crossFilteringBehavior':'oneDirection'} for table in ['Daily','Forecast']]
    model={'name':'NYCTaxi','compatibilityLevel':1600,'model':{'culture':'en-US','defaultPowerBIDataSourceVersion':'powerBI_V3',
            'sourceQueryCulture':'en-US','tables':tables,'relationships':relationships,
            'expressions':[{'name':'DataFolder','kind':'m','expression':'"C:/NYCTaxi/data/exports" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]'}],
            'annotations':[{'name':'PBI_QueryOrder','value':json.dumps(['DataFolder','Zones','Dates','Daily','Pattern','Forecast'])}]}}
    write(OUT/'NYCTaxi.SemanticModel/model.bim',model)
    write(OUT/'NYCTaxi.SemanticModel/definition.pbism',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json','version':'4.0','settings':{}})
    write(OUT/'NYCTaxi.pbip',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json','version':'1.0','artifacts':[{'report':{'path':'NYCTaxi.Report'}}],'settings':{'enableAutoRecovery':True}})
    report=OUT/'NYCTaxi.Report'
    write(report/'definition.pbir',{'$schema':'https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json','version':'4.0','datasetReference':{'byPath':{'path':'../NYCTaxi.SemanticModel'}}})
    write(report/'definition/report.json',{'$schema':SCHEMA+'report/3.0.0/schema.json','themeCollection':{}})
    write(report/'definition/pages/pages.json',{'$schema':SCHEMA+'pagesMetadata/1.0.0/schema.json','pageOrder':['Executive','Patterns','Forecast'],'activePageName':'Executive'})
    counter=0
    def visual(page,kind,roles,x,y,w,h,title):
        nonlocal counter
        counter+=1
        name=f'visual{counter:03d}'
        query={'queryState':{role:{'projections':fields} for role,fields in roles.items()}}
        config={'visualType':kind,'query':query,'visualContainerObjects':{
          'title':[{'properties':{'show':literal(True),'text':literal(title),'fontColor':{'solid':{'color':literal('#14252D')}},'fontSize':literal(12)}}],
          'background':[{'properties':{'show':literal(True),'color':{'solid':{'color':literal('#FFFFFF')}},'transparency':literal(0)}}]}}
        write(report/f'definition/pages/{page}/visuals/{name}/visual.json',{'$schema':SCHEMA+'visualContainer/2.1.0/schema.json','name':name,'position':{'x':x,'y':y,'z':counter,'width':w,'height':h,'tabOrder':counter},'visual':config})
    def measure(name):return projection('Daily',name,True)
    for page,title in [('Executive','Executive overview'),('Patterns','Geographic & hourly patterns'),('Forecast','Forecast evaluation')]:
        write(report/f'definition/pages/{page}/page.json',{'$schema':SCHEMA+'page/2.0.0/schema.json','name':page,'displayName':title,'displayOption':'FitToPage','height':900,'width':1440})
        visual(page,'slicer',{'Values':[projection('Zones','zone')]},32,20,430,100,'Neighborhood')
        visual(page,'slicer',{'Values':[projection('Dates','date')]},490,20,430,100,'Date range · Jan–Mar 2025')
        visual(page,'slicer',{'Values':[projection('Zones','borough')]},948,20,460,100,'Borough')
    for i,(name,title) in enumerate([('Pickups','Observed pickups'),('Fare Revenue','Metered fare revenue'),('Total Charges','Total recorded charges'),('Average Fare','Average eligible fare')]):
        visual('Executive','card',{'Values':[measure(name)]},32+348*i,145,324,140,title)
    visual('Executive','lineChart',{'Category':[projection('Dates','date')],'Y':[measure('Pickups')]},32,312,870,330,'Daily observed pickups')
    visual('Executive','barChart',{'Category':[projection('Zones','zone')],'Y':[measure('Pickups')]},930,312,478,550,'Pickups by neighborhood')
    visual('Executive','lineChart',{'Category':[projection('Dates','date')],'Y':[measure('Fare Revenue'),measure('Total Charges')]},32,665,870,197,'Metered fares and total charges · not profit')
    visual('Patterns','barChart',{'Category':[projection('Zones','borough')],'Y':[measure('Pickups')]},32,145,600,310,'Observed pickups by borough')
    visual('Patterns','barChart',{'Category':[projection('Zones','zone')],'Y':[measure('Fare Revenue')]},660,145,748,310,'Metered fare revenue by zone')
    visual('Patterns','pivotTable',{'Rows':[projection('Pattern','weekday')],'Columns':[projection('Pattern','hod')],'Values':[measure('Pattern Mean Per Zone Hour')]},32,485,1376,375,'Weekday × hour · mean pickups per zone-hour · full quarter')
    for i,(name,title) in enumerate([('Model MAE','Model MAE'),('Baseline MAE','Baseline MAE'),('MAE Improvement','Reduction in MAE'),('Model WAPE','Model WAPE')]):
        visual('Forecast','card',{'Values':[measure(name)]},32+348*i,145,324,140,title)
    visual('Forecast','lineChart',{'Category':[projection('Forecast','hour')],'Y':[measure('Observed Pickups'),measure('Predicted Pickups'),measure('Baseline Pickups')]},32,312,1376,330,'Held-out predictions · March 25–31 · 24-hour daily origins')
    visual('Forecast','tableEx',{'Values':[projection('Zones','zone'),measure('Model MAE'),measure('Baseline MAE'),measure('Model WAPE')]},32,665,1376,197,'Forecast error by neighborhood')
    theme={'name':'NYC Taxi Intelligence','dataColors':['#284D49','#EFC436','#91A5A5','#567B88','#A48B47'],'background':'#F5F6F5','foreground':'#14252D','tableAccent':'#EFC436',
           'textClasses':{'title':{'fontFace':'Segoe UI Semibold','fontSize':13},'label':{'fontFace':'Segoe UI','fontSize':10},'callout':{'fontFace':'Segoe UI Semibold','fontSize':32}}}
    write(OUT/'theme.json',theme)
    (OUT/'measures.dax').write_text('\n\n'.join(f'{name} = {expr}' for name,(expr,_) in MEASURES.items()))
    print(f'Generated {counter} PBIR visuals, 5 semantic-model tables, {len(MEASURES)} DAX measures.')

if __name__=='__main__':main()

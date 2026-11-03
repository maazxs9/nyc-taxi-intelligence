"""Validate generated PBIR JSON using official Microsoft schema resources."""
import json
from pathlib import Path
import warnings
import requests
import jsonschema

ROOT=Path(__file__).resolve().parents[1]

def main():
    cache={}
    aliases=[]
    def fetch(url):
        if url not in cache:
            response=requests.get(url,timeout=30)
            if response.status_code==404 and 'schema.embedded.json' in url:
                # Some published schema IDs use a dot while the served filename
                # uses a hyphen. Resolve that official-resource filename alias.
                actual=url.replace('schema.embedded.json','schema-embedded.json')
                response=requests.get(actual,timeout=30)
                aliases.append({'schema_id':url,'served_url':actual})
            response.raise_for_status()
            cache[url]=response.json()
        return cache[url]
    checked=0
    errors=[]
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',DeprecationWarning)
        for file in (ROOT/'powerbi').rglob('*'):
            if not file.is_file() or file.suffix not in ['.json','.pbip','.pbir','.pbism']:continue
            value=json.loads(file.read_text())
            url=value.get('$schema')
            if not url:continue
            schema=fetch(url)
            resolver=jsonschema.RefResolver(base_uri=url,referrer=schema,handlers={'https':fetch})
            problems=list(jsonschema.Draft7Validator(schema,resolver=resolver).iter_errors(value))
            for error in problems:
                errors.append({'file':str(file.relative_to(ROOT)),'path':list(error.path),'error':error.message})
            checked+=1
    report={'schema_checked_files':checked,'schema_errors':errors,'official_schema_resources':len(cache),
            'resource_aliases':aliases,'desktop_refresh_verified':False,
            'note':'JSON schema validation does not validate DAX, M execution, semantic-model refresh, or visual rendering in Power BI Desktop.'}
    (ROOT/'data/exports/powerbi_schema_verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    if errors:raise SystemExit(1)

if __name__=='__main__':main()

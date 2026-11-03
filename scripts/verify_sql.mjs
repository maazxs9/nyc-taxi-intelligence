// Portable PostgreSQL verification without access to an existing server's credentials.
import {readFile,writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const {PGlite}=await import(process.env.PGLITE_MODULE||'@electric-sql/pglite');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const db=await PGlite.create();
const schema=await readFile(path.join(root,'sql/schema.sql'),'utf8');
await db.exec(schema);
await db.exec(schema); // Schema migrations can be rerun without dropping data.
for(const [table,name] of [['zones','zones'],['dates','dates'],['hourly','hourly'],['predictions','predictions']]) {
  const file=await readFile(path.join(root,'data/exports',name+'.csv'));
  await db.exec(`COPY taxi.${table} FROM '/dev/blob' WITH (FORMAT CSV, HEADER TRUE)`,{blob:new Blob([file])});
  console.log('Loaded '+table);
}
const result=(await db.query('SELECT sum(pickups)::bigint AS pickups,sum(fare_revenue) AS fare_revenue,count(*) AS hourly_rows FROM taxi.hourly')).rows[0];
const quality=JSON.parse(await readFile(path.join(root,'data/exports/quality.json'),'utf8'));
assert.equal(Number(result.pickups),quality.pickups);
assert.ok(Math.abs(result.fare_revenue-quality.fare_revenue)<.02);
const scores=(await db.query('SELECT avg(abs(actual-prediction)) AS mae,sum(abs(actual-prediction))/sum(actual) AS wape FROM taxi.predictions')).rows[0];
const metrics=JSON.parse(await readFile(path.join(root,'data/exports/model_metrics.json'),'utf8'));
assert.ok(Math.abs(scores.mae-metrics.model.mae)<1e-8);
assert.ok(Math.abs(scores.wape-metrics.model.wape)<1e-8);
const analyses=await db.exec(await readFile(path.join(root,'sql/analysis.sql'),'utf8'));
assert.equal(analyses.length,5);
const version=(await db.query('SELECT version()')).rows[0].version;
const verification={engine:'PGlite embedded PostgreSQL',version,full_hourly_aggregate_rows:Number(result.hourly_rows),
  full_pickups_reconciled:Number(result.pickups),model_mae:scores.mae,model_wape:scores.wape,
  schema_rerun_passed:true,analytical_queries_passed:5,
  native_server_load_verified:false,note:'Full aggregates and held-out predictions verified in embedded PostgreSQL. Native psycopg trip-fact load still requires authenticated PostgreSQL.'};
await writeFile(path.join(root,'data/exports/sql_verification.json'),JSON.stringify(verification,null,2));
console.log(JSON.stringify(verification,null,2));
await db.close();

'use strict';
let DATA, FORECAST, GEO;
const $ = id => document.getElementById(id);
const fmt = (v,d=0) => Number(v).toLocaleString('en-US',{maximumFractionDigits:d,minimumFractionDigits:d});
const compact = v => Math.abs(v)>=1e6 ? (v/1e6).toFixed(2)+'M' : Math.abs(v)>=1e3 ? (v/1e3).toFixed(1)+'K' : fmt(v);
const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const sum = (rows,key) => rows.reduce((s,r)=>s+Number(r[key]||0),0);
const ZONES = new Map();
const STATE = {metric:'pickups',forecastMode:'test'};
const NS='http://www.w3.org/2000/svg';
function metric(label,value,note,symbol='↗') {return `<div class="metric"><span class="metric-symbol">${symbol}</span><div class="metric-label">${label}</div><div class="value">${value}</div><small>${note}</small></div>`;}
function zoneName(id) {return ZONES.get(Number(id))?.zone || 'Unknown';}
function go(page) {
  if(!['overview','patterns','forecast','methodology'].includes(page))page='overview';
  document.querySelectorAll('.page').forEach(el=>el.classList.toggle('active',el.id===page));
  document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  history.replaceState(null,'','#'+page);
}
document.querySelectorAll('[data-page]').forEach(el=>el.addEventListener('click',()=>go(el.dataset.page)));
document.querySelectorAll('[data-go]').forEach(el=>el.addEventListener('click',()=>go(el.dataset.go)));
window.addEventListener('hashchange',()=>go(location.hash.slice(1)));
function plot(target, labels, lines, {money=false,fill=false}={}) {
  if(!labels.length){$(target).innerHTML='<p class="empty">No observations for this selection.</p>';return;}
  const W=1000,H=235,L=58,R=18,T=16,B=35,w=W-L-R,h=H-T-B;
  const all=lines.flatMap(s=>s.values).filter(Number.isFinite);
  const maximum=Math.max(1,...all)*1.1;
  const x=i=>L+i*w/Math.max(1,labels.length-1),y=v=>T+h-v/maximum*h;
  let svg=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(lines.map(l=>l.name).join(', '))} by time">`;
  for(let i=0;i<=4;i++) {let v=maximum*i/4;svg+=`<line class="grid" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L-10}" y="${y(v)+3}" text-anchor="end">${money?'$':''}${compact(v)}</text>`;}
  const ticks=[...new Set([0,Math.floor((labels.length-1)*.25),Math.floor((labels.length-1)*.5),Math.floor((labels.length-1)*.75),labels.length-1])];
  ticks.forEach(i=>svg+=`<text x="${x(i)}" y="${H-7}" text-anchor="middle">${esc(labels[i])}</text>`);
  lines.forEach((s,si)=>{
    const path=s.values.map((v,i)=>(i?'L':'M')+x(i).toFixed(2)+','+y(v).toFixed(2)).join(' ');
    if(fill&&si===0) svg+=`<path d="${path} L${x(labels.length-1)},${T+h} L${L},${T+h}Z" fill="${s.color}" opacity=".06"/>`;
    svg+=`<path d="${path}" fill="none" stroke="${s.color}" stroke-width="2.5" stroke-linejoin="round" ${s.dash?'stroke-dasharray="5 5"':''}/>`;
    s.values.forEach((v,i)=>svg+=`<circle cx="${x(i)}" cy="${y(v)}" r="5" fill="transparent"><title>${esc(labels[i])} · ${esc(s.name)}: ${money?'$':''}${fmt(v,1)}</title></circle>`);
  });
  $(target).innerHTML=svg+'</svg>';
}
function color(value,max) {
  const t=Math.sqrt(Math.max(0,value)/Math.max(1,max));
  return `rgb(${Math.round(29+99*t)},${Math.round(48+166*t)},${Math.round(62+127*t)})`;
}
function showPattern(zone) {$('pattern-zone').value=String(zone);renderPatterns();go('patterns');window.scrollTo({top:0,behavior:'smooth'});}
function renderMap(zoneTotals) {
  const max=Math.max(1,...zoneTotals.values());
  const project=([lon,lat])=>[(lon+74.28)*1030+8,(40.94-lat)*1030+3];
  $('zone-map').innerHTML=GEO.features.map(f=>{
    const id=Number(f.properties.zone_id),v=zoneTotals.get(id)||0;
    const rings=f.geometry.type==='MultiPolygon'?f.geometry.coordinates.flat():f.geometry.coordinates;
    const path=rings.map(r=>r.map((p,i)=>(i?'L':'M')+project(p).map(n=>n.toFixed(1)).join(',')).join(' ')+' Z').join(' ');
    return `<path class="zone-shape" d="${path}" fill="${color(v,max)}" fill-rule="evenodd" data-zone="${id}" tabindex="0" role="button" aria-label="${esc(zoneName(id))}: ${fmt(v)} pickups. Explore patterns."><title>${esc(zoneName(id))}\n${fmt(v)} pickups</title></path>`;
  }).join('');
  $('zone-map').querySelectorAll('[data-zone]').forEach(el=>{
    el.addEventListener('click',()=>showPattern(el.dataset.zone));
    el.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();showPattern(el.dataset.zone);}});
  });
}
function renderOverview() {
  let from=$('from').value,to=$('to').value;
  if(!from||!to)return;
  if(from>to){$('to').value=from;to=from;}
  const borough=$('borough').value;
  const rows=DATA.daily.filter(r=>r.date>=from&&r.date<=to&&(!borough||ZONES.get(r.zone_id)?.borough===borough));
  const pickups=sum(rows,'pickups'),financial=sum(rows,'financial_trips'),fare=sum(rows,'fare_revenue'),charges=sum(rows,'total_charges');
  $('overview-metrics').innerHTML=metric('Observed pickups',compact(pickups),fmt(pickups)+' accepted trips','↗')+metric('Metered fare revenue','$'+compact(fare),'Eligible financial trips only','$')+metric('Total recorded charges','$'+compact(charges),'Excludes unrecorded cash tips','$')+metric('Average metered fare',financial?'$'+fmt(fare/financial,2):'—',fmt(financial)+' eligible trips','∅');
  const totals=new Map();rows.forEach(r=>totals.set(r.zone_id,(totals.get(r.zone_id)||0)+r.pickups));
  renderMap(totals);
  const ranked=[...totals].sort((a,b)=>b[1]-a[1]).filter(x=>x[1]>0).slice(0,8);
  $('zone-rankings').innerHTML=ranked.map(([id,value],i)=>`<button class="rank" data-zone="${id}"><span class="rank-n">${String(i+1).padStart(2,'0')}</span><span class="rank-body"><span class="rank-name">${esc(zoneName(id))}</span><span class="rank-bar"><span class="rank-fill" style="width:${value/ranked[0][1]*100}%"></span></span></span><span class="rank-value">${compact(value)}</span></button>`).join('') || '<p class="empty">No trips in this selection.</p>';
  $('zone-rankings').querySelectorAll('[data-zone]').forEach(el=>el.addEventListener('click',()=>showPattern(el.dataset.zone)));
  const days=new Map();rows.forEach(r=>days.set(r.date,(days.get(r.date)||0)+r[STATE.metric]));
  const ordered=[...days].sort((a,b)=>a[0].localeCompare(b[0]));
  plot('daily-chart',ordered.map(d=>new Date(d[0]+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})),[{name:STATE.metric.replaceAll('_',' '),values:ordered.map(d=>d[1]),color:'#72d9bc'}],{money:STATE.metric!=='pickups',fill:true});
}
function renderPatterns() {
  const id=Number($('pattern-zone').value),rows=DATA.profile.filter(r=>r.zone_id===id);
  const total=DATA.daily.filter(r=>r.zone_id===id),pickups=sum(total,'pickups');
  const busiest=[...rows].sort((a,b)=>b.mean_pickups-a.mean_pickups)[0];
  const days=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  $('pattern-metrics').innerHTML=metric('Quarter pickups',compact(pickups),zoneName(id))+metric('Mean hourly pickups',fmt(pickups/DATA.summary.observed_hours,1),'Includes zero-pickup hours')+metric('Busiest typical period',busiest?days[busiest.weekday]+' '+String(busiest.hod).padStart(2,'0')+':00':'—','Based on weekday-hour means')+metric('Area',esc(ZONES.get(id)?.borough==='EWR'?'Newark Airport (NJ)':ZONES.get(id)?.borough||'Unknown'),'Official TLC zone lookup');
  let heat='<span></span>'+Array.from({length:24},(_,h)=>`<span class="heat-hour">${String(h).padStart(2,'0')}</span>`).join('');
  const max=Math.max(1,...rows.map(r=>r.mean_pickups));
  for(let d=0;d<7;d++) {heat+=`<span class="heat-label">${days[d]}</span>`;for(let h=0;h<24;h++) {const r=rows.find(r=>r.weekday===d&&r.hod===h);heat+=`<div class="heat-cell" tabindex="0" style="background:${color(r?.mean_pickups||0,max)}" title="${days[d]} ${h}:00: ${fmt(r?.mean_pickups||0,1)} mean pickups across ${r?.observed_hours||0} observed hours" aria-label="${days[d]} ${h}:00: ${fmt(r?.mean_pickups||0,1)} average pickups"></div>`;}}
  $('heatmap').innerHTML=heat;
  const profile=Array.from({length:24},(_,h)=>{let part=rows.filter(r=>r.hod===h);return sum(part,'pickups')/Math.max(1,sum(part,'observed_hours'));});
  plot('profile-chart',Array.from({length:24},(_,h)=>String(h).padStart(2,'0')+':00'),[{name:'Mean pickups',values:profile,color:'#72d9bc'}],{fill:true});
}
function renderForecast() {
  const m=FORECAST.metrics;
  $('forecast-metrics').innerHTML=metric('Held-out model MAE',fmt(m.model.mae,1),'Pickups per zone-hour')+metric('Seasonal baseline MAE',fmt(m.baseline.mae,1),'Same hour, previous week')+metric('Reduction in MAE',fmt(m.mae_improvement_pct,1)+'%','Against the seasonal baseline')+metric('Held-out model WAPE',fmt(m.model.wape*100,1)+'%',fmt(m.model.observations)+' zone-hour predictions');
  const id=Number($('forecast-zone').value),origin=$('origin').value,isTest=STATE.forecastMode==='test';
  $('origin-label').hidden=!isTest;
  const selected=(isTest?FORECAST.predictions:FORECAST.snapshot).filter(r=>r.zone_id===id&&(!isTest||r.origin.slice(0,10)===origin)).sort((a,b)=>a.hour.localeCompare(b.hour));
  const lines=isTest?[{name:'Observed',values:selected.map(r=>r.actual),color:'#72d9bc'},
                     {name:'Model',values:selected.map(r=>r.prediction),color:'#efc436'},
                     {name:'Seasonal baseline',values:selected.map(r=>r.baseline),color:'#91a5b7',dash:true}]:
                    [{name:'Snapshot forecast',values:selected.map(r=>r.prediction),color:'#efc436'}];
  plot('forecast-chart',selected.map(r=>r.hour.slice(11,16)),lines);
  $('forecast-legend').innerHTML=isTest?'<span>Observed pickups</span><span class="pred">Model prediction</span><span class="base">Seasonal baseline</span>':'<span class="pred">April 1, 2025 · snapshot forecast</span>';
  $('forecast-caption').textContent=isTest?`Forecast issued at midnight on ${origin}, using only prior observations. ${zoneName(id)} · 24-hour horizon. The scores above cover all 20 zones and all 7 test dates, not just this selection.`:'Archived-snapshot forecast for April 1, 2025, generated from data through March 31. It is not a live or current forecast. Actual April 1 pickups are not included. The headline test metrics describe a separately evaluated, fixed model.';
}
document.querySelectorAll('#metric-switch button').forEach(el=>el.addEventListener('click',()=>{STATE.metric=el.dataset.metric;document.querySelectorAll('#metric-switch button').forEach(b=>b.classList.toggle('selected',b===el));renderOverview();}));
document.querySelectorAll('#forecast-switch button').forEach(el=>el.addEventListener('click',()=>{STATE.forecastMode=el.dataset.mode;document.querySelectorAll('#forecast-switch button').forEach(b=>b.classList.toggle('selected',b===el));renderForecast();}));
async function init() {
  try {
    [DATA,FORECAST,GEO]=await Promise.all(['data.json','forecast.json','zones.geojson'].map(async name=>{const response=await fetch('assets/'+name);if(!response.ok)throw new Error(name+' failed to load');return response.json();}));
    DATA.zones.forEach(z=>ZONES.set(z.zone_id,z));
    const zones=DATA.zones.filter(z=>z.zone_id<=263).sort((a,b)=>a.zone.localeCompare(b.zone));
    const options=list=>list.map(z=>`<option value="${z.zone_id}">${esc(z.zone)}</option>`).join('');
    $('pattern-zone').innerHTML=options(zones);$('pattern-zone').value='161';
    $('forecast-zone').innerHTML=options(zones.filter(z=>FORECAST.metrics.zones.includes(z.zone_id)));$('forecast-zone').value='161';
    const origins=[...new Set(FORECAST.predictions.map(r=>r.origin.slice(0,10)))].sort();
    $('origin').innerHTML=origins.map(date=>`<option>${date}</option>`).join('');
    const boroughs=[...new Set(zones.map(z=>z.borough))].sort();
    boroughs.forEach(b=>{const o=document.createElement('option');o.value=b;o.textContent=b==='EWR'?'Newark Airport (NJ)':b;$('borough').append(o);});
    ['from','to','borough'].forEach(id=>$(id).addEventListener('change',renderOverview));
    $('pattern-zone').addEventListener('change',renderPatterns);
    ['forecast-zone','origin'].forEach(id=>$(id).addEventListener('change',renderForecast));
    $('model-insight').innerHTML=`The model reduced held-out MAE by <strong>${fmt(FORECAST.metrics.mae_improvement_pct,1)}%</strong> versus the previous-week baseline across 20 zones and 7 test days.`;
    $('scores').innerHTML=[...FORECAST.metrics.by_zone].sort((a,b)=>a.model.mae-b.model.mae).map(r=>`<tr><td>${esc(zoneName(r.zone_id))}</td><td>${fmt(r.model.mae,1)}</td><td>${fmt(r.baseline.mae,1)}</td><td>${r.model.wape===null?'—':fmt(r.model.wape*100,1)+'%'}</td></tr>`).join('');
    $('quality-details').innerHTML=`<p><strong>${fmt(DATA.summary.source_rows)}</strong> source records across three files.<br><strong>${fmt(DATA.summary.pickups)}</strong> accepted pickups.<br><strong>${fmt(DATA.summary.source_rows-DATA.summary.pickups)}</strong> records excluded by the documented rules.<br><strong>${fmt(DATA.summary.financial_trips)}</strong> pickups eligible for financial metrics.</p>`;
    renderOverview();renderPatterns();renderForecast();go(location.hash.slice(1)||'overview');
    $('loading').hidden=true;$('app').hidden=false;
  }catch(error){$('loading').textContent='The data could not be loaded. Refresh the page, or run the project’s local server. '+error.message;}
}
init();

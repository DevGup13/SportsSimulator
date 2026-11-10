from pathlib import Path
from datetime import datetime,timezone,timedelta
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import json

root=Path(__file__).resolve().parents[1]
target=root/'site/live-fixtures/data.json'
leagues={
 'uefa.champions':'UCL','eng.1':'Premier League',
 'esp.1':'La Liga','ger.1':'Bundesliga',
 'ita.1':'Serie A','fra.1':'Ligue 1','usa.1':'MLS'
}
now=datetime.now(timezone.utc)
end=now+timedelta(days=21)
months=sorted({now.strftime('%Y%m'),end.strftime('%Y%m')})
seen={};errors={};success=0

for slug,name in leagues.items():
 for month in months:
  url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+slug+'/scoreboard?'+urlencode({'dates':month,'limit':500})
  try:
   with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'}),timeout=18) as r:
    obj=json.load(r)
   if not isinstance(obj.get('events'),list):
    raise ValueError('Unexpected response')
   success+=1

   for event in obj['events']:
    try:
     c={x['homeAway']:x['team'] for x in event['competitions'][0]['competitors']}
     h,a=c['home'],c['away']
     date=datetime.fromisoformat(event['date'].replace('Z','+00:00'))
     if not (now<=date<=end) or event.get('status',{}).get('type',{}).get('completed'):
      continue

     eid=str(event['id'])
     seen[(slug,eid)]={
      'league_slug':slug,'league':name,'event_id':eid,
      'home_id':str(h['id']),'away_id':str(a['id']),
      'home':h.get('displayName') or h.get('name'),
      'away':a.get('displayName') or a.get('name'),
      'kickoff_utc':date.isoformat(),'status':'scheduled',
      'completed':False,'provider':'ESPN',
      'provider_ids_present':True,
      'warehouse_identity_join_verified':False,
      'certified_forecast':False
     }
    except (KeyError,TypeError,ValueError,IndexError):
     pass
  except Exception as exc:
   errors[slug+'/'+month]=str(exc)[:130]

# Fail closed on incomplete provider responses.
if success!=len(leagues)*len(months):
 raise SystemExit('Refresh incomplete; prior snapshot retained: '+str(errors))
if not seen:
 raise SystemExit('No upcoming fixtures; prior snapshot retained')

data={
 'version':'AUTO_SNAPSHOT',
 'retrieved_utc':now.isoformat(),
 'window_end_utc':end.isoformat(),
 'query_months':months,
 'provider':'ESPN',
 'successful_requests':success,
 'leagues_requested':len(leagues),
 'source_failures':{},
 'events':sorted(seen.values(),key=lambda x:x['kickoff_utc']),
 'automated_refresh':True,
 'historical_identity_mapping_verified':False,
 'forecasts_certified':False
}
target.parent.mkdir(parents=True,exist_ok=True)
tmp=target.with_name('data.json.tmp')
tmp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf8')
tmp.replace(target)
print('Refreshed',len(seen),'fixtures at',now.isoformat())

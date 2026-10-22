"""Discover official metropolitan delimitation and INEGI boundaries; public metadata only."""
from concurrent.futures import ThreadPoolExecutor
import datetime,hashlib,html,json,re,urllib.request
from pathlib import Path

URLS={
 'conapo':'https://www.gob.mx/conapo/documentos/las-metropolis-de-mexico-2020',
 'sedatu':'https://www.gob.mx/sedatu/documentos/metropolis-de-mexico-2020',
 'inegi_metro':'https://www.inegi.org.mx/temas/estructura/',
 'municipalities':'https://gaia.inegi.org.mx/wscatgeo/v2/mgem/19',
 'boundaries':'https://gaia.inegi.org.mx/wscatgeo/v2/geo/mgem/19',
 'terms':'https://www.inegi.org.mx/inegi/terminos.html',
 'rnc':'https://www.inegi.org.mx/temas/viascomunicacion/',
 'wikipedia_reference_discovery':'https://en.wikipedia.org/wiki/Monterrey_metropolitan_area',
 'search_reference_discovery':'https://www.bing.com/search?q=site%3Agob.mx+Metropolis+Mexico+2020+xlsx+Monterrey',
 'copernicus_catalog':'https://copernicus-dem-30m.s3.amazonaws.com/tileList.txt'}


def get(item):
 key,url=item;r={'key':key,'url':url};out=Path('artifacts/geo005-research');out.mkdir(parents=True,exist_ok=True)
 try:
  request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 public geographic research MonterreyOpenWorld'})
  with urllib.request.urlopen(request,timeout=40)as response:body=response.read(25_000_001);r.update(http_status=response.status,content_type=response.headers.get('Content-Type'))
  if len(body)>25_000_000:raise ValueError('Metadata size cap')
  (out/(key+'.body')).write_bytes(body);r.update(bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
  text=body.decode(errors='replace');r['links']=sorted(set(html.unescape(x)for x in re.findall(r'(?:href|src)=[\"\x27]([^\"\x27]+)',text)if any(w in x.lower()for w in ['metrop','xlsx','.zip','.pdf','conapo','sedatu'])))[:100]
  plain=html.unescape(re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',text)))
  r['excerpts']=[]
  for term in ['Monterrey','16 municipios','18 municipios','metrópolis','Puede explotar comercialmente','2025','2024']:
   i=plain.lower().find(term.lower())
   if i>=0:r['excerpts'].append(plain[max(0,i-50):i+350])
  if key=='municipalities':r['data']=json.loads(body)
  if key=='boundaries':
   data=json.loads(body);r['json_keys']=list(data);r['features_count']=len(data.get('features',[]));r['first_feature_properties']=(data.get('features')or[{}])[0].get('properties')
 except Exception as e:r['error']=str(e)
 return r


if __name__=='__main__':
 with ThreadPoolExecutor(4)as pool:records=list(pool.map(get,URLS.items()))
 p=Path('docs/geo005/official-discovery.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps({'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'budget_usd':0,'discovery_is_not_source_acceptance':True,'records':records},indent=2,ensure_ascii=False)+'\n')
 print(json.dumps([{k:v for k,v in r.items()if k in ('key','http_status','bytes','error','features_count')}for r in records],indent=2))

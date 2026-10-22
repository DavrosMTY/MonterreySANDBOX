"""Read official metadata/terms only. Never accesses Google map/elevation imagery."""
from concurrent.futures import ThreadPoolExecutor
import datetime
import hashlib
import html
import json
from pathlib import Path
import re
import urllib.request

URLS={
 'inegi_terms':'https://www.inegi.org.mx/inegi/terminos.html',
 'inegi_relief':'https://www.inegi.org.mx/temas/relieve/continental/',
 'inegi_geoid':'https://www.inegi.org.mx/temas/geoide/',
 'inegi_cem_versions':'https://www.inegi.org.mx/app/geo2/elevacionesmex/api/versiones',
 'inegi_cem4_resolutions':'https://www.inegi.org.mx/app/geo2/elevacionesmex/api/resoluciones?version=2',
 'inegi_cem4_nuevo_leon':'https://www.inegi.org.mx/app/geo2/elevacionesmex/api/archivos?version=2&opcion=15&clave=19',
 'inegi_geodetic_network':'https://www.inegi.org.mx/app/geo2/rgp/',
 'nuevo_leon_cartography':'https://www.nl.gob.mx/es/servicios/cartografia',
 'monterrey_official':'https://www.monterrey.gob.mx/',
 'google_geo_guidelines':'https://about.google/brand-resource-center/products-and-services/geo-guidelines/',
 'google_maps_platform_terms':'https://cloud.google.com/maps-platform/terms',
 'google_maps_earth_additional_terms':'https://www.google.com/help/terms_maps/'}
TERMS=['Puede hacer y distribuir','Puede explotar comercialmente','créditos','scrap','Scrap','No Scraping','No Export','create content','create or augment','derive','dataset','3D','terrain','game','juego','15','datum','NAVD88']


def get(item):
    key,url=item
    record={'id':key,'url':url,'content_use':'Official metadata / legal research only; no Google geographic content'}
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 MonterreyOpenWorld source research'})
        with urllib.request.urlopen(request,timeout=25)as response:
            body=response.read(4000001);record['http_status']=response.status;record['final_url']=response.url
        if len(body)>4000000:raise ValueError('Document size cap')
        text=html.unescape(re.sub('<[^>]+>',' ',body.decode(errors='replace')));text=re.sub(r'\s+',' ',text)
        record.update(sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),excerpts=[])
        for term in TERMS:
            pos=text.lower().find(term.lower())
            if pos>=0:record['excerpts'].append({'term':term,'text':text[max(0,pos-40):pos+220]})
        if body.startswith((b'[{',b'{')):record['metadata']=json.loads(body)
    except Exception as e:record['error']=str(e)
    return record


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=3)as pool:records=list(pool.map(get,URLS.items()))
    report={'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'paid_services':False,
            'no_google_geographic_data_requested':True,'records':records}
    p=Path('docs/geo004/official-source-research.json');p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps([{k:r[k]for k in ('id','http_status','error')if k in r}for r in records],indent=2))

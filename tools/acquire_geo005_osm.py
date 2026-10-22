import urllib.request,json,hashlib,datetime
from pathlib import Path
from pyproj import Transformer
m=json.load(open('Data/unreal/monterrey_centro_single_v3/manifest.json'));e,n=m['center_easting_northing_m'];lon,lat=Transformer.from_crs(32614,4326,always_xy=True).transform(e,n+1500)
bounds=Transformer.from_crs(32614,4326,always_xy=True).transform_bounds(e-500,n+1000,e+500,n+2000)
query=f'[out:json][timeout:90];(way["highway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});way["building"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});relation["building"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});nwr["natural"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});nwr["landuse"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});nwr["leisure"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});nwr["waterway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});nwr["railway"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]}););(._;>>;);out meta;'
p=Path('artifacts/geo005-sector-inputs');p.mkdir(exist_ok=True);(p/'query.overpass').write_text(query)
print(json.dumps({'center_lat_lon':[lat,lon],'center_utm':[e,n+1500],'bounds_lonlat':bounds,'extent_m':1000,'shared_border_with_pilot_m':1000},indent=2),flush=True)
url='https://overpass-api.de/api/interpreter'
try:
 req=urllib.request.Request(url,data=query.encode(),headers={'User-Agent':'MonterreyOpenWorld METRO001/0.1 GIS research; no background polling','Content-Type':'text/plain'})
 with urllib.request.urlopen(req,timeout=110)as r:body=r.read(30_000_001)
 d=json.loads(body);assert 'remark'not in d and isinstance(d.get('elements'),list)and len(body)<30_000_000
 (p/'osm.json').write_bytes(body);(p/'osm.json.source.json').write_text(json.dumps({'source':'OpenStreetMap via public Overpass','url':url,'query':query,'sha256':hashlib.sha256(body).hexdigest(),'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'license':'ODbL-1.0','license_url':'https://www.openstreetmap.org/copyright','bbox_lonlat':bounds,'observation_date_warning':'Acquisition and OSM last edit do not establish physical observation dates'},indent=2)+'\n');print('OSM acquired',len(body),len(d['elements']))
except Exception as ex:print('OSM local blocked',str(ex))

"""Build the WORLD-002 viewer from immutable GEO-003 plus separately labelled visuals."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

import numpy as np
from pyproj import Transformer
import rasterio

from build_web_viewer import build,sha,ROOT


def background(dem_path,center):
    source=json.loads((ROOT/'Data/raw/copernicus_reviewed.source.json').read_text())
    dem_path=Path(dem_path)
    if not dem_path.exists():
        dem_path.parent.mkdir(parents=True,exist_ok=True)
        request=urllib.request.Request(source['url'],headers={'User-Agent':'MonterreyOpenWorld/0.2 public open DEM'})
        with urllib.request.urlopen(request,timeout=60) as response:
            payload=response.read(50_000_001)
        if len(payload)>50_000_000:raise ValueError('DEM download size cap exceeded')
        if hashlib.sha256(payload).hexdigest()!=source['sha256']:raise ValueError('DEM provenance mismatch')
        dem_path.write_bytes(payload)
    if sha(dem_path)!=source['sha256']:raise ValueError('DEM provenance mismatch')
    levels=[];transform=Transformer.from_crs('EPSG:32614','EPSG:4326',always_xy=True)
    with rasterio.open(dem_path) as ds:
        raster=ds.read(1)
        for step in (360,180,90):
            axis=np.arange(-18000,18001,step);xx,zz=np.meshgrid(axis,axis)
            lon,lat=transform.transform(center[0]+xx,center[1]-zz)
            col,row=(~ds.transform)*(lon,lat);col=np.floor(col).astype(int);row=np.floor(row).astype(int)
            if (col<0).any()or(row<0).any()or(col>=ds.width).any()or(row>=ds.height).any():raise ValueError('Background outside licensed DEM tile')
            heights=raster[row,col].astype(float)
            if not np.isfinite(heights).all()or(heights<0).any():raise ValueError('Missing DEM elevation')
            levels.append({'spacing_m':step,'n':len(axis),'heights_m':np.round(heights,2).ravel().tolist()})
    return {'schema_version':1,'source_url':source['url'],'source_sha256':source['sha256'],
        'source_resolution_m':30,'source_model':'Copernicus GLO-30 DSM, not bare-earth DTM',
        'source_crs':'EPSG:4326','render_crs':'EPSG:32614','vertical_datum':'EGM2008',
        'center_easting_northing_m':center,'bounds_local_m':[-18000,18000],
        'not_playable':True,'exclude_pilot_half_extent_m':1000,'seam_policy':'Exclude only faces wholly inside the pilot; outer LOD faces overlap the boundary behind the authoritative city depth pass','lods':levels,
        'camera_presets':{'silla':{'target':[6500,1550,6200],'label':'Sureste · área del Cerro de la Silla'},
                          'sierra':{'target':[-8500,1800,10500],'label':'Surponiente · Sierra Madre Oriental'},
                          'larga':{'target':[-1500,720,2500],'label':'Sur cercano · Loma Larga'}},
        'preset_note':'Camera directions towards the landforms, not surveyed peak annotations. All silhouettes are sampled from the georeferenced DEM; no invented peaks.'}


def build_world(city,output,dem):
    result=build(city,output,visual=True)
    out=Path(output)
    mountain=background(dem,result['center_easting_northing_m'])
    p=out/'assets/background.json.gz';p.write_bytes(gzip.compress(json.dumps(mountain,separators=(',',':')).encode(),mtime=0))
    result['background']={'url':'assets/'+p.name,'sha256':sha(p),'bytes':p.stat().st_size,
                          'source_sha256':mountain['source_sha256'],'non_playable':True}
    (out/'licenses/osm-street-inventory.json').write_bytes((ROOT/'WebViewer/visual/osm-street-inventory.json').read_bytes())
    (out/'licenses/osm-street-inventory.source.json').write_bytes((ROOT/'WebViewer/visual/osm-street-inventory.source.json').read_bytes())
    (out/'visual-catalog.json').write_bytes((ROOT/'WebViewer/visual/catalog.json').read_bytes())
    result['visual_catalog']={'url':'visual-catalog.json','sha256':sha(out/'visual-catalog.json')}
    (out/'world.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'licenses/WORLD002_VISUALS.txt').write_text('Original visual recipe parameters, generated textures, vegetation and furniture art: CC0 1.0 Universal. https://creativecommons.org/publicdomain/zero/1.0/\nNo change to the game source code license. Geographic data retain ODbL and Copernicus conditions.\nStreet positions from OSM when tagged; facade layouts, dimensions, decorative planting and markings are estimates.\n')
    size=sum(p.stat().st_size for p in out.rglob('*')if p.is_file())
    if size>50*1024**2:raise ValueError('Deployment exceeds 50 MiB cap')
    print(json.dumps({'milestone':'WORLD-002','site_bytes':size,'background_bytes':result['background']['bytes'],'background_lods':[x['spacing_m']for x in mountain['lods']],'visual_stats':result['visual_overlay']['stats']},indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city',default='Data/city/geo003_world001');p.add_argument('--output',required=True)
    p.add_argument('--dem',default='artifacts/world002-inputs/regional-dem.tif')
    a=p.parse_args();build_world(a.city,a.output,a.dem)

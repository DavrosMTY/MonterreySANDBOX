"""Validate visual attributes, original OSM positions and native DEM samples independently."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import struct

import numpy as np
from pyproj import Transformer
import rasterio

from build_web_viewer import ROOT,sha
from world002_decor import lane_policy
from world002_visual import recipe


def validate(city,site,dem):
    city,site=Path(city),Path(site)
    world=json.loads((site/'world.json').read_text());assert world['milestone']=='WORLD-002'
    features=json.loads((site/world['features_url']).read_text())
    roads={r['id']:r for r in json.loads((city/'road_semantics.json').read_text())['roads']}
    checked=0
    for sector in world['sectors']:
        p=site/sector['url'];assert sha(p)==sector['sha256']
        b=gzip.decompress(p.read_bytes());length=struct.unpack_from('<I',b,12)[0]
        doc=json.loads(b[20:20+length]);binary=b[28+length:]
        for mesh in doc['meshes']:
            primitive=mesh['primitives'][0];attribute=primitive['attributes'].get('_MOW_STYLE')
            if mesh['name'] not in ('Buildings','Roads','Bridges'):
                assert attribute is None;continue
            accessor=doc['accessors'][attribute];view=doc['bufferViews'][accessor['bufferView']]
            dtype={5126:'<f4',5121:'u1'}[accessor['componentType']]
            a=np.frombuffer(binary,dtype=dtype,count=accessor['count']*4,offset=view.get('byteOffset',0)+accessor.get('byteOffset',0)).reshape(-1,4)
            assert np.isfinite(a).all();offset=0
            for f in features[sector['id']][mesh['name']]:
                count=f['source']['vertex_count'];expected=np.asarray(recipe(f['source'],roads),dtype=dtype)
                assert np.array_equal(a[offset:offset+count],np.tile(expected,(count,1)))
                offset+=count;checked+=1
            assert offset==len(a)
    def read(record):
        p=site/record['url'];assert sha(p)==record['sha256'];return json.loads(gzip.decompress(p.read_bytes()))
    overlay=read(world['visual_overlay']);inventory=json.loads((ROOT/'WebViewer/visual/osm-street-inventory.json').read_text())
    assert sha(ROOT/'WebViewer/visual/osm-street-inventory.json')==overlay['source_inventory_sha256']
    nodes={f"node/{n['id']}":n for n in inventory['elements']};transform=Transformer.from_crs(4326,32614,always_xy=True)
    counts=Counter();confirmed=0;paint=0
    for cell,records in overlay['sectors'].items():
        for r in records:
            x,h,z=r['position'];assert np.isfinite([x,h,z]).all() and abs(x)<=1000 and abs(z)<=1000
            cx,cy=map(int,cell.split('_'));assert cx*250-1000-1e-4<=x<=(cx+1)*250-1000+1e-4
            assert cy*250-1000-1e-4<=-z<=(cy+1)*250-1000+1e-4
            counts[r['kind']]+=1;assert r['dimensions_estimated']
            if r['placement']=='osm_node':
                node=nodes[r['source_id']];east,north=transform.transform(node['lon'],node['lat']);c=world['center_easting_northing_m']
                assert abs(x-(east-c[0]))<1e-4 and abs(z+(north-c[1]))<1e-4
                assert node['tags']==r['source_tags'];confirmed+=1
            elif r['kind'].startswith('lane_'):
                policy=lane_policy(roads[r['source_id']]['tags']);assert policy is not None
                assert policy['color']==r['kind'][5:] and policy['count']==r['source_lanes'];paint+=1
            elif r['kind']=='crossing':assert r['source_id'] in nodes
            else:assert r['placement']=='procedural_on_existing_sidewalk' and r['source_mesh']
    assert dict(counts)==overlay['stats'] and not overlay['geography_or_lane_graph_modified']
    bg=read(world['background']);assert bg['not_playable'] and sha(dem)==bg['source_sha256'];samples=0
    with rasterio.open(dem) as ds:
        raster=ds.read(1)
        for lod in bg['lods']:
            step=lod['spacing_m'];n=lod['n'];assert n==36000//step+1
            axis=np.arange(n)*step-18000;xx,zz=np.meshgrid(axis,axis);center=bg['center_easting_northing_m']
            tr=Transformer.from_crs(32614,4326,always_xy=True);lon,lat=tr.transform(center[0]+xx,center[1]-zz)
            col,row=(~ds.transform)*(lon,lat);actual=raster[np.floor(row).astype(int),np.floor(col).astype(int)]
            assert np.max(np.abs(actual-np.array(lod['heights_m']).reshape(n,n)))<=.00501;samples+=n*n
    return {'status':'passed','visual_mesh_attributes_checked':checked,'osm_node_positions_preserved':confirmed,
            'lane_dividers_require_explicit_tags':paint,'native_dem_samples_verified':samples,
            'dem_sha256':bg['source_sha256'],'visual_counts':dict(counts),'skipped':overlay['skipped'],
            'decorative_counts':overlay['decorative_counts'],'geographic_graph_modified':False,'unreal_executed':False}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--city',default='Data/city/geo003_world001');p.add_argument('--site',required=True);p.add_argument('--dem',required=True);p.add_argument('--receipt',required=True)
    a=p.parse_args();result=validate(a.city,a.site,a.dem);Path(a.receipt).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

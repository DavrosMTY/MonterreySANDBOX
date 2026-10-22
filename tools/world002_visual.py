"""Original visual layer; never changes GIS geometry or promotes estimates to fact."""
import hashlib
import json
from pathlib import Path
import numpy as np

CATALOG=json.loads((Path(__file__).resolve().parents[1]/'WebViewer/visual/catalog.json').read_text())


def recipe(record, roads=None):
    system=record.get('system')
    seed=int(hashlib.sha256(record['name'].encode()).hexdigest()[:8],16)/2**32
    if system=='Buildings':
        category=record.get('category','unknown')
        tags=record.get('source_tags',{})
        if tags.get('building') in ('office','commercial') and record.get('top_relative_ground_m',0)>28:
            category='corporate'
        return [CATALOG['styles'].get(category,5),seed,record.get('bottom_m',0),
                record.get('top_m',1)-record.get('bottom_m',0)]
    codes=CATALOG['surface_codes']
    tags=[(roads or {}).get(x,{}).get('tags',{}).get('surface','unknown')for x in record.get('source_road_ids',[])]
    known=set(codes.get(x,0)for x in tags)
    surface=known.pop() if len(known)==1 else 0
    return [surface,seed,0,0]


def style_attributes(meshes, roads=None):
    return np.concatenate([np.tile(np.array(recipe(record,roads),dtype='<f4'),(len(mesh.vertices),1))
                           for _,mesh,record in meshes])

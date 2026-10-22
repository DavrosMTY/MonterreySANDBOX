"""Engine-independent metropolitan polygons, stable metric tiles and honest coverage."""
import hashlib,json,math
from pathlib import Path

import numpy as np
from pyproj import CRS,Geod,Transformer
import shapely
from shapely.geometry import box,mapping,shape

TO_UTM=Transformer.from_crs(4326,32614,always_xy=True)
TO_WGS=Transformer.from_crs(32614,4326,always_xy=True)


def project(geometry,transformer=TO_UTM):
    return shapely.transform(geometry,lambda xy:np.column_stack(transformer.transform(xy[:,0],xy[:,1])))


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tile_id(east_index,north_index,size=500):
    if size not in (500,1000,2000):raise ValueError('Unsupported stable grid level')
    return f'utm14n_{size}_e{east_index}_n{north_index}'


def tiles(geometry,size=500):
    """Intersect the official polygon, including holes; a bbox is only an index."""
    if geometry.is_empty or not geometry.is_valid:raise ValueError('Require valid official metropolitan polygon')
    left,bottom,right,top=geometry.bounds
    for y in range(math.floor(bottom/size),math.ceil(top/size)):
        for x in range(math.floor(left/size),math.ceil(right/size)):
            square=box(x*size,y*size,(x+1)*size,(y+1)*size)
            if not square.intersects(geometry):continue
            clipped=square.intersection(geometry)
            if clipped.area<.01:continue
            yield {'id':tile_id(x,y,size),'east_index':x,'north_index':y,'size_m':size,'geometry':clipped,'grid_bounds_utm_m':square.bounds,'metropolitan_fraction':clipped.area/(size*size)}


def coverage(footprint,metropolitan):
    area=footprint.intersection(metropolitan).area
    return {'area_km2':area/1e6,'fraction':area/metropolitan.area,'percentage':area/metropolitan.area*100,'area_basis':'EPSG:32614 grid area; not an accuracy certificate'}


def official_union(boundaries,selection):
    if not selection.get('official_definition_url')or not selection.get('definition_evidence_sha256'):raise ValueError('Official selection evidence required')
    codes=selection['municipality_codes']
    if len(codes)!=len(set(codes))or not codes:raise ValueError('Duplicate/empty municipality selection')
    selected={};original={}
    for f in boundaries['features']:
        code=str(f['properties']['cvegeo'])
        if code not in codes:continue
        g=shape(f['geometry'])
        if not g.is_valid:raise ValueError('Official geometry invalid; preserve and review explicitly: '+code)
        if g.geom_type not in ('Polygon','MultiPolygon'):raise ValueError('Expected official municipal polygon')
        original[code]=f;selected[code]=project(g)
    if set(selected)!=set(codes):raise ValueError('Missing selected municipalities')
    metro=shapely.union_all(list(selected.values()))
    if not metro.is_valid:raise ValueError('Invalid union of official municipal boundaries')
    overlap=sum(g.area for g in selected.values())-metro.area
    if overlap>metro.area*1e-7:raise ValueError('Overlapping municipal source geometry')
    return metro,selected,original


def building_fidelity(tags,independent_height_evidence=None,independent_shape_evidence=None):
    """An attractive facade or an unverified OSM height never confers A/B."""
    from .urban import number
    height=number(tags.get('height'))
    height_ok=bool(independent_height_evidence and independent_height_evidence.get('validated')and independent_height_evidence.get('source_url'))
    shape_ok=bool(independent_shape_evidence and independent_shape_evidence.get('validated')and independent_shape_evidence.get('source_url'))
    return {'tier':'A'if height_ok and shape_ok else'B'if height_ok else'C','tagged_height_m':height,'height_verified':height_ok,'shape_verified':shape_ok,'tagged_height_is_not_verified_height':height is not None and not height_ok}


def choose_ground_source(records):
    eligible=[r for r in records if r.get('license_reviewed')and r.get('horizontal_crs')and r.get('vertical_operation_available')and r.get('model')=='DTM'and r.get('coverage_verified')]
    if not eligible:return None
    # Purpose and usable datum come before product spacing. Unknown EPV stays unknown.
    return sorted(eligible,key=lambda r:(r.get('vertical_accuracy_m')is None,r.get('vertical_accuracy_m')or math.inf,r['native_spacing_m']))[0]

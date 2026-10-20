"""Input geography and vertical crossing audit, separate from solid-mesh QA."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np
from pyproj import Geod, Transformer
import shapely
from shapely.geometry import shape
import trimesh

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from GeoPipeline.buildings3d import footprint_parts
from GeoPipeline.mesh import Surface
from GeoPipeline.mesh import enu_to_gltf
from GeoPipeline.roads3d import Network


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city',default='Data/city/geo002_v2'); p.add_argument('--urban',default='Data/urban/monterrey_centro_v3')
    p.add_argument('--terrain',default='Data/unreal/monterrey_centro_single_v3'); p.add_argument('--output',default='artifacts/geo002_input_audit.json')
    a = p.parse_args()
    city,terrain,urban_dir = ROOT/a.city, ROOT/a.terrain, ROOT/a.urban
    m = json.loads((city/'manifest.json').read_text()); t = json.loads((terrain/'manifest.json').read_text())
    u = json.loads((urban_dir/'urban.json').read_text()); features = json.loads((urban_dir/'buildings.geojson').read_text())['features']
    east,north = t['center_easting_northing_m']
    project = Transformer.from_crs('EPSG:4326','EPSG:32614',always_xy=True)
    delta = 0.
    for feature in features:
        absolute = shapely.transform(shape(feature['geometry']),project.transform,interleaved=False)
        local = shapely.transform(absolute,lambda xy:xy-[east,north])
        stored = shapely.union_all(footprint_parts(feature))
        delta = max(delta,local.hausdorff_distance(stored))
    if delta>.001: raise ValueError('WGS84/UTM/local building positions differ')
    inv = Transformer.from_crs('EPSG:32614','EPSG:4326',always_xy=True)
    ll = [inv.transform(east+t['extent_m']*v[0],north+t['extent_m']*v[1]) for v in [(-.5,.5),(.5,.5),(-.5,-.5)]]
    geod = Geod(ellps='WGS84')
    edges = [geod.inv(*ll[0],*ll[i])[2] for i in (1,2)]
    surface = Surface(terrain/t['reference_geotiff'],t)
    network = Network(u,surface,json.loads((city/'config.json').read_text())['roads'])
    roads = network.roads; tree = shapely.STRtree([r['line'] for r in roads])
    crossings = []
    blockers=shapely.union_all([p for feature in features
                              if any(r.get('osm_id')==feature['id'] and r.get('bottom_relative_ground_m')==0 for r in m['mesh_parts'] if r['role']=='building')
                              for p in footprint_parts(feature)])
    exported=trimesh.load_scene(city/m['glb'],process=False)
    parts_by_road={};tri_cache={}
    for part in m['mesh_parts']:
        if part['role'] not in ('carriageway','walkway'):continue
        for road_id in part.get('source_road_ids',[]):parts_by_road.setdefault(road_id,[]).append(part)
    def mesh_height(road,xy):
        heights=[]
        for part in parts_by_road.get(road['id'],[]):
            bounds=np.asarray(part['bounds_enu_m'])
            if np.any(xy<bounds[0,:2]-.001) or np.any(xy>bounds[1,:2]+.001):continue
            name=part['name']
            if name not in tri_cache:
                mat,key=exported.graph[name];mesh=exported.geometry[key]
                vertices=trimesh.transform_points(mesh.vertices,np.linalg.inv(enu_to_gltf())@mat)
                tri_cache[name]=vertices[mesh.faces]
            t=tri_cache[name];e0,e1=t[:,1]-t[:,0],t[:,2]-t[:,0]
            den=e0[:,0]*e1[:,1]-e1[:,0]*e0[:,1]
            valid=den>1e-10
            if not np.any(valid):continue
            t,e0,e1,den=t[valid],e0[valid],e1[valid],den[valid]
            rel=xy-t[:,0,:2]
            u=(rel[:,0]*e1[:,1]-e1[:,0]*rel[:,1])/den
            v=(e0[:,0]*rel[:,1]-rel[:,0]*e0[:,1])/den
            inside=(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)
            heights.extend((t[:,0,2]+u*e0[:,2]+v*e1[:,2])[inside].tolist())
        return max(heights) if heights else None
    for i,road in enumerate(roads):
        if road['kind']=='surface': continue
        for j in tree.query(road['line'],predicate='intersects'):
            if i==j or ((roads[j]['kind']!='surface') and j<i):continue
            other=roads[j]
            if (road['kind'],road['layer'])==(other['kind'],other['layer']):continue
            if set(road['end_nodes']) & set(other['end_nodes']):continue  # A source-connected transition/portal.
            crossing=road['line'].intersection(other['line'])
            points = [crossing] if crossing.geom_type=='Point' else list(crossing.geoms) if crossing.geom_type=='MultiPoint' else []
            for point in points:
                xy = np.array([[point.x,point.y]])
                za,zb = network.z(xy,[road])[0],network.z(xy,[other])[0]
                gap=abs(za-zb)
                ma,mb=mesh_height(road,xy[0]),mesh_height(other,xy[0])
                crossings.append({'roads':[road['id'],other['id']],'kinds':[road['kind'],other['kind']],
                                  'xy_enu_m':xy[0].tolist(),'estimated_top_surface_separation_m':float(gap),
                                  'potential_solid_overlap':bool(gap<.6),'clearance_below_5m_estimate':bool(gap<5),
                                  'actual_exported_mesh_top_separation_m':abs(ma-mb) if ma is not None and mb is not None else None,
                                  'mesh_surface_heights_m':[ma,mb],
                                  'missing_surface_inside_blocking_building':bool((ma is None or mb is None) and blockers.covers(point))})
    differences = np.abs(surface.data[:-1,:-1].astype(float)-surface.data[:-1,1:]-surface.data[1:,:-1]+surface.data[1:,1:])/4
    result={'status':'coordinate_consistency_passed','building_features_checked':len(features),
            'max_wgs84_vs_local_footprint_disagreement_m':delta,'utm_grid_edge_length_m':t['extent_m'],
            'geodesic_north_and_west_edges_m':edges,'projection_scale_at_center':t['projection_scale_at_center'],
            'independent_survey_accuracy_verified':False,'source_dsm_native_resolution_approx_m':30,
            'max_bilinear_vs_mesh_triangle_height_difference_at_cell_center_m':float(differences.max()),
            'different_grade_crossings_audited':len(crossings),
            'potential_grade_solid_overlaps':sum(c['potential_solid_overlap'] for c in crossings),
            'grade_crossings_below_nominal_5m_clearance':sum(c['clearance_below_5m_estimate'] for c in crossings),
            'exported_mesh_crossings_with_both_surfaces':sum(c['actual_exported_mesh_top_separation_m'] is not None for c in crossings),
            'exported_mesh_crossings_missing_surface':sum(c['actual_exported_mesh_top_separation_m'] is None for c in crossings),
            'missing_crossings_inside_blocking_buildings':sum(c['missing_surface_inside_blocking_building'] for c in crossings),
            'exported_mesh_crossings_potential_solid_overlap':sum(c['actual_exported_mesh_top_separation_m'] is not None and c['actual_exported_mesh_top_separation_m']<.6 for c in crossings),
            'exported_mesh_crossings_below_5m':sum(c['actual_exported_mesh_top_separation_m'] is not None and c['actual_exported_mesh_top_separation_m']<5 for c in crossings),
            'minimum_exported_mesh_top_separation_m':min((c['actual_exported_mesh_top_separation_m'] for c in crossings if c['actual_exported_mesh_top_separation_m'] is not None),default=None),
            'physical_clearances_validated':False,'crossings':crossings,
            'notes':['Crossings use procedural top-surface estimates, not surveyed engineering heights.',
                     'Potential collisions and low clearances remain explicit; no road is moved to hide them.',
                     'Absolute vertical/horizontal accuracy requires independent control points and bare-earth DTM.']}
    out = ROOT/a.output;out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='crossings'},indent=2))


if __name__=='__main__':main()

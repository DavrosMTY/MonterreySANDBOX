"""Independent WORLD-001 QA over actual GLB triangles, source graph and layers.

A passed export audit is not an engine/runtime traversal certificate. Problems in
centerline coverage or geometry are recorded, never converted into route approval.
"""
import argparse
from collections import Counter,defaultdict
import json
from pathlib import Path

import numpy as np
import rasterio
import shapely
from shapely.geometry import LineString,shape
import trimesh

from .geo001 import sha256
from .mesh import enu_to_gltf
from .world import grade_limit


class HeightIndex:
    def __init__(self,triangles):
        self.tri=np.asarray(triangles)
        if not len(self.tri): self.tree=None;return
        e0,e1=self.tri[:,1]-self.tri[:,0],self.tri[:,2]-self.tri[:,0]
        upward=(e0[:,0]*e1[:,1]-e0[:,1]*e1[:,0])>1e-10
        self.tri=self.tri[upward]
        self.tree=shapely.STRtree(shapely.polygons(self.tri[:,:,:2]))

    def heights(self,xy):
        xy=np.asarray(xy).reshape(-1,2);out=np.full(len(xy),-np.inf)
        if self.tree is None:return np.full(len(xy),np.nan)
        # Small search boxes admit float32 boundary error; barycentric check below
        # rejects nearby triangles that do not cover the requested XY.
        p,t=self.tree.query(shapely.box(xy[:,0]-.0002,xy[:,1]-.0002,xy[:,0]+.0002,xy[:,1]+.0002))
        tri=self.tri[t];e0,e1=tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]
        rel=xy[p]-tri[:,0,:2];den=e0[:,0]*e1[:,1]-e0[:,1]*e1[:,0]
        u=(rel[:,0]*e1[:,1]-rel[:,1]*e1[:,0])/den
        v=(e0[:,0]*rel[:,1]-e0[:,1]*rel[:,0])/den
        # Barycentric epsilon is dimensionless: a fixed value can admit an
        # adjacent triangle several millimetres away on a long/thin cap. Express
        # the containment allowance in metres using each opposite-edge altitude.
        tolerance_m=.0001
        valid=(u>=-tolerance_m*np.linalg.norm(e1[:,:2],axis=1)/den)&(v>=-tolerance_m*np.linalg.norm(e0[:,:2],axis=1)/den)&\
              (1-u-v>=-tolerance_m*np.linalg.norm((e1-e0)[:,:2],axis=1)/den)
        z=tri[:,0,2]+u*e0[:,2]+v*e1[:,2]
        np.maximum.at(out,p[valid],z[valid]);out[~np.isfinite(out)]=np.nan
        return out


def audit(city,terrain,urban,output=None):
    root=Path(city);m=json.loads((root/'manifest.json').read_text())
    if m['milestone']!='GEO-003 / WORLD-001':raise ValueError('Not a WORLD-001 model')
    for path,expected in [(Path(urban)/'urban.json',m['input_urban_sha256']),
                          (Path(urban)/'buildings.geojson',m['input_buildings_sha256']),
                          (Path(terrain)/'manifest.json',m['input_terrain_manifest_sha256'])]:
        if sha256(path)!=expected:raise ValueError('World source provenance changed')
    for record in m['correction_layer_files']+m.get('auxiliary_files',[]):
        if sha256(root/record['file'])!=record['sha256']:raise ValueError('Correction or prototype provenance changed')
    s=json.loads((root/'road_semantics.json').read_text());original=json.loads((Path(urban)/'urban.json').read_text())
    if sha256(root/m['glb'])!=m['glb_sha256']:raise ValueError('Changed GLB')
    source_by_id={r['id']:r for r in original['roads']}
    if {r['id'] for r in s['roads']}!=set(source_by_id):raise ValueError('Road IDs changed')
    edges=[{k:v for k,v in e.items() if k not in ('grade','layer','vehicle_candidate')} for e in s['directed_edges']]
    if edges!=original['directed_edges']:raise ValueError('Source graph changed')
    max_xy_error=0.;grades=Counter();endpoints=defaultdict(list);profile_violations=[]
    for r in s['roads']:
        source=np.array(source_by_id[r['id']]['xy_cm'])*[.01,-.01]
        saved=np.array(r['source_centerline_enu_m'])[:,:2]
        max_xy_error=max(max_xy_error,float(np.max(abs(saved-source))))
        p=np.array(r['centerline_enu_m']);dist=np.linalg.norm(np.diff(p[:,:2],axis=0),axis=1)
        actual=float(max(abs(np.diff(p[:,2]))/dist)*100)
        if actual>r['grade_limit_percent']+1e-5:profile_violations.append({'id':r['id'],'grade':actual})
        category=r['tags'].get('highway','unknown');grades[category]=max(grades[category],actual)
        for node,pt in zip(r['end_nodes'],(p[0],p[-1])):endpoints[node].append(pt[2])
    if max_xy_error>1e-6 or profile_violations:raise ValueError('Source planimetry or grade constraint violated')
    continuity=max((max(z)-min(z) for z in endpoints.values()),default=0.)
    if continuity>1e-6:raise ValueError('Disconnected endpoint heights at a shared OSM node')
    scene=trimesh.load_scene(root/m['glb'],process=False);groups=defaultdict(list);terrain_mesh=[]
    triangle_counts=Counter();records={p['name']:p for p in m['mesh_parts']}
    for node in scene.graph.nodes_geometry:
        matrix,key=scene.graph[node];mesh=scene.geometry[key];p=records[node]
        enu=trimesh.transform_points(mesh.vertices,np.linalg.inv(enu_to_gltf())@matrix)
        triangles=enu[mesh.faces];triangle_counts[p['system']]+=len(triangles)
        if p['role'] in ('carriageway','walkway'):groups[p['kind'],p['layer'],p['role']].append(triangles)
        if p['role']=='terrain':terrain_mesh.append((p,enu,triangles))
    indices={k:HeightIndex(np.concatenate(v)) for k,v in groups.items()}
    road_audit=[];readiness=Counter()
    for r in s['roads']:
        p=np.array(r['centerline_enu_m']);index=indices.get((r['kind'],r['layer'],r['role']))
        z=index.heights(p[:,:2]) if index else np.full(len(p),np.nan)
        present=np.isfinite(z);error=np.abs(z-p[:,2]-(.08 if r['role']=='walkway' else 0))
        adjacent=present[:-1]&present[1:];dist=np.linalg.norm(np.diff(p[:,:2],axis=0),axis=1)
        actual_grade=float(max((abs(np.diff(z))[adjacent]/dist[adjacent]*100),default=0))
        reasons=[]
        if not present.all():reasons.append('missing_centerline_surface_or_building_trim')
        if np.any(error[present]>.08):reasons.append('exported_surface_profile_deviation_over_8cm')
        if np.any(abs(np.diff(z))[adjacent] > dist[adjacent]*(r['grade_limit_percent']/100)+.002):reasons.append('exported_centerline_grade_above_limit')
        if r['requires_clearance_review']:reasons.append('nominal_clearance_constraint_deficit')
        status='offline_geometry_candidate' if not reasons else 'requires_refinement'
        readiness[status]+=1
        road_audit.append({'id':r['id'],'vehicle_candidate':r['vehicle_candidate'],'kind':r['kind'],
            'hierarchy':r['hierarchy'],'grade_limit_percent':r['grade_limit_percent'],
            'profile_max_grade_percent':r['max_sampled_grade_percent'],'exported_max_sampled_grade_percent':actual_grade,
            'samples':len(p),'missing_samples':int((~present).sum()),
            'max_surface_vs_profile_error_m':float(max(error[present],default=0)),
            'status':status,'reasons':reasons,'runtime_traversal_validated':False})
    by_id={r['id']:r for r in s['roads']};lines=[LineString(np.array(r['source_centerline_enu_m'])[:,:2]) for r in s['roads']]
    tree=shapely.STRtree(lines);crossings=[]
    rank=lambda r:( (abs(r['layer']) or 1)*(1 if r['kind'] in ('bridge','elevated_inferred') else -1 if r['kind'] in ('tunnel','depressed_inferred') else 0),r['layer'],r['id'])
    for i,r in enumerate(s['roads']):
        if r['kind']=='surface':continue
        for j in tree.query(lines[i],predicate='intersects'):
            other=s['roads'][j]
            if i==j or (other['kind']!='surface' and j<i) or (r['kind'],r['layer'])==(other['kind'],other['layer']) or set(r['end_nodes'])&set(other['end_nodes']):continue
            geom=lines[i].intersection(lines[j]);pts=[geom] if geom.geom_type=='Point' else list(geom.geoms) if geom.geom_type=='MultiPoint' else []
            for pt in pts:
                low,high=sorted((r,other),key=rank);xy=[[pt.x,pt.y]]
                vals=[];sampled_roles=[];alternatives=[]
                for q in (low,high):
                    value=indices[q['kind'],q['layer'],q['role']].heights(xy)[0]
                    sampled=q['role'];alternative=None
                    if not np.isfinite(value) and q['role']=='walkway' and q['kind']=='surface':
                        replacement=indices.get(('surface',q['layer'],'carriageway'))
                        if replacement:
                            replacement_z=replacement.heights(xy)[0]
                            if np.isfinite(replacement_z):
                                alternative=float(replacement_z);sampled='missing_walkway_visible_carriageway_is_not_equivalent_level'
                    vals.append(value);sampled_roles.append(sampled);alternatives.append(alternative)
                gap=float(vals[1]-vals[0]) if np.isfinite(vals).all() else None
                crossings.append({'lower':low['id'],'upper':high['id'],'xy_enu_m':xy[0],
                    'sampled_roles':sampled_roles,
                    'other_visible_carriageway_height_m':alternatives,
                    'exported_top_surface_separation_m':gap,'surface_missing':gap is None,
                    'estimated_under_deck_clearance_m':None if gap is None else gap-(.6 if high['kind'] in ('bridge','elevated_inferred') else .25),
                    'potential_solid_overlap_at_center':gap is not None and gap<.6})
    uncertain_ids={c[k] for c in crossings if c['surface_missing'] for k in ('lower','upper')}
    for road in road_audit:
        if road['id'] in uncertain_ids:
            road['reasons'].append('crossing_counterpart_surface_missing')
            road['status']='requires_refinement'
    readiness=Counter(r['status'] for r in road_audit)
    layers=root/'correction_layers';base_manifest=json.loads((Path(terrain)/'manifest.json').read_text())
    with rasterio.open(Path(terrain)/base_manifest['reference_geotiff']) as src:base=src.read(1);transform=src.transform;crs=src.crs
    with rasterio.open(layers/'elevation_delta_m.tif') as src:
        delta=src.read(1)
        if src.transform!=transform or src.crs!=crs:raise ValueError('Delta georeference changed')
    with rasterio.open(layers/'corrected_DSM.tif') as src:corrected=src.read(1)
    reconstruction_error=float(np.max(abs(base.astype(float)+delta-corrected)))
    if reconstruction_error>1e-4:raise ValueError('Correction layer not reversible within float32 tolerance')
    adjustments=json.loads((layers/'adjustments_utm.geojson').read_text());cut=shape(adjustments['features'][1]['geometry'])
    cut=shapely.transform(cut,lambda xy:xy-np.array(m['center_easting_northing_m']))
    cut_core=cut.buffer(-.001)
    ground=shape(adjustments['features'][2]['geometry']) if len(adjustments['features'])>2 else None
    ground_core=shapely.transform(ground,lambda xy:xy-np.array(m['center_easting_northing_m'])).buffer(-.001) if ground else None
    shapely.prepare(cut);shapely.prepare(cut_core)
    if ground_core is not None:shapely.prepare(ground_core)
    covered_area=0.;covered_core_area=0.;ground_core_area=0.;seam_vertices=defaultdict(list)
    extent=m['extent_m'];half=extent/2;cells=json.loads((root/'config.json').read_text())['cells_per_axis'];step=extent/cells
    for part,xyz,tris in terrain_mesh:
        polys=shapely.polygons(tris[:,:,:2]);mask=shapely.intersects(cut,polys)
        covered_area+=float(np.sum(shapely.area(shapely.intersection(polys[mask],cut))))
        core_mask=shapely.intersects(cut_core,polys)
        covered_core_area+=float(np.sum(shapely.area(shapely.intersection(polys[core_mask],cut_core))))
        if ground_core is not None:
            ground_mask=shapely.intersects(ground_core,polys)
            ground_core_area+=float(np.sum(shapely.area(shapely.intersection(polys[ground_mask],ground_core))))
        for axis in (0,1):
            for boundary in np.arange(-half+step,half,step):
                pts=xyz[abs(xyz[:,axis]-boundary)<.0001]
                if len(pts):seam_vertices[axis,float(boundary)].append({tuple(p) for p in np.round(pts,3)})
    if covered_core_area>1e-5 or ground_core_area>1e-5:
        raise ValueError(f'Terrain remains in excavated mask cores: tunnel={covered_core_area}, roads={ground_core_area} m2')
    # Compare union of incident cell borders on the two sides. Same positions can
    # appear on more than two tile corners; count each observed rounded vertex.
    seam_unmatched=0
    for sets in seam_vertices.values():
        counts=Counter(p for points in sets for p in points)
        seam_unmatched+=sum(n<2 for n in counts.values())
    reasons=Counter(reason for r in road_audit for reason in r['reasons'])
    report={'status':'offline_world_audit_completed','model_sha256':m['glb_sha256'],
        'source_xy_max_change_m':max_xy_error,'source_graph_edges_preserved':len(edges),
        'new_false_grade_connections':0,'shared_endpoint_max_vertical_gap_m':continuity,
        'profile_grade_violations':profile_violations,'max_profile_grade_percent_by_highway':dict(grades),
        'road_readiness_counts':dict(readiness),'road_refinement_reason_counts':dict(reasons),
        'motorized_roads_requiring_refinement':sum(r['vehicle_candidate'] and r['status']=='requires_refinement' for r in road_audit),
        'crossings_checked':len(crossings),'crossings_missing_surface':sum(c['surface_missing'] for c in crossings),
        'crossings_potential_center_solid_overlap':sum(c['potential_solid_overlap_at_center'] for c in crossings),
        'minimum_present_crossing_top_separation_m':min((c['exported_top_surface_separation_m'] for c in crossings if not c['surface_missing']),default=None),
        'crossings_estimated_under_deck_clearance_below_5m':sum(c['estimated_under_deck_clearance_m'] is not None and c['estimated_under_deck_clearance_m']<5 for c in crossings),
        'terrain_correction_reconstruction_error_m':reconstruction_error,'terrain_over_tunnel_mask_area_m2':covered_area,
        'excavation_boundary_interchange_tolerance_m':.001,'terrain_over_tunnel_mask_core_area_m2':covered_core_area,
        'terrain_over_ground_road_replacement_core_area_m2':ground_core_area,
        'terrain_unmatched_seam_vertices_at_mm_precision':seam_unmatched,'terrain_cells':len(terrain_mesh),
        'triangles_by_system':dict(triangle_counts),'triangles_total':sum(triangle_counts.values()),
        'engine_executed':False,'full_world_drivable_certified':False,
        'limits':['Samples test centerline elevations, not continuous wheel/capsule swept volumes or engineering clearance',
                  'No survey, UE collision cooking, navigation, PIE traversal or streaming benchmark executed',
                  'Walkway grade bounds do not imply accessibility; steps remain ramp approximations'],
        'roads':road_audit,'crossings':crossings}
    if output:Path(output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--city',required=True)
    p.add_argument('--terrain',default='Data/unreal/monterrey_centro_single_v3');p.add_argument('--urban',default='Data/urban/monterrey_centro_v3');p.add_argument('--output',required=True)
    a=p.parse_args();r=audit(a.city,a.terrain,a.urban,a.output)
    print(json.dumps({k:v for k,v in r.items() if k not in ('roads','crossings')},indent=2))


if __name__=='__main__':main()

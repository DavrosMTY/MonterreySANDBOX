"""Independent full-model GEO-004 checks, profiles and explicit unresolved structures."""
from collections import Counter,defaultdict
import csv
import json
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString,Point
import trimesh
import rasterio

from pyproj import Transformer
from .geo001 import sha256
from .geo004 import PlanarDTM
from .mesh import Surface,enu_to_gltf
from .qa_world import HeightIndex
from .buildings3d import footprint_parts


def load_model(path):
    path=Path(path);m=json.loads((path/'manifest.json').read_text());s=json.loads((path/'road_semantics.json').read_text())
    if sha256(path/m['glb'])!=m['glb_sha256']or sha256(path/'road_semantics.json')!=m['road_semantics_sha256']:raise ValueError('Model/source hash mismatch')
    scene=trimesh.load_scene(path/m['glb'],process=False);meta={p['name']:p for p in m['mesh_parts']};meshes={};groups=defaultdict(list);terrains=[];numerical=Counter()
    for node in scene.graph.nodes_geometry:
        transform,key=scene.graph[node];g=scene.geometry[key];xyz=trimesh.transform_points(g.vertices,np.linalg.inv(enu_to_gltf())@transform);tri=xyz[g.faces];r=meta[node]
        if not np.isfinite(xyz).all():raise ValueError('Nonfinite geometry')
        meshes[node]=(xyz,g.faces);numerical['triangles']+=len(g.faces);numerical['post_float32_degenerate_triangles']+=int((np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1)<=1e-12).sum())
        if r['role'] in ('carriageway','walkway','sidewalk'):groups[r.get('kind','surface'),r.get('layer',0),r['role']].append(tri)
        if r['role']=='terrain':terrains.append(tri)
    indices={k:HeightIndex(np.concatenate(v))for k,v in groups.items()};terrain_index=HeightIndex(np.concatenate(terrains))
    return m,s,meta,meshes,indices,terrain_index,numerical


def crossing_checks(semantics,indices):
    roads=semantics['roads'];lines=[LineString(np.array(r['source_centerline_enu_m'])[:,:2])for r in roads];tree=shapely.STRtree(lines);result=[]
    rank=lambda r:((abs(r['layer'])or 1)*(1 if r['kind']in ('bridge','elevated_inferred')else -1 if r['kind']in ('tunnel','depressed_inferred')else 0),r['layer'],r['id'])
    for i,r in enumerate(roads):
        if r['kind']=='surface':continue
        for j in tree.query(lines[i],predicate='intersects'):
            q=roads[j]
            if i==j or(q['kind']!='surface'and j<i)or(r['kind'],r['layer'])==(q['kind'],q['layer'])or set(r['end_nodes'])&set(q['end_nodes']):continue
            cut=lines[i].intersection(lines[j]);points=[cut]if cut.geom_type=='Point'else list(cut.geoms)if cut.geom_type=='MultiPoint'else[]
            for point in points:
                low,high=sorted((r,q),key=rank);z=[]
                for road in (low,high):
                    index=indices.get((road['kind'],road['layer'],road['role']));h=index.heights([[point.x,point.y]])[0]if index else np.nan;z.append(float(h)if np.isfinite(h)else None)
                gap=z[1]-z[0]if None not in z else None
                upper_depth=.6 if high['kind']in ('bridge','elevated_inferred')else .25
                # Lower tunnel has a separately modelled ceiling, never equivalent
                # to a surface road merely because another visible road covers XY.
                lower_above=4.8 if low['kind']=='tunnel'and low['role']=='carriageway'else .08
                overlap=gap is not None and gap<upper_depth+lower_above
                result.append({'lower':low['id'],'upper':high['id'],'xy_enu_m':[point.x,point.y],
                    'top_surface_gap_m':gap,'missing_surface':gap is None,'potential_lining_or_deck_overlap':overlap,
                    'geometry_clearance_review':gap is None or overlap,'surveyed_clearance':False})
    return result


def validate(before,after,terrain,output,urban='Data/urban/monterrey_centro_v3'):
    before,after,terrain,out,urban=map(Path,(before,after,terrain,output,urban))
    if out.exists():raise FileExistsError('Preserve earlier validation')
    out.mkdir(parents=True);a=load_model(before);b=load_model(after);old,os,om,og,oi,ot,on=a;new,ns,nm,ng,ni,nt,nn=b
    review=[];to_geo=Transformer.from_crs(32614,4326,always_xy=True)
    def flag(kind,xy,severity,ids,cause):
        east,north=np.array(new['center_easting_northing_m'])+np.asarray(xy);lon,lat=to_geo.transform(east,north)
        review.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'kind':kind,'severity':severity,'position_enu_m':[float(xy[0]),float(xy[1]),float(dtm([xy])[0])],'source_ids':ids,'cause':cause,'survey_accuracy_certified':False}})
    raw=json.loads((urban/'urban.json').read_text());footprints=json.loads((urban/'buildings.geojson').read_text())
    assert sha256(urban/'urban.json')==old['input_urban_sha256']==new['input_urban_sha256']
    assert sha256(urban/'buildings.geojson')==old['input_buildings_sha256']==new['input_buildings_sha256']
    clean=lambda edges:[{k:v for k,v in e.items()if k not in ('grade','layer','vehicle_candidate')}for e in edges]
    assert clean(os['directed_edges'])==clean(ns['directed_edges'])==raw['directed_edges']
    assert [r['id']for r in os['roads']]==[r['id']for r in ns['roads']]
    old_buildings={n:r for n,r in om.items()if r['role']=='building'};new_buildings={n:r for n,r in nm.items()if r['role']=='building'};assert set(old_buildings)==set(new_buildings)
    horizontal_error=0.;height_error=0.;ledger=[]
    tm=json.loads((terrain/'manifest.json').read_text());dtm=PlanarDTM(terrain/tm['reference_geotiff'],tm)
    for name,r in new_buildings.items():
        previous=old_buildings[name]
        for key in ('osm_id','category','height_source','height_estimated','source_tags','footprint_holes','top_relative_ground_m','bottom_relative_ground_m'):assert r[key]==previous[key]
        ox=np.unique(np.round(og[name][0][:,:2],4),axis=0);nx=np.unique(np.round(ng[name][0][:,:2],4),axis=0)
        # Rounding to a fixed decimal can straddle a bin by float32 error. Compare
        # nearest actual XY vertices, rather than requiring decimal-bin identity.
        from scipy.spatial import cKDTree
        error=max(cKDTree(ox).query(nx)[0].max(),cKDTree(nx).query(ox)[0].max());horizontal_error=max(horizontal_error,float(error))
        height_error=max(height_error,abs(r['top_m']-r['base_elevation_m']-previous['top_relative_ground_m']))
        ledger.append({'id':r['osm_id'],'part':name,'old_base_m':previous['base_elevation_m'],'new_base_m':r['base_elevation_m'],
            'base_delta_m':r['base_elevation_m']-previous['base_elevation_m'],'old_bottom_m':previous['bottom_m'],'new_bottom_m':r['bottom_m'],
            'old_top_m':previous['top_m'],'new_top_m':r['top_m'],'relative_height_and_footprint_preserved':True})
    assert horizontal_error<=.0002 and height_error<1e-8
    with(out/'building-correction-ledger.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(ledger[0]));w.writeheader();w.writerows(ledger)
    by_feature={f['id']:f for f in footprints['features']};building_checks=[]
    for name,r in new_buildings.items():
        poly=footprint_parts(by_feature[r['osm_id']])[r['part']]
        dense=shapely.segmentize(poly,2.5);xy=np.vstack([np.asarray(ring.coords)[:-1,:2]for ring in [dense.exterior,*dense.interiors]])
        # Include every native grid sample inside the footprint, so a terrain
        # high point inside a large building is not missed by perimeter-only QA.
        lo=np.ceil(np.array(poly.bounds[:2])/5)*5;hi=np.floor(np.array(poly.bounds[2:])/5)*5
        gx,gy=np.meshgrid(np.arange(lo[0],hi[0]+.01,5),np.arange(lo[1],hi[1]+.01,5));inside=np.column_stack([gx.ravel(),gy.ravel()]);inside=inside[shapely.covers(poly,shapely.points(inside))]
        perimeter_ground=dtm(xy);ground=dtm(np.vstack([xy,inside]));base=r['base_elevation_m'];bottom=r['bottom_m'];elevated=r['bottom_relative_ground_m']>0
        if not elevated and np.ptp(ground)>2:flag('foundation_slope_requires_control',[poly.centroid.x,poly.centroid.y],2,[r['osm_id']],'Natural DTM span across footprint >2m; platform/foundation survey missing, terrain not flattened')
        building_checks.append({'name':name,'osm_id':r['osm_id'],'minimum_height_explicit_or_estimated':elevated,
            'bottom_above_lowest_perimeter_m':float(bottom-perimeter_ground.min()),'ground_footprint_sample_span_m':float(np.ptp(ground)),'native_interior_samples_checked':len(inside),
            'terrain_above_roof_m':float(max(0,ground.max()-r['top_m'])),
            'foundation_requires_review':not elevated and(np.ptp(ground)>2 or bottom-ground.min()>.5),
            'absolute_foundation_accuracy_validated':False})
    roads=[];profiles=[];endpoint_heights=defaultdict(list);old_by_id={r['id']:r for r in os['roads']};max_road_xy_error=0.
    for r in ns['roads']:
        old_r=old_by_id[r['id']];source=np.array(old_r['source_centerline_enu_m']);source_new=np.array(r['source_centerline_enu_m'])
        max_road_xy_error=max(max_road_xy_error,float(np.max(abs(source[:,:2]-source_new[:,:2]))))
        assert old_r['tags']==r['tags']and old_r['end_nodes']==r['end_nodes']and old_r['kind']==r['kind']and old_r['layer']==r['layer']
        p=np.array(old_r['centerline_enu_m']);xy=p[:,:2];s=np.r_[0,np.cumsum(np.linalg.norm(np.diff(xy,axis=0),axis=1))]
        index=ni.get((r['kind'],r['layer'],r['role']));prior=oi.get((r['kind'],r['layer'],r['role']))
        heights=index.heights(xy)if index else np.full(len(xy),np.nan);old_heights=prior.heights(xy)if prior else np.full(len(xy),np.nan)
        expected=dtm(xy)+.12+(.08 if r['role']=='walkway'else 0);present=np.isfinite(heights);at_grade=r['kind']=='surface'
        support_error=float(np.max(abs(heights[present]-expected[present]),initial=0))if at_grade else None
        adjacent=present[:-1]&present[1:];length=np.diff(s)
        grades=abs(np.diff(heights))[adjacent]/np.maximum(length[adjacent],1e-6)*100
        roads.append({'id':r['id'],'kind':r['kind'],'layer':r['layer'],'role':r['role'],'vehicle_candidate':r['vehicle_candidate'],
            'missing_samples_before':int((~np.isfinite(old_heights)).sum()),'missing_samples_after':int((~present).sum()),
            'at_grade_support_error_max_m':support_error,'exported_max_grade_percent':float(np.max(grades,initial=0)),
            'source_control_validation_pending':True,'surveyed_road_elevations':False})
        screening_grade=100 if r['tags'].get('highway')=='steps'else 35 if r['role']=='walkway'else 15
        if len(grades)and grades.max()>screening_grade:
            segment=np.flatnonzero(adjacent)[int(grades.argmax())]
            flag('road_longitudinal_grade_review',(xy[segment]+xy[segment+1])/2,2,[r['id']],f'Exported sampled grade >{screening_grade}% screening; natural source slopes retained, engineering gradient not validated')
        for node,point in zip(r['end_nodes'],(r['centerline_enu_m'][0],r['centerline_enu_m'][-1])):endpoint_heights[node].append(point[2])
        if not present.all():
            missing=int(np.flatnonzero(~present)[0]);flag('missing_source_road_surface',xy[missing],2,[r['id']],'Source footprint clipping/road-role overlap leaves this exported centerline uncovered; no other level substitutes for it')
        for i in range(len(p)):
            profiles.append({'road_id':r['id'],'distance_m':s[i],'east_local_m':xy[i,0],'north_local_m':xy[i,1],
                'geo003_exported_m':None if not np.isfinite(old_heights[i])else old_heights[i],
                'geo004_exported_m':None if not np.isfinite(heights[i])else heights[i],'geo004_dtm_m':expected[i]-.12-(.08 if r['role']=='walkway'else 0),
                'structure_estimated':not at_grade})
    assert max_road_xy_error<1e-6
    continuity=max((max(v)-min(v)for v in endpoint_heights.values()),default=0.)
    assert continuity<1e-6
    with(out/'road-longitudinal-profiles.csv').open('w',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(profiles[0]));w.writeheader();w.writerows(profiles)
    cross_old=crossing_checks(os,oi);cross_new=crossing_checks(ns,ni)
    for c in cross_new:
        if c['geometry_clearance_review']:flag('structural_crossing_requires_review',c['xy_enu_m'],3 if c['potential_lining_or_deck_overlap']else 2,[c['lower'],c['upper']],'A counterpart surface is missing or lining/deck gap is insufficient; no clearance certification')
    pier_checks=[];bridge_terrain_intersections=[]
    for name,r in nm.items():
        if r['role']=='bridge_support':
            xyz,faces=ng[name];xy=np.mean(xyz[:,:2],axis=0);index=ni.get(('bridge',r['layer'],r['bridge_deck_role']))
            deck=index.heights([xy])[0]if index else np.nan;gap=None if not np.isfinite(deck)else float(deck-.6-HeightIndex(xyz[faces]).heights([xy])[0])
            pier_checks.append({'name':name,'estimated':True,'support_to_deck_bottom_gap_m':gap})
            if gap is None or abs(gap)>.25:flag('bridge_support_gap_review',xy,2,r['source_road_ids'],'Estimated support does not meet the sampled deck underside within 25cm')
        if r['system']=='Bridges'and r['role']in ('carriageway','walkway'):
            xyz,faces=ng[name];tri=xyz[faces];up=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0])[:,2]>1e-8;p=tri[up].mean(axis=1);penetration=dtm(p[:,:2])-p[:,2]
            if np.any(penetration>.25):
                i=int(penetration.argmax());bridge_terrain_intersections.append({'name':name,'maximum_terrain_above_deck_m':float(penetration[i])});flag('terrain_above_estimated_bridge_deck',p[i,:2],3,r['source_road_ids'],'Natural DTM is above an estimated deck; requires independent structural elevations, no terrain flattening')
    # Real exported terrain on both sides of every sector boundary, relative to
    # the canonical native grid; portal holes remain explicit missing surfaces.
    seam_errors=[];missing=0
    for axis in (0,1):
        for boundary in np.arange(-750,1000,250):
            along=np.linspace(-999,999,160);xy=np.column_stack([np.full(len(along),boundary),along])if axis==0 else np.column_stack([along,np.full(len(along),boundary)])
            for sign in (-1,1):
                q=xy.copy();q[:,axis]+=sign*.001;z=nt.heights(q);valid=np.isfinite(z);missing+=int((~valid).sum());seam_errors.extend(abs(z[valid]-dtm(q[valid])).tolist())
    max_seam=max(seam_errors,default=0.)
    assert max_seam<.001
    layers={}
    for name in ('terrain_reference','baseline_DSM_on_5m_grid','source_replacement_delta_m','inegi_NAVD88','vertical_operation_delta_m'):
        with rasterio.open(terrain/(name+'.tif'))as ds:layers[name]=ds.read(1).astype(float)
    reverse=float(np.max(abs(layers['baseline_DSM_on_5m_grid']+layers['source_replacement_delta_m']-layers['terrain_reference'])))
    datum_reverse=float(np.max(abs(layers['inegi_NAVD88']+layers['vertical_operation_delta_m']-layers['terrain_reference'])))
    assert max(reverse,datum_reverse)<.0001
    structures_pending=[c for c in cross_new if c['geometry_clearance_review']]
    result={'status':'passed_geometric_invariants_with_pending_source_and_structural_validation',
        'source_graph_edges_preserved':len(ns['directed_edges']),'road_ids_and_tags_preserved':len(roads),
        'buildings_preserved':len(new_buildings),'maximum_building_xy_difference_m':horizontal_error,'maximum_road_source_xy_difference_m':max_road_xy_error,
        'relative_building_height_max_change_m':height_error,'shared_endpoint_profile_gap_m':continuity,
        'terrain_sector_boundary_support_error_max_m':max_seam,'portal_hole_missing_seam_samples':missing,
        'source_replacement_reconstruction_max_m':reverse,'datum_delta_reconstruction_max_m':datum_reverse,
        'at_grade_roads_with_support_error_over_25cm':sum(r['kind']=='surface'and(r['at_grade_support_error_max_m']or 0)>.25 for r in roads),
        'roads_missing_centerline_surface_before':sum(r['missing_samples_before']>0 for r in roads),
        'roads_missing_centerline_surface_after':sum(r['missing_samples_after']>0 for r in roads),
        'crossings_checked_before':len(cross_old),'crossings_checked_after':len(cross_new),
        'crossings_missing_surface_before':sum(c['missing_surface']for c in cross_old),'crossings_missing_surface_after':sum(c['missing_surface']for c in cross_new),
        'crossings_potential_structure_overlap_before':sum(c['potential_lining_or_deck_overlap']for c in cross_old),
        'crossings_potential_structure_overlap_after':sum(c['potential_lining_or_deck_overlap']for c in cross_new),
        'building_foundations_requiring_review':sum(r['foundation_requires_review']for r in building_checks),
        'non_elevated_buildings_floating_over_50cm':sum(not r['minimum_height_explicit_or_estimated']and r['bottom_above_lowest_perimeter_m']>.5 for r in building_checks),
        'buildings_terrain_above_roof_over_25cm':sum(r['terrain_above_roof_m']>.25 for r in building_checks),
        'estimated_bridge_supports_checked':len(pier_checks),'estimated_support_gaps_over_25cm':sum(p['support_to_deck_bottom_gap_m']is None or abs(p['support_to_deck_bottom_gap_m'])>.25 for p in pier_checks),'bridge_parts_terrain_above_deck_over_25cm':len(bridge_terrain_intersections),
        'review_map_points':len(review),'original_source_epv_m':None,'absolute_accuracy_certified':False,'source_year':2007,'unreal_executed':False,'full_world_drivable_certified':False,
        'numerical_geometry_before':dict(on),'numerical_geometry_after':dict(nn),'structural_crossings_requiring_review':structures_pending,
        'geometric_tolerance_note':'25cm cap/support screening, 1mm seam/numeric tolerances; these are NOT source vertical/horizontal accuracy.',
        'source_model_sha256':new['glb_sha256']}
    (out/'review-issues.geojson').write_text(json.dumps({'type':'FeatureCollection','features':review},separators=(',',':'),allow_nan=False)+'\n')
    (out/'bridge-supports.json').write_text(json.dumps(pier_checks,indent=2,allow_nan=False)+'\n')
    (out/'validation.json').write_text(json.dumps(result,indent=2,allow_nan=False,default=lambda x:x.item())+'\n')
    (out/'roads.json').write_text(json.dumps(roads,separators=(',',':'),allow_nan=False)+'\n')
    (out/'buildings.json').write_text(json.dumps(building_checks,default=lambda x:x.item(),separators=(',',':'),allow_nan=False)+'\n')
    (out/'crossings.json').write_text(json.dumps({'before':cross_old,'after':cross_new},indent=2,allow_nan=False)+'\n')
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    chosen=sorted((r for r in roads if r['kind']=='surface'),key=lambda r:old_by_id[r['id']].get('procedural_profile_adjustment_max_m',0),reverse=True)[:4]
    fig,axes=plt.subplots(len(chosen),1,figsize=(10,10))
    for ax,r in zip(axes,chosen):
        p=[p for p in profiles if p['road_id']==r['id']];distance=[v['distance_m']for v in p]
        ax.plot(distance,[v['geo003_exported_m']for v in p],label='GEO-003 exportado');ax.plot(distance,[v['geo004_exported_m']for v in p],label='GEO-004 exportado');ax.plot(distance,[v['geo004_dtm_m']for v in p],label='MDT INEGI transformado',linestyle='--');ax.set_title(r['id']);ax.set_ylabel('EGM2008 (m)');ax.legend(fontsize=7)
    axes[-1].set_xlabel('Distancia longitudinal (m)');fig.suptitle('Perfiles reales de los modelos · no constituyen levantamiento');fig.tight_layout();fig.savefig(out/'longitudinal-comparison.png',dpi=140);plt.close(fig)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('before','after','terrain','output'):p.add_argument('--'+name,required=True)
    a=p.parse_args();r=validate(a.before,a.after,a.terrain,a.output);print(json.dumps(r,indent=2,default=lambda x:x.item()))

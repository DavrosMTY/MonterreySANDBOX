"""GEO-004: natural DTM, independent road platforms/structures and local portal masks.

No joint grade-limit LP or nearest-road terrain warp. At-grade heights sample one
continuous DTM; bridges/tunnels retain distinct, explicitly estimated profiles.
Original GEO-003 and all OSM inputs remain immutable references.
"""
from collections import Counter,defaultdict
import copy
import json
from pathlib import Path
import time

import numpy as np
import shapely
from shapely.geometry import LineString,Point,Polygon,box,mapping
import trimesh

from . import buildings3d,roads3d
from .city import DEFAULT_CONFIG,save_obj
from .geo001 import sha256
from .mesh import Surface,densify_polygon,enu_to_gltf,enu_to_unreal_cm,extrude,terrain_meshes
from .world import cut_terrain_meshes,tunnel_walls


def grid_boundary(poly,spacing=5.):
    """Every source-grid crossing on boundaries, including shared cell borders."""
    def ring(coords):
        points=[]
        for a,b in zip(np.asarray(coords)[:-1,:2],np.asarray(coords)[1:,:2]):
            d=b-a;t=[0.]
            for axis in (0,1):
                if abs(d[axis])<1e-10:continue
                lo,hi=sorted((a[axis],b[axis]));lines=np.arange(np.floor(lo/5)*5,hi+5,5)
                t.extend(((lines-a[axis])/d[axis]).tolist())
            t.extend(np.linspace(0,1,max(2,int(np.ceil(np.linalg.norm(d)/5))+1)).tolist())
            for v in sorted({round(v,12)for v in t if 0<=v<1}):points.append(a+d*v)
        return points
    return Polygon(ring(poly.exterior.coords),[ring(r.coords)for r in poly.interiors])


class TerrainNetwork(roads3d.Network):
    def __init__(self,urban,surface,config):
        super().__init__(urban,surface,config)
        self.profiles={}
        for r in self.roads:
            # Interior DTM-grid samples constrain cap triangulation; not a solved
            # or independently modified road elevation profile.
            p=r['line'].buffer(r['width_m']/2+r['sidewalk_m']+5)
            lo=np.maximum(np.floor(np.array(p.bounds[:2])/5)*5,-surface.half)
            hi=np.minimum(np.ceil(np.array(p.bounds[2:])/5)*5,surface.half)
            x,y=np.meshgrid(np.arange(lo[0],hi[0]+.01,5),np.arange(lo[1],hi[1]+.01,5))
            xy=np.column_stack([x.ravel(),y.ravel()]);xy=xy[shapely.covers(p,shapely.points(xy))]
            self.profiles[r['id']]={'xy':xy}
            r['elevation_source']='INEGI_5m_DTM_EGM2008_platform_offset'if r['kind']=='surface'else'INEGI_5m_DTM_plus_unverified_structural_profile'
            r['vertical_absolute_accuracy_m']=None;r['structure_surveyed']=False


def portal_mask(network):
    shapes=[];details=[]
    for r in network.roads:
        if r['kind']!='tunnel':continue
        length=r['line'].length;s=np.linspace(0,length,max(2,int(np.ceil(length/2.5))+1))
        xy=np.array([r['line'].interpolate(v).coords[0]for v in s]);floor=network.z(xy,[r]);ground=network.surface(xy)
        a,b=r['end_nodes'];distance=np.minimum(network.distances['tunnel'][a]+s,network.distances['tunnel'][b]+length-s)
        exposed=(ground<floor+4.8+.25)&(ground>floor-.25)&(distance<=60)
        for i in range(len(s)-1):
            if exposed[i]or exposed[i+1]:shapes.append(LineString(xy[i:i+2]).buffer(r['width_m']/2+.35,cap_style='flat',quad_segs=2))
        if exposed.any():details.append({'id':r['id'],'source_portal_geometry_estimated':True,'samples_exposed':int(exposed.sum())})
    return shapely.union_all(shapes).intersection(box(-network.surface.half,-network.surface.half,network.surface.half,network.surface.half)),details


def natural_terrain(surface,network,cells):
    """Reuse the numerical triangle cutter solely for explicit estimated portals.

    No broad road replacement and no whole-tunnel excavation. Never changes the
    source raster. Local helper objects avoid changing the GEO-003 behavior.
    """
    from . import world
    # Original cutter derives masks from network.roads. A dedicated small copy
    # of the triangle clipping method keeps that historical implementation intact.
    from .mesh import polygons
    mask=network.portal_cut_geometry
    for name,mesh in terrain_meshes(surface,cells):
        if mask.is_empty:yield name,mesh;continue
        tri=mesh.triangles;polys=shapely.polygons(tri[:,:,:2]);hit=shapely.intersects(polys,mask)
        if not hit.any():yield name,mesh;continue
        vertices=mesh.vertices.tolist();faces=mesh.faces[~hit].tolist()
        for t,p in zip(tri[hit],polys[hit]):
            for remain in polygons(p.difference(mask)):
                for q in shapely.constrained_delaunay_triangles(remain).geoms:
                    xy=np.asarray(q.exterior.coords)[:3,:2]
                    bary=np.linalg.solve(np.vstack([t[:,:2].T,np.ones(3)]),np.vstack([xy.T,np.ones(3)]));z=t[:,2]@bary
                    pts=np.column_stack([xy,z]);ids=np.arange(len(vertices),len(vertices)+3)
                    if np.cross(pts[1]-pts[0],pts[2]-pts[0])[2]<0:ids=ids[::-1]
                    vertices.extend(pts.tolist());faces.append(ids.tolist())
        result=trimesh.Trimesh(vertices,faces,process=True);result.update_faces(result.nondegenerate_faces(height=1e-10));result.remove_unreferenced_vertices()
        result.visual.face_colors=[132,151,113,255];yield name,result


def supports(network,cells):
    lower=[r for r in network.roads if r['kind']not in ('bridge','elevated_inferred')]
    footprints=[r['line'].buffer(r['width_m']/2+1)for r in lower];tree=shapely.STRtree(footprints)
    for r in network.roads:
        if r['kind']!='bridge':continue
        for i,s in enumerate(np.arange(12,r['line'].length-10,30)):
            p=r['line'].interpolate(s);poly=p.buffer(.6,quad_segs=1)
            if len(tree.query(poly,predicate='intersects')):continue
            xy=np.array([[p.x,p.y]]);ground=float(network.surface(xy)[0]);deck=float(network.z(xy,[r])[0])-.6
            if deck-ground<2.5:continue
            cell=np.clip(((xy[0]+network.surface.half)/(2*network.surface.half/cells)).astype(int),0,cells-1).tolist()
            yield f'geo004_support_{r["id"].replace("/","_")}_{i}',extrude(poly,ground-.25,deck,[114,117,115,255],[114,117,115,255]),{
                'role':'bridge_support','kind':'bridge','layer':r['layer'],'cell':cell,'source_road_ids':[r['id']],
                'placement_estimated':True,'structure_surveyed':False,'elevation_estimated':True}


def build(terrain,urban,baseline,output):
    terrain,urban,baseline,out=map(Path,(terrain,urban,baseline,output));start=time.perf_counter()
    if out.exists():raise FileExistsError('Preserve earlier model')
    tm=json.loads((terrain/'manifest.json').read_text());old=json.loads((baseline/'manifest.json').read_text())
    if tm['source_vertical_datum']!='EGM2008'or tm.get('native_product_spacing_m')!=5:raise ValueError('Require the validated INEGI DTM')
    if sha256(terrain/tm['reference_geotiff'])!=tm['reference_geotiff_sha256']:raise ValueError('DTM hash mismatch')
    u=json.loads((urban/'urban.json').read_text());buildings=json.loads((urban/'buildings.geojson').read_text())
    if sha256(urban/'urban.json')!=old['input_urban_sha256']or sha256(urban/'buildings.geojson')!=old['input_buildings_sha256']:raise ValueError('Original OSM provenance changed')
    config=copy.deepcopy(DEFAULT_CONFIG);config['roads']['mesh_edge_spacing_m']=5
    surface=Surface(terrain/tm['reference_geotiff'],tm);network=TerrainNetwork(u,surface,config['roads'])
    network.portal_cut_geometry,portal_details=portal_mask(network)
    meshes={};parts=[];scene=trimesh.Scene();by_cell=defaultdict(list);obstacles=[];cells=config['cells_per_axis'];step=2*surface.half/cells
    def add(name,mesh,record):
        role=record['role'];kind=record.get('kind','')
        system='Landscape'if role=='terrain'else'Buildings'if role=='building'else'Tunnels'if kind=='tunnel'else'Bridges'if kind in ('bridge','elevated_inferred')else'Sidewalks'if role in ('sidewalk','walkway')else'Roads'
        pivot=mesh.bounds.mean(axis=0);cell=record.get('cell',np.clip(((pivot[:2]+surface.half)/step).astype(int),0,cells-1).tolist())
        local=mesh.copy();local.apply_translation(-pivot);matrix=enu_to_gltf();matrix[:3,3]=matrix[:3,:3]@pivot
        scene.add_geometry(local,node_name=name,geom_name=name,transform=matrix)
        record.update(name=name,cell=cell,system=system,vertex_count=len(mesh.vertices),triangle_count=len(mesh.faces),bounds_enu_m=mesh.bounds.tolist(),
            pivot_enu_m=pivot.tolist(),watertight=bool(mesh.is_watertight),winding_consistent=bool(mesh.is_winding_consistent),
            signed_volume_m3=None if role=='terrain'else float(mesh.volume),minimum_triangle_area_m2=float(mesh.area_faces.min()),
            source_data_preserved=True,collision_policy='unverified_static_triangle_mesh',base_accuracy_unknown=True)
        meshes[name]=mesh;parts.append(record);by_cell[system,tuple(cell)].append((name,mesh))
    for name,mesh in natural_terrain(surface,network,cells):add(name,mesh,{'role':'terrain','elevation_source':'INEGI_5m_DTM_NAVD88_to_EGM2008','intentionally_open_surface':True})
    print('GEO004 natural terrain',len(parts),flush=True)
    for f in buildings['features']:
        for name,mesh,record,poly in buildings3d.generate(f,surface,config['buildings'],graybox=True):
            record.update(role='building',base_source='10th_percentile_INEGI_DTM_perimeter_EGM2008_accuracy_unknown')
            add(name,mesh,record)
            if record['bottom_relative_ground_m']==0:obstacles.append(poly)
    print('GEO004 buildings',len(buildings['features']),flush=True)
    for name,mesh,record in roads3d.generate(network,obstacles,cells,densifier=grid_boundary):
        record['terrain_cut_for_tunnel']=record['kind']=='tunnel';record['excavation_policy']='local_estimated_portal_only'
        record['profile_source']='continuous_INEGI_DTM_at_grade_or_separate_estimated_structure'
        add(name,mesh,record)
    print('GEO004 road meshes',len(parts),flush=True)
    for name,mesh,record in tunnel_walls(network,cells):add(name,mesh,record)
    for name,mesh,record in supports(network,cells):add(name,mesh,record)
    out.mkdir(parents=True);glb=out/'monterrey_geo004.glb';scene.export(glb)
    exports=[]
    for (system,(cx,cy)),pieces in sorted(by_cell.items()):
        pivot=np.array([-surface.half+(cx+.5)*step,-surface.half+(cy+.5)*step,0.]);folder=out/'ue_systems'/system;folder.mkdir(parents=True,exist_ok=True)
        p=folder/f'{system}_{cx}_{cy}.obj';save_obj(p,pieces,pivot)
        exports.append({'system':system,'cell':[cx,cy],'file':str(p.relative_to(out)),'sha256':sha256(p),'position_unreal_cm':enu_to_unreal_cm(pivot).tolist(),'source_mesh_names':[n for n,_ in pieces]})
    semantic=network.semantic_graph(u)
    semantic.update(source_dtm_sha256=tm['reference_geotiff_sha256'],original_osm_graph_unchanged=True,
                    all_structure_profiles_estimated=True,source_vertical_datum='EGM2008')
    (out/'road_semantics.json').write_text(json.dumps(semantic,separators=(',',':'),allow_nan=False)+'\n')
    portal_geo=shapely.transform(network.portal_cut_geometry,lambda xy:xy+np.array(tm['center_easting_northing_m']))
    (out/'portal_masks_utm.geojson').write_text(json.dumps({'type':'FeatureCollection','crs':{'type':'name','properties':{'name':'EPSG:32614'}},'features':[
        {'type':'Feature','properties':{'estimated':True,'not_surveyed':True,'policy':'local estimated portal clearances, not entire tunnel corridor'},'geometry':mapping(portal_geo)}]})+'\n')
    report={**{k:old[k]for k in ('center_easting_northing_m','extent_m','source_crs','source_vertical_datum','projection_scale_at_center','grid_convergence_at_center_degrees','gltf_enu_matrix')},
        'schema_version':4,'milestone':'GEO-004','synthetic':False,'glb':glb.name,'glb_sha256':sha256(glb),'mesh_parts':parts,
        'baseline_glb_sha256':old['glb_sha256'],'input_urban_sha256':old['input_urban_sha256'],'input_buildings_sha256':old['input_buildings_sha256'],
        'input_terrain_manifest_sha256':sha256(terrain/'manifest.json'),'road_semantics_sha256':sha256(out/'road_semantics.json'),
        'source_dtm':tm,'ue_system_cells':exports,'terrain_import_mode':'natural_DTM_static_mesh_with_local_estimated_portal_openings',
        'geometric_tolerances_are_not_survey_accuracy':True,'engine_validation':{'editor_executed':False,'windows_build':False},
        'summary':{'building_features':len(buildings['features']),'building_parts':sum(r['role']=='building'for r in parts),
                   'road_segments':len(network.roads),'road_grade_segments':dict(Counter(r['kind']for r in network.roads)),
                   'mesh_parts':len(parts),'triangles':sum(r['triangle_count']for r in parts),'vertices':sum(r['vertex_count']for r in parts),
                   'triangles_by_system':dict(Counter({s:sum(r['triangle_count']for r in parts if r['system']==s)for s in {r['system']for r in parts}})),
                   'portal_excavation_area_m2':network.portal_cut_geometry.area,'ground_warp_vertices':0,
                   'bridge_supports_estimated':sum(r['role']=='bridge_support'for r in parts),'generation_seconds':time.perf_counter()-start},
        'portal_details':portal_details,'limitations':['5 m derived grid, 2007 source; no published EPV; not a current survey',
            'NAVD88 declared; GGM10/EGM2008 operation explicit, GGM05 realization uncertainty retained',
            'OSM relative building heights, widths and all structure geometry remain estimates',
            'Native DTM slopes retained; no joint grade clamp or arbitrary terrain smoothing',
            'Portals, structural approaches and supports require review; no engine collision/drivability certificate']}
    (out/'manifest.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n');(out/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    (out/'DATA_LICENSES.txt').write_text('Fuente: INEGI, MDT LiDAR 5m G14C26A3, datos 2007, edición 2012. Proyecto: reproyección ITRF92 a UTM WGS84; NAVD88 a EGM2008 por rejillas GGM10/NGA. No es transformación avalada por INEGI. EPV no publicada. https://www.inegi.org.mx/inegi/terminos.html\n© OpenStreetMap contributors, ODbL 1.0. GGM10: © INEGI CC BY 4.0 (conversión OSGeo PROJ-data); EGM2008: US NGA dominio público.\n')
    print(json.dumps(report['summary'],indent=2));return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--terrain',required=True);p.add_argument('--urban',default='Data/urban/monterrey_centro_v3');p.add_argument('--baseline',default='Data/city/geo003_world001');p.add_argument('--output',required=True)
    a=p.parse_args();build(a.terrain,a.urban,a.baseline,a.output)

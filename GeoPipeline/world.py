"""WORLD-001: constrained road profiles and reversible, local DSM adaptations.

All corrections are gameplay estimates; this module never relabels DSM as DTM.
The original GEO-001 raster, OSM XY, edge IDs and vertical datum stay unchanged.
"""
from collections import Counter, defaultdict
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
import shapely
from shapely.geometry import Point, Polygon, box, mapping
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
import trimesh

from .geo001 import sha256
from .mesh import Surface, densify_polygon, extrude, polygons, terrain_meshes, enu_to_unreal_cm
from .roads3d import Network

GRADE_LIMITS_PERCENT = {'motorway':8., 'trunk':8., 'primary':10., 'secondary':10.,
                        'tertiary':12., 'residential':12., 'service':12.,
                        'living_street':12., 'default_motor':12., 'walkway':35., 'steps':100.}
PROFILE_SPACING_M = 5.
FADE_M = 6.


def grade_limit(road):
    key=road['tags'].get('highway','').removesuffix('_link')
    if road['role']=='walkway': return GRADE_LIMITS_PERCENT['steps' if key=='steps' else 'walkway']
    return GRADE_LIMITS_PERCENT.get(key,GRADE_LIMITS_PERCENT['default_motor'])


class ProfileNetwork(Network):
    """One sparse LP; shared source endpoint IDs are the SAME elevation variable.

    Hard constraints bound longitudinal grades. Strongly penalized crossing slack
    keeps infeasible nominal separations visible rather than relaxing the grades.
    Weighted L1 displacement keeps the solution close to the previous proxy.
    No graph edge is added by proximity or polygon intersection.
    """
    def __init__(self, baseline):
        self.__dict__.update(baseline.__dict__)
        self.profiles={}
        extra=defaultdict(list)
        crossing_constraints=[]
        for lower,upper,p in self.crossing_points:
            for r in (lower,upper): extra[r['id']].append(r['line'].project(p))
        keys={}; target_lists=defaultdict(list); rows=[];cols=[];vals=[];rhs=[]
        def variable(key,target):
            if key not in keys:keys[key]=len(keys)
            idx=keys[key];target_lists[idx].append(target);return idx
        def constraint(terms,bound):
            row=len(rhs)
            for col,val in terms:rows.append(row);cols.append(col);vals.append(val)
            rhs.append(bound)
        for r in self.roads:
            length=r['line'].length
            # Include all source bends, crossing constraints and uniform samples.
            bends=[0.]; coords=np.asarray(r['line'].coords)
            bends.extend(np.cumsum(np.linalg.norm(np.diff(coords,axis=0),axis=1)).tolist())
            positions=np.unique(np.round([*np.linspace(0,length,max(2,int(np.ceil(length/PROFILE_SPACING_M))+1)),*extra[r['id']],*bends],8))
            positions[0]=0.;positions[-1]=length
            positions=positions[np.r_[True,np.diff(positions)>1e-6]]
            xy=np.array([r['line'].interpolate(float(s)).coords[0] for s in positions])
            target=baseline.z(xy,[r]); ids=[]
            for i,t in enumerate(target):
                key=('node',r['end_nodes'][0]) if i==0 else ('node',r['end_nodes'][1]) if i==len(target)-1 else ('road',r['id'],i)
                ids.append(variable(key,float(t)))
            limit=grade_limit(r)/100
            for a,b,dist in zip(ids[:-1],ids[1:],np.diff(positions)):
                constraint([(a,1.),(b,-1.)],limit*dist)
                constraint([(a,-1.),(b,1.)],limit*dist)
            self.profiles[r['id']]={'s':positions,'xy':xy,'ids':np.array(ids),'target':target}
        n=len(keys)
        # 7.2 m nominal top separation leaves room for 0.6 m deck and transverse
        # profile variation; actual exported geometry is checked independently.
        for lower,upper,p in self.crossing_points:
            pair=[]
            for r in (lower,upper):
                profile=self.profiles[r['id']];s=r['line'].project(p)
                j=int(np.argmin(abs(profile['s']-s)));pair.append(int(profile['ids'][j]))
            slack=2*n+len(crossing_constraints)
            constraint([(pair[0],1.),(pair[1],-1.),(slack,-1.)],-7.2)
            crossing_constraints.append((lower,upper,p))
        targets=np.array([np.median(target_lists[i]) for i in range(n)])
        for i,t in enumerate(targets):
            constraint([(i,1.),(n+i,-1.)],float(t))
            constraint([(i,-1.),(n+i,-1.)],float(-t))
        a=coo_matrix((vals,(rows,cols)),shape=(len(rhs),2*n+len(crossing_constraints))).tocsr()
        result=linprog(np.r_[np.zeros(n),np.ones(n),np.full(len(crossing_constraints),1e6)],A_ub=a,b_ub=rhs,
                       bounds=[(float(t-25),float(t+25)) for t in targets]+[(0,None)]*(n+len(crossing_constraints)),
                       method='highs',options={'time_limit':180.})
        if not result.success:raise ValueError(f'Constrained network profile failed: {result.message}')
        for r in self.roads:
            profile=self.profiles[r['id']];profile['z']=result.x[profile['ids']]
            r.update(elevation_source='WORLD001_joint_grade_constrained_procedural_profile',
                     grade_limit_percent=grade_limit(r),hierarchy=road_hierarchy(r))
        unresolved=[]
        for deficit,(lower,upper,p) in zip(result.x[2*n:],crossing_constraints):
            if deficit>.001:
                unresolved.append({'lower':lower['id'],'upper':upper['id'],'xy_enu_m':[p.x,p.y],
                                   'nominal_separation_deficit_m':float(deficit)})
        for r in self.roads:
            r['requires_clearance_review']=any(r['id'] in (c['lower'],c['upper']) for c in unresolved)
        self.profile_audit={'solver':'scipy.optimize.linprog HiGHS, sparse L1 fit; crossing slack penalty 1e6',
            'status':result.message,'variables':n,'hard_inequalities':len(rhs),
            'max_absolute_profile_change_from_GEO002_proxy_m':float(max(np.max(abs(p['z']-p['target'])) for p in self.profiles.values())),
            'objective_l1_m':float(result.fun),'nominal_crossing_top_separation_m':7.2,
            'unresolved_nominal_clearance_constraints':unresolved,
            'grade_limits_percent':GRADE_LIMITS_PERCENT,'sample_spacing_max_m':PROFILE_SPACING_M,
            'osm_xy_changed':False,'new_graph_connections':0,'surveyed_road_elevations':False,
            'max_constraint_violation_m':float(max(0.,np.max(a@result.x-np.array(rhs))))}
        self.clearance_audit=dict(self.clearance_audit,world001_profile_solver=self.profile_audit)
        self.constraints=defaultdict(dict) # replaced by the complete, solved profile
        print('WORLD001 profiles solved',json.dumps({'variables':n,'crossings':len(crossing_constraints),
            'unresolved':len(unresolved),'max_adjustment_m':self.profile_audit['max_absolute_profile_change_from_GEO002_proxy_m']}),flush=True)

    def z(self,xy,roads):
        xy=np.asarray(xy).reshape(-1,2)
        lines=np.array([r['line'] for r in roads],dtype=object)
        points=shapely.points(xy);nearest=shapely.STRtree(lines).nearest(points)
        distances=shapely.line_locate_point(lines[nearest],points)
        values=np.empty(len(xy))
        for idx in np.unique(nearest):
            select=nearest==idx;p=self.profiles[roads[idx]['id']]
            values[select]=np.interp(distances[select],p['s'],p['z'])
        return values

    def semantic_graph(self,original):
        data=super().semantic_graph(original)
        for r in data['roads']:
            p=self.profiles[r['id']]
            r['centerline_enu_m']=np.column_stack([p['xy'],p['z']]).tolist()
            r['max_sampled_grade_percent']=float(np.max(abs(np.diff(p['z']))/np.diff(p['s']))*100)
            r['profile_is_piecewise_linear']=True
            r['procedural_profile_adjustment_max_m']=float(np.max(abs(p['z']-p['target'])))
        data['profile_solver']=self.profile_audit
        return data


def road_hierarchy(road):
    h=road['tags'].get('highway','').removesuffix('_link')
    return 'pedestrian' if road['role']=='walkway' else 'arterial' if h in ('motorway','trunk','primary') else 'collector' if h in ('secondary','tertiary') else 'local'


def distant_instance(part):
    bounds=np.array(part['bounds_enu_m']);pivot=bounds.mean(axis=0)
    return {'source_id':part['osm_id'],'prototype':'unit_box','category':part['category'],
            'position_unreal_cm':enu_to_unreal_cm(pivot).tolist(),
            'bounds_size_cm':((bounds[1]-bounds[0])*100).tolist(),
            'scale_dimensionless':(bounds[1]-bounds[0]).tolist(),
            'approximation':'axis_aligned_bounds_distant_visual_only'}


class CorrectedSurface(Surface):
    """Additive vertex correction, within ground road corridors only; reversible."""
    def __init__(self,base,network):
        self.__dict__.update(base.__dict__);self.base=base
        self.data=base.data.astype(float).copy()
        rows,cols=np.mgrid[:self.data.shape[0],:self.data.shape[1]]
        xy=np.column_stack([(-self.half+cols*self.spacing).ravel(),(self.half-rows*self.spacing).ravel()])
        roads=[r for r in network.roads if r['kind'] in ('surface','depressed_inferred') and r['role']=='carriageway']
        blend=np.zeros(len(xy));wanted=self.data.ravel().copy()
        if roads:
            lines=np.array([r['line'] for r in roads],dtype=object);points=shapely.points(xy)
            nearest=shapely.STRtree(lines).nearest(points);dist=shapely.distance(points,lines[nearest])
            widths=np.array([r['width_m']/2+2 for r in roads])[nearest]
            blend=1-np.clip((dist-widths)/FADE_M,0,1);blend=blend*blend*(3-2*blend)
            wanted=network.z(xy,roads)-network.config['road_lift_m']
        self.delta=((wanted-self.data.ravel())*blend).reshape(self.data.shape)
        self.data+=self.delta
        changed=np.abs(self.delta)>1e-7
        self.audit={'kind':'procedural_gameplay_correction_not_surveyed_DTM',
            'max_abs_delta_m':float(np.max(abs(self.delta))),'changed_vertices':int(changed.sum()),
            'total_vertices':int(self.delta.size),'changed_vertex_fraction':float(changed.mean()),
            'outside_corridor_changed_vertices':int(np.count_nonzero((blend==0)&(abs(self.delta.ravel())>1e-9))),
            'fade_m':FADE_M,'correction_corridors':len(roads),'source_DEM_modified':False}
        self.corridors=shapely.union_all([r['line'].buffer(r['width_m']/2+2+FADE_M,quad_segs=2) for r in roads])


def tunnel_cut(network):
    """Open-cut equivalent: remove terrain over mapped tunnel corridors including portals.

    Roof lining replaces the removed surface; this is NOT a height-field tunnel.
    Carriageways and separately mapped pedestrian tunnels are included.
    """
    return shapely.union_all([r['line'].buffer(r['width_m']/2+.5,cap_style='square',quad_segs=2)
                              for r in network.roads if r['kind']=='tunnel']).intersection(box(-network.surface.half,-network.surface.half,network.surface.half,network.surface.half))


def cut_terrain_meshes(surface,network,cells):
    cut=tunnel_cut(network);network.tunnel_cut_geometry=cut
    ground=ground_replacement_mask(network)
    network.ground_replacement_geometry=ground
    cut=shapely.union_all([cut,ground])
    for name,mesh in terrain_meshes(surface,cells):
        triangles=mesh.triangles;poly=shapely.polygons(triangles[:,:,:2])
        intersects=shapely.intersects(poly,cut)
        if not np.any(intersects):yield name,mesh;continue
        vertices=mesh.vertices.tolist();faces=mesh.faces[~intersects].tolist()
        for tri,p in zip(triangles[intersects],poly[intersects]):
            remain=p.difference(cut)
            for part in polygons(remain):
                for t in shapely.constrained_delaunay_triangles(part).geoms:
                    xy=np.array(t.exterior.coords)[:3,:2]
                    # Interpolate ORIGINAL triangle plane so cuts do not alter its
                    # elevation and adjacent triangles/tiles share exact edge Z.
                    bary=np.linalg.solve(np.vstack([tri[:,:2].T,np.ones(3)]),np.vstack([xy.T,np.ones(3)]))
                    z=tri[:,2]@bary
                    pts=np.column_stack([xy,z]);ids=np.arange(len(vertices),len(vertices)+3)
                    if np.cross(pts[1]-pts[0],pts[2]-pts[0])[2]<0:ids=ids[::-1]
                    vertices.extend(pts.tolist());faces.append(ids.tolist())
        new=trimesh.Trimesh(vertices,faces,process=True)
        new.update_faces(new.nondegenerate_faces(height=1e-10))
        new.remove_unreferenced_vertices();new.visual.face_colors=[132,151,113,255]
        if np.min(new.area_faces)<=1e-12:raise ValueError('Degenerate terrain excavation triangle')
        yield name,new


def ground_replacement_mask(network):
    """Remove terrain beneath the actual at-grade road/sidewalk footprint.

    The watertight road slab supplies the collision surface. This prevents the
    coarser 4 m terrain triangles protruding through a 5 m road profile.
    """
    bounds=box(-network.surface.half,-network.surface.half,network.surface.half,network.surface.half)
    shapes=[]
    for r in network.roads:
        if r['kind'] not in ('surface','depressed_inferred'):continue
        outer=r['line'].buffer(r['width_m']/2,cap_style='round',quad_segs=2)
        if r['sidewalk_m']:
            if r['sidewalk_sides'] in ('left','right'):
                sign=1 if r['sidewalk_sides']=='left' else -1
                outer=outer.union(r['line'].offset_curve(sign*(r['width_m']/2+r['sidewalk_m']/2)).buffer(r['sidewalk_m']/2,cap_style='flat',quad_segs=2))
            else:outer=r['line'].buffer(r['width_m']/2+r['sidewalk_m'],cap_style='round',quad_segs=2)
        shapes.append(outer)
    obstacle=getattr(network,'ground_obstacle',Polygon()).buffer(network.config['building_clearance_m'])
    # Match derived road polygon snap, inset 2 mm to retain terrain under any
    # interchange rounding sliver. The narrow overlap is below driving surface.
    return shapely.set_precision(shapely.union_all(shapes).intersection(bounds).difference(obstacle),.001).buffer(-.002,quad_segs=1)


def tunnel_walls(network,cells):
    """Side retaining strips around unioned tunnel floors, open at source portals."""
    roads=[r for r in network.roads if r['kind']=='tunnel']
    half=network.surface.half;step=2*half/cells
    for layer in sorted({r['layer'] for r in roads}):
        selected=[r for r in roads if r['layer']==layer]
        floors=shapely.union_all([r['line'].buffer(r['width_m']/2,cap_style='flat',quad_segs=2) for r in selected])
        walls=floors.buffer(.3,quad_segs=2).difference(floors)
        portals=[]
        for r in selected:
            for node in r['end_nodes']:
                touching=network.incident[node]
                if len(touching)==1 or any(network.roads[i]['kind']!='tunnel' for i in touching):
                    portals.append(Point(network.nodes[node]).buffer(r['width_m']/2+1))
        walls=walls.difference(shapely.union_all(portals))
        for cy in range(cells):
            for cx in range(cells):
                cell=box(-half+cx*step,-half+cy*step,-half+(cx+1)*step,-half+(cy+1)*step)
                for i,p in enumerate(polygons(walls.intersection(cell))):
                    if p.area<.02:continue
                    p=densify_polygon(p,3.)
                    z=lambda xy:network.z(xy,selected)
                    mesh=extrude(p,lambda xy:z(xy)-.25,lambda xy:z(xy)+4.8,[112,111,105,255],[112,111,105,255])
                    name=f'tunnel_walls_{layer}_{cx}_{cy}_{i}'.replace('-','minus')
                    yield name,mesh,{'kind':'tunnel','layer':layer,'role':'tunnel_wall','cell':[cx,cy],
                                    'procedural':True,'terrain_cut_for_tunnel':True,'source_road_ids':[r['id'] for r in selected]}


def finalize_world(out,report,meshes,surface,network):
    """Publish corrected layers and system-separated, collision-tagged cell exports."""
    from .city import save_obj
    out=Path(out);layers=out/'correction_layers';layers.mkdir()
    source=surface.base
    origin=report['center_easting_northing_m'];spacing=surface.spacing
    transform=rasterio.transform.from_origin(origin[0]-surface.half-spacing/2,origin[1]+surface.half+spacing/2,spacing,spacing)
    for name,data in [('elevation_delta_m',surface.delta),('corrected_DSM',surface.data)]:
        with rasterio.open(layers/f'{name}.tif','w',driver='GTiff',width=data.shape[1],height=data.shape[0],count=1,
                           dtype='float32',crs='EPSG:32614',transform=transform,compress='deflate') as dst:
            dst.write(data.astype('float32'),1);dst.update_tags(vertical_datum=report['source_vertical_datum'],procedural='true')
    cut=network.tunnel_cut_geometry
    geo={'type':'FeatureCollection','name':'WORLD001_local_adjustments','crs':{'type':'name','properties':{'name':'EPSG:32614'}},'features':[]}
    for kind,geom in [('road_correction_corridor',surface.corridors),('tunnel_open_cut_mask',cut),
                      ('ground_road_surface_replacement_mask',network.ground_replacement_geometry)]:
        geom=shapely.transform(geom,lambda xy:xy+origin)
        geo['features'].append({'type':'Feature','properties':{'kind':kind,'procedural':True,'not_surveyed':True},'geometry':mapping(geom)})
    (layers/'adjustments_utm.geojson').write_text(json.dumps(geo)+'\n')
    (layers/'audit.json').write_text(json.dumps(surface.audit,indent=2)+'\n')
    records={p['name']:p for p in report['mesh_parts']}
    systems=defaultdict(list)
    for name,mesh in meshes.items():
        p=records[name];role=p['role'];kind=p.get('kind','')
        system='Landscape' if role=='terrain' else 'Buildings' if role=='building' else 'Tunnels' if kind=='tunnel' else 'Bridges' if kind in ('bridge','elevated_inferred') else 'Sidewalks' if role in ('sidewalk','walkway') else 'Roads'
        p.update(system=system,collision_policy='complex_static_triangle_mesh',nanite_candidate=system in ('Buildings','Bridges'),
                 source_data_preserved=True)
        systems[system,tuple(p['cell'])].append((name,mesh))
    cells=json.loads((out/'config.json').read_text())['cells_per_axis']
    exports=[];step=report['extent_m']/cells
    for (system,(cx,cy)),pieces in sorted(systems.items()):
        pivot=np.array([-surface.half+(cx+.5)*step,-surface.half+(cy+.5)*step,0.])
        folder=out/'ue_systems'/system;folder.mkdir(parents=True,exist_ok=True)
        path=folder/f'{system}_{cx}_{cy}.obj';save_obj(path,pieces,pivot)
        ue=enu_to_unreal_cm(np.vstack([mesh.bounds for _,mesh in pieces])-pivot)
        exports.append({'name':path.stem,'system':system,'cell':[cx,cy],'file':str(path.relative_to(out)),
            'sha256':sha256(path),'material_file':str(path.with_suffix('.mtl').relative_to(out)),
            'material_sha256':sha256(path.with_suffix('.mtl')),'position_unreal_cm':enu_to_unreal_cm(pivot).tolist(),
            'bounds_local_unreal_cm':[ue.min(axis=0).tolist(),ue.max(axis=0).tolist()],
            'source_mesh_names':[n for n,_ in pieces],'collision_policy':'complex_static_triangle_mesh',
            'nanite_candidate':system in ('Buildings','Bridges'),'spatially_loaded':True,'hlod_layer':system})
    report.update(milestone='GEO-003 / WORLD-001',ue_system_cells=exports,
        terrain_import_mode='excavated_static_mesh_required_do_not_import_uncut_Landscape',
        procedural_terrain_adjustments=surface.audit,profile_solver=network.profile_audit)
    report['summary']['triangles_by_system']=dict(Counter())
    counts=Counter()
    for p in records.values():counts[p['system']]+=p['triangle_count']
    report['summary']['triangles_by_system']=dict(counts)
    report['summary']['local_correction_corridors']=surface.audit['correction_corridors']
    semantic=json.loads((out/'road_semantics.json').read_text())
    motor=[r for r in semantic['roads'] if r['vehicle_candidate']]
    report['summary']['motorized_profile_grade_over_15_percent_count']=sum(r['max_sampled_grade_percent']>15 for r in motor)
    report['summary']['motorized_profile_max_grade_percent']=max((r['max_sampled_grade_percent'] for r in motor),default=0.)
    report['summary']['tunnel_excavation_area_m2']=float(cut.area)
    report['summary']['ground_road_terrain_replacement_area_m2']=float(network.ground_replacement_geometry.area)
    # Distant proxy recipe: all instances share one unit-box prototype. Not used
    # for near collision or authoritative footprints; source IDs remain attached.
    instances=[]
    for p in records.values():
        if p['role']!='building':continue
        instances.append(distant_instance(p))
    proxy=trimesh.creation.box(extents=[1,1,1]);proxy.export(out/'distant_unit_box.glb')
    (out/'instancing_plan.json').write_text(json.dumps({'prototype':'distant_unit_box.glb','prototype_triangles':12,
        'prototype_size_unreal_cm':[100,100,100],
        'instances':instances,'engine_HISM_executed':False,'collision_enabled':False,
        'intended_min_distance_m':600,'not_used_in_authoritative_city_glb':True},indent=2)+'\n')
    report['auxiliary_files']=[{'file':name,'sha256':sha256(out/name)} for name in ('instancing_plan.json','distant_unit_box.glb')]
    report['correction_layer_files']=[{'file':str(p.relative_to(out)),'sha256':sha256(p)} for p in sorted(layers.iterdir())]
    report['limitations']=[v for v in report['limitations'] if not v.startswith('No terrain excavation')]
    report['limitations'] += ['Local additive DSM corrections and road heights are procedural estimates, not a newly acquired DTM',
        'Tunnel terrain is removed over full corridor; lining is an open-cut equivalent, not surveyed portals or retaining structures',
        'Grade limits apply to piecewise-linear centerlines; exported surface checks and engine collision tests have independent scopes',
        'Static mesh terrain is mandatory in WORLD001; importing original Landscape would close the excavated corridors',
        'UE compile, import, collision cooking, runtime traversal and streaming remain unverified without a licensed editor']
    (out/'manifest.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')


def main():
    from .city import build,DEFAULT_CONFIG
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--terrain',default='Data/unreal/monterrey_centro_single_v3')
    p.add_argument('--urban',default='Data/urban/monterrey_centro_v3')
    p.add_argument('--output',required=True)
    a=p.parse_args()
    build(a.terrain,a.urban,a.output,world=True)


if __name__=='__main__':main()

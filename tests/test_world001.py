import copy
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
import shapely
from shapely.geometry import Polygon

from GeoPipeline.mesh import Surface,extrude
from GeoPipeline.roads3d import Network,DEFAULTS
from GeoPipeline.world import ProfileNetwork,CorrectedSurface,cut_terrain_meshes,tunnel_cut,tunnel_walls,grade_limit
from GeoPipeline.qa_world import HeightIndex
from GeoPipeline import buildings3d


class SpikeSurface:
    half=1000.
    def __call__(self,xy):
        p=np.asarray(xy)
        return 500+18*np.exp(-((p[:,0]-25)/3)**2)


def source_network(specs,surface=None):
    """Build source IDs independently from the profile optimizer."""
    nodes={};roads=[];edges=[]
    for i,(coords,tags) in enumerate(specs):
        ends=[]
        for p in (coords[0],coords[-1]):
            key=f'{p[0]}:{p[1]}';nodes[key]={'xy_cm':[p[0]*100,-p[1]*100]};ends.append(key)
        rid=f'road_{i}'
        roads.append({'id':rid,'osm_way_id':i,'tags':tags,'xy_cm':[[x*100,-y*100] for x,y in coords]})
        edges.append({'road_id':rid,'from':ends[0],'to':ends[1],'id':str(i)})
    urban={'graph_nodes':nodes,'roads':roads,'directed_edges':edges}
    return Network(urban,surface or SpikeSurface(),copy.deepcopy(DEFAULTS)),urban


SPECS=[([(-100,0),(100,0)],{'highway':'primary'}),
       ([(100,0),(200,0)],{'highway':'residential'}),
       ([(0,-100),(0,100)],{'highway':'primary','bridge':'yes','layer':'1'}),
       ([(-100,40),(100,40)],{'highway':'secondary','tunnel':'yes','layer':'-1'})]


@pytest.fixture
def solved():
    baseline,urban=source_network(SPECS)
    return ProfileNetwork(baseline),urban


def test_spikes_removed_with_hard_limits_shared_endpoints_and_unchanged_graph(solved):
    net,urban=solved;data=net.semantic_graph(urban)
    for r in data['roads']:
        assert r['max_sampled_grade_percent']<=grade_limit(r)+1e-6
        np.testing.assert_allclose(np.array(r['source_centerline_enu_m'])[:,:2],np.array(urban['roads'][int(r['id'].split('_')[1])]['xy_cm'])*[.01,-.01])
    assert data['roads'][0]['centerline_enu_m'][-1][2]==data['roads'][1]['centerline_enu_m'][0][2]
    assert len(data['directed_edges'])==len(urban['directed_edges'])
    assert data['new_geometric_crossing_connections']==0
    assert not net.profile_audit['unresolved_nominal_clearance_constraints']
    assert data['roads'][0]['procedural_profile_adjustment_max_m']>5


def test_clearances_solved_without_connecting_different_grade_crossings(solved):
    net,_=solved
    for low,high,p in net.crossing_points:
        assert net.z([[p.x,p.y]],[high])[0]-net.z([[p.x,p.y]],[low])[0]>=7.2-1e-6
        assert not set(low['end_nodes'])&set(high['end_nodes'])


def test_impossible_short_grade_connection_is_flagged_and_not_hidden():
    specs=[([(-1,0),(1,0)],{'highway':'primary'}),
           ([(0,-1),(0,1)],{'highway':'primary','bridge':'yes','layer':'1'}),
           ([(0,1),(1,0)],{'highway':'residential'})]
    baseline,_=source_network(specs);net=ProfileNetwork(baseline)
    assert net.profile_audit['unresolved_nominal_clearance_constraints']
    assert any(r['requires_clearance_review'] for r in net.roads)
    for r in net.roads:
        p=net.profiles[r['id']]
        assert max(abs(np.diff(p['z']))/np.diff(p['s']))*100<=grade_limit(r)+1e-5


def raster_surface(tmp_path):
    path=tmp_path/'base.tif';rows,cols=np.mgrid[:65,:65]
    data=(500+8*np.exp(-((cols-35)/2)**2)).astype('float32')
    with rasterio.open(path,'w',driver='GTiff',count=1,width=65,height=65,dtype='float32',crs='EPSG:32614',transform=from_origin(0,0,4,4)) as dst:dst.write(data,1)
    return Surface(path,{'extent_m':256,'sample_spacing_m':4}),path


def test_correction_is_local_and_preserves_base_with_exact_reconstruction(tmp_path):
    base,path=raster_surface(tmp_path);original=path.read_bytes();before=base.data.copy()
    baseline,_=source_network(SPECS[:1],base);net=ProfileNetwork(baseline)
    surface=CorrectedSurface(base,net)
    assert surface.audit['changed_vertices']>0
    assert surface.audit['outside_corridor_changed_vertices']==0
    assert surface.audit['changed_vertex_fraction']<.4
    np.testing.assert_array_equal(base.data,before)
    np.testing.assert_allclose(base.data+surface.delta,surface.data)
    assert path.read_bytes()==original
    assert np.all(surface.delta[0]==0)


def test_tunnel_excavation_removes_actual_terrain_triangles_and_keeps_winding(tmp_path):
    base,_=raster_surface(tmp_path)
    baseline,_=source_network([([(-100,0),(100,0)],{'highway':'secondary','tunnel':'yes','layer':'-1'})],base)
    net=ProfileNetwork(baseline);surface=CorrectedSurface(base,net)
    cut=tunnel_cut(net);meshes=list(cut_terrain_meshes(surface,net,2))
    assert len(meshes)==4
    for _,m in meshes:
        assert np.all(m.face_normals[:,2]>0)
        projected=shapely.polygons(m.triangles[:,:,:2])
        assert sum(shapely.area(shapely.intersection(projected,cut)))<1e-7
    walls=list(tunnel_walls(net,2))
    assert walls
    assert all(m.is_watertight and m.volume>0 for _,m,_ in walls)
    assert all(r['role']=='tunnel_wall' for _,_,r in walls)


def test_graybox_keeps_courtyard_and_reduces_facade_geometry():
    class Flat:
        def __call__(self,xy):return np.full(len(xy),500.)
    rings=[[[0,0],[2000,0],[2000,2000],[0,2000],[0,0]],[[500,500],[500,1500],[1500,1500],[1500,500],[500,500]]]
    feature={'id':'way/1','properties':{'world_polygons_cm':[rings],'tags':{'building':'yes','building:levels':'4'}}}
    detailed=list(buildings3d.generate(feature,Flat(),buildings3d.DEFAULTS))[0]
    gray=list(buildings3d.generate(feature,Flat(),buildings3d.DEFAULTS,graybox=True))[0]
    assert len(gray[1].faces)<len(detailed[1].faces)/3
    assert gray[1].is_watertight
    assert gray[2]['footprint_holes']==1
    assert gray[2]['top_m']==detailed[2]['top_m']
    assert np.allclose(gray[1].bounds,detailed[1].bounds)


def test_height_index_reads_export_surface_not_semantic_claim():
    tri=np.array([[[0,0,500],[10,0,501],[0,10,500]]],dtype=float)
    actual=HeightIndex(tri).heights([[1,1],[5,1],[20,20]])
    np.testing.assert_allclose(actual[:2],[500.1,500.5])
    assert np.isnan(actual[-1])


def test_critical_vertex_on_shared_diagonal_remains_closed():
    poly=Polygon([(0,0),(100,0),(100,100),(0,100)])
    points=[(float(v),float(v)) for v in np.linspace(1,99,40)]
    mesh=extrude(poly,499.,lambda xy:500+np.sin(xy[:,0]/10),[1,2,3,255],[1,2,3,255],interior_points=points)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert mesh.volume>0


def test_height_index_tolerance_is_in_metres_not_barycentric_units():
    # Point is 0.4 mm outside this long triangle; dimensionless epsilon 1e-4
    # would accept it and incorrectly prefer the elevated adjacent surface.
    tri=np.array([[[0,0,520],[100,0,520],[0,5,520]],
                  [[-100,-5,500],[100,0,500],[-100,0,500]]],dtype=float)
    h=HeightIndex(tri).heights([[1,-.0004]])[0]
    assert h==pytest.approx(500)


def test_route_selection_respects_direction_and_quarantines_failed_geometry():
    from tools.prepare_world_routes import select_route
    sem={'roads':[{'id':'a'},{'id':'b'},{'id':'bad'}],
         'nodes':{'0':{'xy_enu_m':[0,0]},'1':{'xy_enu_m':[1,0]},'2':{'xy_enu_m':[2,0]}},
         'directed_edges':[{'from':'0','to':'1','road_id':'a','length_m':10},
                           {'from':'1','to':'2','road_id':'bad','length_m':10},
                           {'from':'2','to':'1','road_id':'b','length_m':10}]}
    qa={'roads':[{'id':'a','vehicle_candidate':True,'status':'offline_geometry_candidate'},
                 {'id':'b','vehicle_candidate':True,'status':'offline_geometry_candidate'},
                 {'id':'bad','vehicle_candidate':True,'status':'requires_refinement'}]}
    route=select_route(sem,qa)
    assert [e['road_id'] for e in route['edges']]==['a']
    assert route['end']=='1'
    assert not route['engine_driven']


def test_world_runner_records_unavailable_engine_without_claiming_execution(tmp_path):
    import subprocess,sys
    receipt=tmp_path/'ue.json'
    result=subprocess.run([sys.executable,'tools/run_unreal_geo003.py','--editor',str(tmp_path/'missing.exe'),'--receipt',str(receipt)],capture_output=True,text=True)
    assert result.returncode==2
    report=json.loads(receipt.read_text())
    assert report['status']=='blocked'
    assert report['editor_executed'] is False
    assert report['native_module_compiled'] is False


def test_distant_instance_uses_dimensionless_scale_for_one_metre_prototype():
    from GeoPipeline.world import distant_instance
    record=distant_instance({'osm_id':'way/9','category':'residential','bounds_enu_m':[[10,20,500],[30,50,510]]})
    np.testing.assert_allclose(record['position_unreal_cm'],[2000,-3500,50500])
    np.testing.assert_allclose(np.array(record['scale_dimensionless'])*100,record['bounds_size_cm'])
    assert record['scale_dimensionless']==[20,30,10]

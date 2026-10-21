import io
import json

import numpy as np
import pytest
from shapely.geometry import Point, Polygon
import trimesh

from GeoPipeline import buildings3d
from GeoPipeline.city import DEFAULT_CONFIG, validate_config, save_obj
from GeoPipeline.mesh import densify_polygon, enu_to_gltf, enu_to_unreal_cm, extrude


def test_closed_building_with_courtyard_caps_and_modular_facades():
    poly = Polygon([(0, 0), (20, 0), (20, 10), (0, 10)], [[(4, 3), (4, 7), (8, 7), (8, 3)]])
    mesh = extrude(densify_polygon(poly, 4), 500, 510, [180]*3+[255], [120]*3+[255], 3.2)
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert mesh.volume == pytest.approx((200-16)*10)
    assert mesh.bounds.tolist() == [[0, 0, 500], [20, 10, 510]]
    top_faces = mesh.triangles[np.all(np.isclose(mesh.triangles[:, :, 2], 510), axis=1)]
    # No top triangle spans the courtyard, even though its centroid could lie outside.
    hole = Polygon([(4, 3), (4, 7), (8, 7), (8, 3)])
    assert sum(Polygon(t[:, :2]).intersection(hole).area for t in top_faces) < 1e-9
    assert len(np.unique(mesh.visual.face_colors, axis=0)) == 3  # Wall, glazing, roof.


@pytest.mark.parametrize('height,expected,source', [('15 m', 15, 'osm_height_tag'), (None, 9.6, 'procedural_class_default')])
def test_height_source_and_explicit_estimation(height, expected, source):
    result = buildings3d.heights({'building':'yes', **({'height':height} if height else {})}, buildings3d.DEFAULTS)
    assert result['top_relative_ground_m'] == pytest.approx(expected)
    assert result['height_source'] == source
    assert result['height_estimated'] == (height is None)


def test_levels_config_and_canopy_not_filled_to_ground():
    config = json.loads(json.dumps(buildings3d.DEFAULTS)); config['floor_height_m'] = 3.5
    result = buildings3d.heights({'building':'commercial', 'building:levels':'6', 'building:min_level':'2'}, config)
    assert result['top_relative_ground_m'] == 21
    assert result['bottom_relative_ground_m'] == 7
    assert result['height_estimated']
    canopy = buildings3d.heights({'building':'roof'}, config)
    assert canopy['bottom_relative_ground_m'] == pytest.approx(canopy['top_relative_ground_m']-.35)


@pytest.mark.parametrize('tags,category', [({'building':'house'},'residential'),({'building':'warehouse'},'industrial'),({'building':'yes','shop':'mall'},'commercial'),({'building':'yes'},'unknown')])
def test_classification_does_not_invent_use(tags, category):
    assert buildings3d.classify(tags) == category


def test_profiled_road_slab_is_closed_and_positive():
    poly = densify_polygon(Polygon([(0,0),(50,0),(50,7),(0,7)]), 6)
    z = lambda xy: 500+np.asarray(xy)[:,0]*.1
    mesh = extrude(poly, lambda xy:z(xy)-.4, z, [80]*3+[255], [80]*3+[255])
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert mesh.volume == pytest.approx(50*7*.4, rel=1e-7)


def test_elevated_one_storey_does_not_create_degenerate_float_row():
    mesh = extrude(Polygon([(0,0),(20,0),(20,10),(0,10)]), 500.1+6.4, 500.1+9.6,
                   [180]*3+[255], [120]*3+[255], 3.2)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(200*3.2)


def test_gltf_roundtrip_preserves_metre_axes_dimensions_and_position():
    mesh = extrude(Polygon([(10,20),(30,20),(30,25),(10,25)]), 500, 512, [200]*3+[255], [100]*3+[255])
    scene = trimesh.Scene(); scene.add_geometry(mesh, node_name='osm_123', geom_name='osm_123', transform=enu_to_gltf())
    raw = scene.export(file_type='glb')
    loaded = trimesh.load_scene(io.BytesIO(raw), file_type='glb', process=False)
    np.testing.assert_allclose(loaded.bounds, [[10,500,-25],[30,512,-20]], atol=1e-5)
    assert sum(len(m.faces) for m in loaded.geometry.values()) == len(mesh.faces)


def test_obj_export_unreal_centimetres_pivot_and_winding(tmp_path):
    mesh = extrude(Polygon([(10,20),(30,20),(30,25),(10,25)]), 500, 512, [200]*3+[255], [100]*3+[255])
    pivot = np.array([20,20,0.])
    path = tmp_path/'cell.obj'; save_obj(path, [('building_123', mesh)], pivot)
    loaded = trimesh.load_scene(path, process=False).to_mesh()
    np.testing.assert_allclose(loaded.bounds, [[-1000,-500,50000],[1000,0,51200]])
    # OBJ materials may split vertices; assess solid topology after geometric welding.
    loaded = trimesh.Trimesh(loaded.vertices, loaded.faces, process=True)
    assert loaded.is_watertight and loaded.volume > 0
    assert loaded.volume == pytest.approx(mesh.volume*1e6)
    np.testing.assert_allclose(enu_to_unreal_cm([1,2,3]), [100,-200,300])


def test_invalid_config_and_degenerate_footprint_rejected():
    c = json.loads(json.dumps(DEFAULT_CONFIG)); c['roads']['lane_width_m'] = float('nan')
    with pytest.raises(ValueError): validate_config(c)
    with pytest.raises(ValueError):
        extrude(Polygon([(0,0),(1,0),(2,0)]), 0, 10, [200]*3+[255], [100]*3+[255])


def test_critical_interior_height_vertex_survives_cap_tessellation():
    poly=Polygon([(0,0),(20,0),(20,10),(0,10)])
    def peak(xy):
        xy=np.asarray(xy);z=np.full(len(xy),500.)
        z[np.linalg.norm(xy-[10,5],axis=1)<.001]=506.1
        return z
    mesh=extrude(poly,lambda xy:peak(xy)-.5,peak,[80]*3+[255],[80]*3+[255],interior_points=[[10,5]])
    assert mesh.is_watertight and mesh.is_winding_consistent
    assert mesh.vertices[:,2].max()==pytest.approx(506.1)
    assert any(np.allclose(p,[10,5,506.1]) for p in mesh.vertices)


def test_foundation_skirt_reaches_lowest_perimeter_on_sloping_dsm():
    feature={'id':'way/123','properties':{'tags':{'building':'yes','height':'15'},
              'world_polygons_cm':[[[[0,0],[2000,0],[2000,-1000],[0,-1000],[0,0]]]]}}
    def slope(xy):
        p=np.asarray(xy);return 500+p[:,0]*.1+p[:,1]*.2
    name,mesh,record,poly=list(buildings3d.generate(feature,slope,buildings3d.DEFAULTS))[0]
    assert record['bottom_m'] <= 499.75+1e-8
    assert record['height_estimated'] is False
    assert mesh.is_watertight
    np.testing.assert_allclose(mesh.bounds[:,:2],[[0,0],[20,10]])

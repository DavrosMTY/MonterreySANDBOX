import json
from pathlib import Path

import numpy as np
import pytest

from GeoPipeline.roads3d import DEFAULTS, Network, grade, width
from GeoPipeline.urban import convert


class FlatSurface:
    half = 1000
    def __call__(self, xy): return np.full(len(xy), 500.)


def network(tmp_path, change=None):
    fixture = json.loads((Path(__file__).parent/'fixtures/synthetic_urban.json').read_text())
    if change: change(fixture)
    path = tmp_path/'fixture.json'; path.write_text(json.dumps(fixture))
    urban = convert(path, tmp_path/'urban')
    return Network(urban, FlatSurface(), DEFAULTS), urban


def test_bridge_crossing_does_not_connect_ground_graph_and_midpoint_elevated(tmp_path):
    n, original = network(tmp_path)
    semantic = n.semantic_graph(original)
    assert len(semantic['directed_edges']) == len(original['directed_edges'])
    assert semantic['new_geometric_crossing_connections'] == 0
    bridge = next(r for r in n.roads if r['kind'] == 'bridge')
    mid = np.array(bridge['line'].interpolate(.5, normalized=True).coords)
    assert n.z(mid, [bridge])[0] >= 506.22-1e-8
    ends = np.array([bridge['line'].coords[0],bridge['line'].coords[-1]])
    np.testing.assert_allclose(n.z(ends,[bridge]), [500.12,500.12])
    assert {e['from'] for e in semantic['directed_edges'] if e['grade']=='bridge'} == {'11'}
    assert semantic['lane_graph_generated'] is False


def test_tunnel_profile_is_below_ground_and_distinct(tmp_path):
    def change(data):
        way = next(e for e in data['elements'] if e.get('type')=='way' and e['id']==102)
        way['tags'].pop('bridge'); way['tags'].update(tunnel='yes',layer='-1')
    n, _ = network(tmp_path, change)
    tunnel = next(r for r in n.roads if r['kind']=='tunnel')
    p = np.array(tunnel['line'].interpolate(.5,normalized=True).coords)
    assert n.z(p,[tunnel])[0] <= 494.02+1e-8
    assert grade({'layer':'2'}) == ('elevated_inferred',2)
    assert grade({'tunnel':'building_passage'}) == ('surface',0)


def test_width_is_semantic_estimate_not_individual_lanes():
    w, source = width({'highway':'primary','lanes':'6'},DEFAULTS)
    assert w == pytest.approx(19.6)
    assert source == 'osm_lanes_times_procedural_lane_width'
    assert width({'highway':'primary','width':'11 m'}, DEFAULTS) == (11,'osm_width_tag')
    assert width({'highway':'footway','lanes':'2'},DEFAULTS)[0] == 1.8


def test_ground_surfaces_sidewalks_and_junctions_do_not_fill_buildings(tmp_path):
    from shapely.geometry import box,Polygon
    from shapely import union_all
    from GeoPipeline.roads3d import generate
    n, original = network(tmp_path)
    blocker = box(-10,-10,10,10)
    generated = list(generate(n,[blocker],1))
    assert any(meta['role']=='sidewalk' for name,mesh,meta in generated)
    for name, mesh, meta in generated:
        assert mesh.is_watertight and mesh.volume>0
        if meta['kind']=='surface':
            top = mesh.triangles[mesh.face_normals[:,2]>.99]
            projected = union_all([Polygon(t[:,:2]) for t in top])
            assert projected.intersection(blocker).area < 1e-7
    assert sum(x['building_overlap_removed_m2'] for x in n.geometry_audit)>0
    assert n.semantic_graph(original)['directed_edges']

import json
from pathlib import Path

import pytest

from GeoPipeline.urban import convert, number

FIXTURE = Path(__file__).parent/'fixtures/synthetic_urban.json'


def test_graph_shared_nodes_direction_bridges_and_buildings(tmp_path):
    result = convert(FIXTURE, tmp_path/'urban')
    assert result['synthetic_fixture'] is True
    assert len(result['roads']) == 5
    assert len(result['directed_edges']) == 9
    assert len(result['graph_nodes']) == 7
    bridge = [e for e in result['directed_edges'] if e['road_id'].startswith('way/102/')]
    assert len(bridge) == 1
    assert (bridge[0]['from'], bridge[0]['to']) == ('11', '10')
    # Geometric crossings with no shared OSM node do not create a junction.
    assert not any(e['to'] == '2' or e['from'] == '2' for e in bridge)
    assert result['building_count'] == 1
    assert result['skipped']['building_relations_unresolved'] == 1
    assert all(n['z_cm'] is None for n in result['graph_nodes'].values())
    b = json.loads((tmp_path/'urban/buildings.geojson').read_text())['features'][0]
    assert b['geometry']['type'] == 'Polygon'
    assert b['properties']['height_m'] == 12
    assert b['properties']['height_source'] == 'osm_height_tag'
    assert b['properties']['base_z_cm'] is None
    assert b['properties']['area_m2'] > 2000


def test_clip_to_square_and_origin_in_cm(tmp_path):
    result = convert(FIXTURE, tmp_path/'clip', extent_m=100)
    assert any(k.startswith('clip:') for k in result['graph_nodes'])
    for road in result['roads']:
        assert all(-5000.001 <= coordinate <= 5000.001 for point in road['xy_cm'] for coordinate in point)
    assert result['graph_nodes']['2']['xy_cm'] == [0, 0]


@pytest.mark.parametrize('text', ['12 ft', '12;15', '-5', 'nan', 'inf', 'about 12', '0'])
def test_ambiguous_heights_never_invented(text):
    assert number(text) is None


def test_missing_building_height_stays_unknown_and_missing_nodes_counted(tmp_path):
    data = json.loads(FIXTURE.read_text())
    data['elements'] = [e for e in data['elements'] if not (e['type'] == 'node' and e['id'] == 1)]
    for e in data['elements']:
        if e.get('id') == 200:
            del e['tags']['height']
    source = tmp_path/'fixture.json'; source.write_text(json.dumps(data))
    result = convert(source, tmp_path/'out')
    assert result['skipped']['incomplete_roads'] == 1
    b = json.loads((tmp_path/'out/buildings.geojson').read_text())['features'][0]
    assert b['properties']['height_m'] is None


def test_overpass_error_rejected(tmp_path):
    source = tmp_path/'error.json'; source.write_text('{"remark":"timeout","elements":[]}')
    with pytest.raises(ValueError, match='error'):
        convert(source, tmp_path/'out')


def test_motorway_implied_direction_and_reversible_stays_unresolved(tmp_path):
    data = json.loads(FIXTURE.read_text())
    for e in data['elements']:
        if e['type'] == 'way' and e['id'] == 100:
            e['tags']['highway'] = 'motorway'
        if e['type'] == 'way' and e['id'] == 101:
            e['tags']['oneway'] = 'reversible'
    source = tmp_path/'data.json'; source.write_text(json.dumps(data))
    result = convert(source, tmp_path/'out')
    motorway = [r for r in result['roads'] if r['osm_way_id'] == 100]
    assert all(r['direction_source'] == 'osm_implied_oneway' for r in motorway)
    assert len(result['directed_edges']) == 3  # Two motorway segments and the reverse bridge.
    assert not any(r['direction_resolved'] for r in result['roads'] if r['osm_way_id'] == 101)


def test_relation_courtyard_fragmented_exterior_and_no_duplicate_member(tmp_path):
    # A member building also carries tags; exporting it again would fill the courtyard.
    data = json.loads(FIXTURE.read_text())
    data['elements'] = [e for e in data['elements'] if e['type'] != 'relation']
    data['elements'] += [
        {'type':'node','id':30,'lat':25.6681,'lon':-100.3089},
        {'type':'node','id':31,'lat':25.6681,'lon':-100.3086},
        {'type':'node','id':32,'lat':25.6684,'lon':-100.3086},
        {'type':'node','id':33,'lat':25.6684,'lon':-100.3089},
        {'type':'way','id':201,'nodes':[30,31,32,33,30]},
        {'type':'relation','id':301,'members':[{'type':'way','ref':200,'role':'outer'}, {'type':'way','ref':201,'role':'inner'}],
         'tags':{'type':'multipolygon','building':'yes','height':'15'}}]
    source = tmp_path/'data.json'; source.write_text(json.dumps(data))
    result = convert(source, tmp_path/'out')
    assert result['building_count'] == 1
    feature = json.loads((tmp_path/'out/buildings.geojson').read_text())['features'][0]
    assert feature['id'] == 'relation/301'
    assert len(feature['geometry']['coordinates']) == 2
    assert feature['properties']['height_m'] == 15
    # Now split the outer ring into two separate ways and reverse one fragment.
    for e in data['elements']:
        if e['type']=='way' and e['id']==200: e['nodes']=[20,21,22]
        if e['type']=='relation': e['members'].append({'type':'way','ref':202,'role':'outer'})
    data['elements'].append({'type':'way','id':202,'nodes':[20,23,22]})
    source.write_text(json.dumps(data))
    result = convert(source, tmp_path/'fragments')
    assert result['building_count'] == 1
    b = json.loads((tmp_path/'fragments/buildings.geojson').read_text())['features'][0]
    assert b['properties']['area_m2'] == pytest.approx(feature['properties']['area_m2'])


def test_relation_open_chain_rejected_without_fabricating_building(tmp_path):
    from GeoPipeline.urban import multipolygon
    with pytest.raises(ValueError, match='Open'):
        multipolygon({'tags':{'type':'multipolygon'},'members':[{'type':'way','ref':1,'role':'outer'}]},
                     {1:{'nodes':[1,2,3]}}, {1:(0,0),2:(1,0),3:(1,1)})

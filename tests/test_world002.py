"""Visual inference policies; never classify missing geographic facts as confirmed."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from world002_decor import lane_policy
from world002_visual import recipe


@pytest.mark.parametrize('tags',[{}, {'lanes':'3'}, {'oneway':'yes'}, {'lanes':'2;3','oneway':'yes'},
                                 {'lanes':'4','oneway':'no'}, {'lanes':'1','oneway':'yes'}, {'lanes':'2','oneway':'reversible'}])
def test_unknown_or_ambiguous_lane_allocation_has_no_paint(tags):
    assert lane_policy(tags) is None


def test_only_explicit_lane_count_and_direction_generate_dividers():
    assert lane_policy({'lanes':'3','oneway':'yes'})['dividers']==2
    assert lane_policy({'lanes':'2','oneway':'-1'})['color']=='white'
    assert lane_policy({'lanes':'2','oneway':'no'})['color']=='yellow'


def test_visual_style_is_deterministic_without_mutating_unknown_category():
    r={'name':'building/123','system':'Buildings','category':'unknown','bottom_m':530,'top_m':542}
    before=dict(r);a=recipe(r)
    assert a==recipe(r) and a[0]==5 and a[2:]==[530,12] and r==before
    assert recipe({**r,'name':'building/124'})[1]!=a[1]


def test_corporate_appearance_requires_source_office_tag_and_height():
    r={'name':'office','system':'Buildings','category':'unknown','top_relative_ground_m':35}
    assert recipe(r)[0]==5
    assert recipe({**r,'source_tags':{'building':'office'}})[0]==2
    assert recipe({**r,'source_tags':{'building':'office'},'top_relative_ground_m':8})[0]==5


def test_supplemental_inventory_is_pinned_attributed_and_geographically_bounded():
    root=Path(__file__).resolve().parents[1]/'WebViewer/visual'
    source=root/'osm-street-inventory.json';receipt=json.loads(source.with_suffix('.source.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==receipt['sha256']
    nodes=json.loads(source.read_text())['elements'];assert len(nodes)==200
    assert len({r['id']for r in nodes})==len(nodes)
    for node in nodes:
        assert node['type']=='node' and node['tags']
        assert 25.6578<=node['lat']<=25.6762 and -100.3202<=node['lon']<=-100.2998

from io import BytesIO
import json
from urllib.request import Request

import pytest

from GeoPipeline import acquire
from GeoPipeline.geo001 import sha256


def test_copernicus_tile_uses_floor_for_negative_longitude():
    assert acquire.dem_url(25.667, -100.310).endswith('Copernicus_DSM_COG_10_N25_00_W101_00_DEM.tif')


def test_query_is_bounded_and_includes_required_recursion():
    q = acquire.osm_query(25.667, -100.310, 2000)
    assert 'way["highway"]' in q and 'relation["building"]' in q
    assert '>;out skel qt;' in q
    with pytest.raises(ValueError, match='limited'):
        acquire.osm_query(25.667, -100.310, 6000)


def response(monkeypatch, content):
    class Response(BytesIO):
        headers = {'ETag': 'fixture'}
    monkeypatch.setattr(acquire, 'urlopen', lambda *a, **k: Response(content))


def test_acquisition_checksum_matches_flushed_bytes(monkeypatch, tmp_path):
    content = b'{"elements":[],"osm3s":{"timestamp_osm_base":"fixture"}}'
    response(monkeypatch, content)
    output = tmp_path/'data.json'
    meta = acquire.download(Request('https://example.org/data'), output, {'source': 'OpenStreetMap'}, 1000)
    assert output.read_bytes() == content
    assert meta['sha256'] == sha256(output)
    assert json.loads(output.with_suffix('.json.source.json').read_text())['bytes'] == len(content)


@pytest.mark.parametrize('content,limit', [(b'x'*200, 100), (b'{"remark":"timeout","elements":[]}', 1000)])
def test_failed_acquisition_leaves_no_data_or_partial_file(monkeypatch, tmp_path, content, limit):
    response(monkeypatch, content)
    with pytest.raises(ValueError):
        acquire.download(Request('https://example.org/data'), tmp_path/'data.json', {'source': 'OpenStreetMap'}, limit)
    assert list(tmp_path.iterdir()) == []

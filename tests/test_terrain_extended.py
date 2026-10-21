from argparse import Namespace
import json

import numpy as np
from PIL import Image
import pytest
import rasterio
from rasterio.transform import from_origin
from pyproj import Transformer

from GeoPipeline.geo001 import SIZE, CRS, center_utm, dem_heights, grid, run, sha256
from GeoPipeline.validate import validate


def options(path, **kwargs):
    values = dict(demo=True, dem=None, lat=25.667, lon=-100.310,
                  extent_m=2000., tiles=1, vertical_datum='UNVERIFIED', output=str(path), source_record=None)
    values.update(kwargs)
    return Namespace(**values)


def write_dem(path, data, transform, crs=CRS, nodata=-9999., scale=1., offset=0.):
    with rasterio.open(path, 'w', driver='GTiff', width=data.shape[1], height=data.shape[0],
                       count=1, dtype='float32', crs=crs, transform=transform, nodata=nodata) as dst:
        dst.write(data.astype('float32'), 1)
        dst.scales, dst.offsets = (scale,), (offset,)
        dst.set_band_unit(1, 'm')


@pytest.mark.parametrize('extent', [0, -1, float('nan'), float('inf')])
def test_invalid_extent(extent):
    with pytest.raises(ValueError):
        grid(25.667, -100.310, extent)


@pytest.mark.parametrize('lat,lon', [(float('nan'), -100), (25, float('inf')), (-25, -100), (25, 0)])
def test_invalid_zone(lat, lon):
    with pytest.raises(ValueError):
        center_utm(lat, lon)


def test_planar_dem_pixel_centers_orientation_scale_and_offset(tmp_path):
    left, top, spacing = grid(25.667, -100.310)
    rows, cols = np.mgrid[0:SIZE, 0:SIZE]
    source = 400 + .1*cols + .2*rows
    path = tmp_path/'plane.tif'
    write_dem(path, source, from_origin(left-spacing/2, top+spacing/2, spacing, spacing), scale=2, offset=10)
    heights = dem_heights(path, 25.667, -100.310, 2000)
    np.testing.assert_allclose(heights, source*2+10, atol=1e-4)
    out = tmp_path/'export'
    m = run(options(out, demo=False, dem=str(path), vertical_datum='fixture-local'))
    assert validate(out)['tiles_verified'] == 1
    assert m['source_dem_sha256'] == sha256(path)
    nw, ne, sw, se = m['tiles'][0]['control_points']
    assert nw['unreal_cm'][0] == pytest.approx(-100000)
    assert nw['unreal_cm'][1] == pytest.approx(-100000)
    assert ne['source_height_m'] < se['source_height_m']
    assert sw['source_height_m'] < se['source_height_m']


def test_geographic_dem_reprojection(tmp_path):
    # Real reprojection code path, generated analytic fixture (not real elevations).
    t = from_origin(-100.34, 25.70, .0001, .0001)
    rows, cols = np.mgrid[0:700, 0:700]
    lon, lat = t.c + (cols+.5)*t.a, t.f+(rows+.5)*t.e
    data = 500 + 100*(lon+100.31) + 200*(lat-25.667)
    path = tmp_path/'geographic.tif'
    write_dem(path, data, t, crs='EPSG:4326')
    result = dem_heights(path, 25.667, -100.310, 2000)
    left, top, spacing = grid(25.667, -100.310)
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    lon, lat = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True).transform(left+x*spacing, top-y*spacing)
    expected = 500+100*(lon+100.31)+200*(lat-25.667)
    np.testing.assert_allclose(result, expected, atol=.002)


@pytest.mark.parametrize('missing', [True, False])
def test_nodata_and_missing_coverage_rejected(tmp_path, missing):
    left, top, spacing = grid(25.667, -100.310)
    source = np.full((SIZE, SIZE), 500., dtype='float32')
    if missing:
        source[200:300, 200:300] = -9999
    path = tmp_path/'bad.tif'
    write_dem(path, source, from_origin(left-spacing/2+(0 if missing else 10000), top+spacing/2, spacing, spacing))
    with pytest.raises(ValueError, match='coverage/NoData'):
        dem_heights(path, 25.667, -100.310, 2000)


def test_non_metric_units_rejected(tmp_path):
    path = tmp_path/'feet.tif'
    write_dem(path, np.ones((10, 10)), from_origin(0, 10, 1, 1))
    with rasterio.open(path, 'r+') as dst:
        dst.set_band_unit(1, 'ft')
    with pytest.raises(ValueError, match='units'):
        dem_heights(path, 25.667, -100.310, 2000)


def test_four_tiles_seams_repeatability_and_tamper_detection(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    ma = run(options(a, tiles=2))
    mb = run(options(b, tiles=2))
    assert ma == mb
    result = validate(a)
    assert result['tiles_verified'] == 4
    assert result['shared_borders_verified'] == 4
    for tile in ma['tiles']:
        for k in ['png', 'r16']:
            assert (a/tile[k]).read_bytes() == (b/tile[k]).read_bytes()
    first = a/ma['tiles'][0]['r16']
    content = bytearray(first.read_bytes()); content[0] ^= 1; first.write_bytes(content)
    with pytest.raises(ValueError, match='Checksum'):
        validate(a)


def test_no_overwrite_or_unverified_datum(tmp_path):
    out = tmp_path/'existing'; out.mkdir(); (out/'user.txt').write_text('preserve')
    with pytest.raises(ValueError, match='empty'):
        run(options(out))
    assert (out/'user.txt').read_text() == 'preserve'
    with pytest.raises(ValueError, match='datum'):
        run(options(tmp_path/'bad', demo=False, dem='unused'))


def test_png_raw_roundtrip_and_quantization_bound(tmp_path):
    m = run(options(tmp_path/'out'))
    arr = np.fromfile(tmp_path/'out/terrain_505.r16', dtype='<u2').reshape(SIZE, SIZE)
    assert np.array_equal(arr, np.asarray(Image.open(tmp_path/'out/terrain_505.png')))
    assert m['max_quantization_error_m'] <= m['unreal_z_scale_cm']/25600+1e-9


def test_missing_tile_and_placement_rejected(tmp_path):
    out = tmp_path/'export'; m = run(options(out))
    m['tiles'][0]['actor_location_cm'][0] += 1
    (out/'manifest.json').write_text(json.dumps(m))
    with pytest.raises(ValueError, match='placement'):
        validate(out)


def test_provenance_checksum_rejected(tmp_path):
    left, top, spacing = grid(25.667, -100.310)
    path, record = tmp_path/'dem.tif', tmp_path/'source.json'
    write_dem(path, np.full((SIZE, SIZE), 500), from_origin(left-spacing/2, top+spacing/2, spacing, spacing))
    record.write_text(json.dumps({'sha256': 'wrong'}))
    with pytest.raises(ValueError, match='checksum'):
        run(options(tmp_path/'out', demo=False, dem=str(path), vertical_datum='fixture-local', source_record=str(record)))

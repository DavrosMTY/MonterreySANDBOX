"""Verify exported bytes, elevations, placement, and exact shared tile borders."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

from .geo001 import SIZE, sha256


def validate(directory):
    root = Path(directory).resolve()
    m = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    if m.get('schema_version') != 3:
        raise ValueError('Expected manifest schema 3; regenerate older exports')
    count = m['tiles_per_axis']
    if not 1 <= count <= 8 or len(m['tiles']) != count**2:
        raise ValueError('Missing or extra tiles')
    arrays = {}
    reference = (root/m['reference_geotiff']).resolve()
    if not reference.is_relative_to(root) or sha256(reference) != m['reference_geotiff_sha256']:
        raise ValueError('Reference GeoTIFF checksum mismatch')
    for tile in m['tiles']:
        key = tile['x'], tile['y']
        if key in arrays or not all(isinstance(v, int) and 0 <= v < count for v in key):
            raise ValueError('Duplicate or invalid tile coordinates')
        paths = [(root/tile[name]).resolve() for name in ('png', 'r16')]
        if not all(p.is_relative_to(root) for p in paths):
            raise ValueError('Export path escapes output directory')
        png, raw = paths
        if raw.stat().st_size != SIZE*SIZE*2:
            raise ValueError('R16 byte length mismatch')
        if sha256(raw) != tile['r16_sha256'] or sha256(png) != tile['heightmap_png_sha256']:
            raise ValueError('Checksum mismatch')
        data = np.fromfile(raw, dtype='<u2').reshape(SIZE, SIZE)
        with Image.open(png) as image:
            if image.size != (SIZE, SIZE) or not np.array_equal(data, np.asarray(image)):
                raise ValueError('PNG and R16 differ')
        scale, actor = m['unreal_z_scale_cm'], m['unreal_landscape_actor_z_cm']
        step = m['sample_spacing_m'] * (SIZE-1)*100
        expected_actor = [-m['extent_m']*50 + key[0]*step, -m['extent_m']*50 + key[1]*step, actor]
        if not np.allclose(tile['actor_location_cm'], expected_actor, atol=1e-7, rtol=0):
            raise ValueError('Tile placement mismatch')
        for point, (row, col) in zip(tile['control_points'], [(0, 0), (0, 504), (504, 0), (504, 504)], strict=True):
            decoded = (actor + (int(data[row, col])-32768)*scale/128)/100
            if abs(decoded-point['source_height_m']) > m['max_quantization_error_m']+1e-6:
                raise ValueError('Control-point elevation mismatch')
            if int(data[row, col]) != point['encoded_uint16']:
                raise ValueError('Control-point encoding mismatch')
        arrays[key] = data
    seams = 0
    for (x, y), a in arrays.items():
        if (x+1, y) in arrays:
            if not np.array_equal(a[:, -1], arrays[x+1, y][:, 0]):
                raise ValueError('East/west seam mismatch')
            seams += 1
        if (x, y+1) in arrays:
            if not np.array_equal(a[-1], arrays[x, y+1][0]):
                raise ValueError('North/south seam mismatch')
            seams += 1
    import rasterio
    with rasterio.open(reference) as src:
        expected_size = count*(SIZE-1)+1
        if src.crs.to_epsg() != 32614 or src.shape != (expected_size, expected_size):
            raise ValueError('Reference GeoTIFF CRS/shape mismatch')
        east, north = m['center_easting_northing_m']
        expected_nw = [east-m['extent_m']/2, north+m['extent_m']/2]
        if not np.allclose(src.xy(0, 0), expected_nw, atol=1e-7, rtol=0):
            raise ValueError('Reference GeoTIFF pixel-center georeferencing mismatch')
        if not np.allclose(src.res, [m['sample_spacing_m']]*2, atol=1e-9, rtol=0):
            raise ValueError('Reference GeoTIFF spacing mismatch')
        for (x, y), encoded in arrays.items():
            original = src.read(1, window=((y*504, y*504+SIZE), (x*504, x*504+SIZE)))
            decoded = (encoded.astype('float64')-32768)*m['unreal_z_scale_cm']/12800 + m['unreal_landscape_actor_z_cm']/100
            if not np.isfinite(original).all() or np.max(np.abs(decoded-original)) > m['max_quantization_error_m']+1e-6:
                raise ValueError('Reference GeoTIFF elevations differ from heightmaps')
    return {'tiles_verified': len(arrays), 'shared_borders_verified': seams,
            'synthetic': m['synthetic_demo_not_geographic_truth'],
            'engine_import_verified': False, 'status': 'passed'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory')
    args = parser.parse_args()
    try:
        print(json.dumps(validate(args.directory), indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Validation failed: {exc}\n')


if __name__ == '__main__':
    main()

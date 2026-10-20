"""Metric DEM to UE5 Landscape export. Engine integration is a separate check."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image
from pyproj import Proj, Transformer

SIZE = 505
CRS = 'EPSG:32614'


def center_utm(lat, lon):
    if not (math.isfinite(lat) and math.isfinite(lon) and 0 <= lat <= 84 and -102 <= lon < -96):
        raise ValueError('Expected finite coordinates in northern UTM zone 14 (Monterrey)')
    return Transformer.from_crs('EPSG:4326', CRS, always_xy=True).transform(lon, lat)


def grid(lat, lon, extent_m=2000.0):
    if not math.isfinite(extent_m) or extent_m <= 0:
        raise ValueError('extent_m must be finite and positive')
    east, north = center_utm(lat, lon)
    return east - extent_m / 2, north + extent_m / 2, extent_m / (SIZE - 1)


def synthetic_heights(extent_m=2000.0, size=SIZE):
    """Fictional regression fixture. Never a source of real Monterrey relief."""
    if not math.isfinite(extent_m) or extent_m <= 0:
        raise ValueError('extent_m must be finite and positive')
    y, x = np.mgrid[0:size, 0:size]
    xn = (x - (size - 1)/2) / ((size-1)/2)
    yn = (y - (size - 1)/2) / ((size-1)/2)
    return (545 + 55*np.exp(-((xn-.35)**2/.12 + (yn+.15)**2/.21))
            + 8*np.sin(3*xn)*np.cos(2*yn)).astype('float32')


def dem_heights(path, lat, lon, extent_m, size=SIZE):
    import rasterio
    from rasterio.warp import reproject, Resampling
    from rasterio.transform import from_origin
    left, top, _ = grid(lat, lon, extent_m)
    spacing = extent_m / (size - 1)
    with rasterio.open(path) as src:
        if src.count != 1 or src.crs is None:
            raise ValueError('DEM must have exactly one raster band and a valid CRS')
        if src.units[0] and src.units[0].lower() not in ('m', 'metre', 'meter', 'metres', 'meters'):
            raise ValueError('DEM vertical units must be metres; convert explicitly first')
        heights = np.full((size, size), np.nan, dtype=np.float32)
        # Pixel CENTERS are vertices, including common borders of adjacent tiles.
        reproject(source=rasterio.band(src, 1), destination=heights,
                  src_transform=src.transform, src_crs=src.crs, src_nodata=src.nodata,
                  dst_transform=from_origin(left-spacing/2, top+spacing/2, spacing, spacing),
                  dst_crs=CRS, dst_nodata=np.nan, resampling=Resampling.bilinear)
        heights = heights * src.scales[0] + src.offsets[0]
    if not np.isfinite(heights).all():
        raise ValueError(f'DEM coverage/NoData failure: {int((~np.isfinite(heights)).sum())} samples')
    return heights


def quantize_for_unreal(heights):
    """UE: world_z_cm = actor_z_cm + (uint16 - 32768)/128 * scale_z."""
    if heights.ndim != 2 or min(heights.shape) < 2 or not np.isfinite(heights).all():
        raise ValueError('Need a finite 2D height grid with at least 2x2 vertices')
    hmin, hmax = float(heights.min()), float(heights.max())
    h0 = (hmin + hmax) / 2
    z_scale_cm = max(abs(hmin-h0), abs(hmax-h0), 1.0) * 100 / 256 * 1.10
    values = np.rint(32768 + (heights.astype('float64')-h0)*12800/z_scale_cm)
    if values.min() < 0 or values.max() > 65535:
        raise ValueError('Quantization would clip elevations')
    encoded = values.astype('<u2')
    reconstruction = h0 + (encoded.astype('float64')-32768) * z_scale_cm / 12800
    return encoded, h0, z_scale_cm, float(np.max(np.abs(reconstruction - heights)))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def run(args):
    tiles = getattr(args, 'tiles', 1)
    if not isinstance(tiles, int) or not 1 <= tiles <= 8:
        raise ValueError('tiles must be an integer from 1 to 8 per axis (bounded memory)')
    left, top, _ = grid(args.lat, args.lon, args.extent_m)
    if not args.demo and (not str(args.vertical_datum).strip() or args.vertical_datum.upper() in ('UNVERIFIED', 'UNKNOWN', 'SYNTHETIC')):
        raise ValueError('Declare the source vertical datum; no automatic datum conversion')
    out = Path(args.output)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output directory must be empty; choose a new output path')
    size = tiles * (SIZE - 1) + 1
    heights = (synthetic_heights(args.extent_m, size) if args.demo else
               dem_heights(args.dem, args.lat, args.lon, args.extent_m, size))
    encoded, h0, zscale, error = quantize_for_unreal(heights)
    spacing = args.extent_m / (size - 1)
    e, n = center_utm(args.lat, args.lon)
    source_record = None
    if getattr(args, 'source_record', None):
        source_record = json.loads(Path(args.source_record).read_text(encoding='utf-8'))
        if not args.demo and source_record.get('sha256') != sha256(args.dem):
            raise ValueError('Source provenance checksum differs from DEM')
        if not args.demo and source_record.get('vertical_datum') != args.vertical_datum:
            raise ValueError('Declared vertical datum differs from acquisition provenance')
    factors = Proj(CRS).get_factors(args.lon, args.lat)
    manifest = {
        'schema_version': 3, 'project': 'MonterreyOpenWorld', 'milestone': 'GEO-001.1',
        'synthetic_demo_not_geographic_truth': bool(args.demo),
        'source_dem': None if args.demo else str(Path(args.dem).resolve()),
        'source_dem_sha256': None if args.demo else sha256(args.dem), 'source_record': source_record,
        'source_vertical_datum': 'synthetic' if args.demo else args.vertical_datum,
        'vertical_units': 'metres', 'vertical_datum_conversion_applied': False,
        'crs': CRS, 'center_lat_lon': [args.lat, args.lon],
        'projection_scale_at_center': factors.meridional_scale,
        'grid_convergence_at_center_degrees': factors.meridian_convergence,
        'distance_basis': 'UTM grid metres; no ground-scale correction applied',
        'center_easting_northing_m': [e, n], 'extent_m': args.extent_m,
        'resolution_vertices': [SIZE, SIZE], 'mosaic_resolution_vertices': [size, size],
        'sample_spacing_m': spacing, 'tiles_per_axis': tiles,
        'unreal_x_scale_cm': spacing*100, 'unreal_y_scale_cm': spacing*100,
        'unreal_z_scale_cm': zscale, 'unreal_landscape_actor_z_cm': h0*100,
        'unreal_topology': {'components_per_axis': 4, 'sections_per_component_axis': 2, 'quads_per_section': 63},
        'coordinate_convention': {'x': 'east', 'y': 'south', 'z': 'up', 'units': 'centimetres',
                                  'horizontal_origin': 'project center', 'vertical_origin': 'source datum zero',
                                  'rows': 'north to south; positive Unreal Y', 'flip_rows': False},
        'engine_import_verified': False,
        'height_min_m': float(heights.min()), 'height_max_m': float(heights.max()),
        'max_quantization_error_m': error, 'r16_endianness': 'little', 'tiles': [],
        'warning': 'Resampling does not increase source ground resolution. DSM may include buildings/vegetation. Engine orientation requires control-point validation.'
    }
    out.mkdir(parents=True, exist_ok=True)
    for ty in range(tiles):
        for tx in range(tiles):
            x, y = tx*(SIZE-1), ty*(SIZE-1)
            tile = encoded[y:y+SIZE, x:x+SIZE].copy()
            stem = 'terrain_505' if tiles == 1 else f'terrain_x{tx}_y{ty}'
            png, raw = out/f'{stem}.png', out/f'{stem}.r16'
            Image.fromarray(tile).save(png)
            raw.write_bytes(tile.tobytes(order='C'))
            corners = []
            for label, dx, dy in [('NW', 0, 0), ('NE', 504, 0), ('SW', 0, 504), ('SE', 504, 504)]:
                east, north = left+(x+dx)*spacing, top-(y+dy)*spacing
                corners.append({'corner': label, 'utm_m': [east, north],
                                'source_height_m': float(heights[y+dy, x+dx]),
                                'encoded_uint16': int(tile[dy, dx]),
                                'unreal_cm': [(east-e)*100, (n-north)*100, float(heights[y+dy, x+dx])*100]})
            manifest['tiles'].append({'x': tx, 'y': ty, 'png': png.name, 'r16': raw.name,
                     'heightmap_png_sha256': sha256(png), 'r16_sha256': sha256(raw),
                     'actor_location_cm': [(-args.extent_m/2+x*spacing)*100, (-args.extent_m/2+y*spacing)*100, h0*100],
                     'control_points': corners})
    # A GIS-readable reference carries explicit pixel-center georeferencing.
    import rasterio
    from rasterio.transform import from_origin
    reference = out/'terrain_reference.tif'
    with rasterio.open(reference, 'w', driver='GTiff', width=size, height=size,
                       count=1, dtype='float32', crs=CRS,
                       transform=from_origin(left-spacing/2, top+spacing/2, spacing, spacing),
                       compress='deflate', nodata=np.nan) as dst:
        dst.write(heights.astype('float32'), 1)
        dst.set_band_unit(1, 'm')
        dst.update_tags(VERTICAL_DATUM=manifest['source_vertical_datum'],
                        SYNTHETIC=str(args.demo), AREA_OR_POINT='Point')
    manifest['reference_geotiff'] = reference.name
    manifest['reference_geotiff_sha256'] = sha256(reference)
    if source_record:
        notices = '\n\n'.join(source_record[k] for k in ('derived_notice', 'liability_notice', 'distribution_obligations') if k in source_record)
        if notices:
            (out/'DATA_LICENSES.txt').write_text(notices+'\n\n'+source_record.get('license_url', '')+'\n', encoding='utf-8')
    if tiles == 1:
        for key in ('r16_sha256', 'heightmap_png_sha256'):
            manifest[key] = manifest['tiles'][0][key]
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'output': str(out), 'synthetic': args.demo, 'tiles': tiles**2, 'error_m': error}))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--demo', action='store_true', help='Synthetic fixture, not real Monterrey')
    group.add_argument('--dem', help='Licensed local single-band GeoTIFF in metres')
    parser.add_argument('--lat', type=float, default=25.667)
    parser.add_argument('--lon', type=float, default=-100.310)
    parser.add_argument('--extent-m', type=float, default=2000.)
    parser.add_argument('--tiles', type=int, default=1, help='1..8 tiles per axis, shared quantization')
    parser.add_argument('--vertical-datum', default='UNVERIFIED')
    parser.add_argument('--source-record', help='Acquisition provenance JSON with matching SHA-256')
    parser.add_argument('--output', default='Data/unreal/demo')
    args = parser.parse_args()
    try:
        run(args)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'GEO export failed: {exc}\n')


if __name__ == '__main__':
    main()

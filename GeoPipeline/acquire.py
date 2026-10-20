"""Small, explicit HTTPS acquisitions with provenance; no implicit background download."""
import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import tempfile
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .geo001 import center_utm, grid, sha256, CRS
from pyproj import Transformer
from .sources import COPERNICUS_SOURCE, COPERNICUS_LICENCE_URL, COPERNICUS_DERIVED_NOTICE, COPERNICUS_LIABILITY, COPERNICUS_OBLIGATIONS

AGENT = 'MonterreyOpenWorld-GEO001/0.2 (bounded research acquisition)'


def dem_url(lat, lon):
    center_utm(lat, lon)
    # Copernicus tile names use the southwest degree corner.
    tile = f'Copernicus_DSM_COG_10_N{math.floor(lat):02d}_00_W{abs(math.floor(lon)):03d}_00_DEM'
    return f'https://copernicus-dem-30m.s3.amazonaws.com/{tile}/{tile}.tif'


def osm_query(lat, lon, extent_m):
    if extent_m > 5000:
        raise ValueError('Overpass request limited to 5 km; use regional extracts for larger areas')
    left, top, _ = grid(lat, lon, extent_m)
    transform = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True)
    corners = [transform.transform(x, y) for x in (left, left+extent_m) for y in (top, top-extent_m)]
    south, north = min(p[1] for p in corners), max(p[1] for p in corners)
    west, east = min(p[0] for p in corners), max(p[0] for p in corners)
    bbox = f'{south:.8f},{west:.8f},{north:.8f},{east:.8f}'
    return (f'[out:json][timeout:60];(way["highway"]({bbox});way["building"]({bbox});'
            f'relation["building"]({bbox}););out body;>;out skel qt;')


def download(request, output, metadata, max_bytes):
    output = Path(output)
    record = output.with_suffix(output.suffix+'.source.json')
    if output.exists() or record.exists():
        raise ValueError('Refusing to overwrite existing data or provenance')
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        with urlopen(request, timeout=90) as response, tempfile.NamedTemporaryFile(dir=output.parent, delete=False) as f:
            tmp = Path(f.name)
            total = 0
            while block := response.read(1024*1024):
                total += len(block)
                if total > max_bytes:
                    raise ValueError('Response exceeds bounded download size')
                f.write(block)
            f.flush()
            metadata.update({'url': request.full_url, 'retrieved_at_utc': datetime.now(timezone.utc).isoformat(),
                             'bytes': total, 'etag': response.headers.get('ETag'), 'sha256': sha256(tmp)})
        # HTTP success can still contain an Overpass error document.
        if metadata['source'] == 'OpenStreetMap':
            body = json.loads(tmp.read_text(encoding='utf-8'))
            if 'remark' in body or not isinstance(body.get('elements'), list):
                raise ValueError('Overpass returned an error or malformed response')
            metadata['osm_timestamp'] = body.get('osm3s', {}).get('timestamp_osm_base')
        else:
            import rasterio
            with rasterio.open(tmp) as src:
                if not src.crs or src.count != 1:
                    raise ValueError('Downloaded DEM lacks CRS or has unexpected bands')
                metadata['raster_crs'] = str(src.crs)
                metadata['raster_resolution'] = list(src.res)
        tmp.rename(output)
        record.write_text(json.dumps(metadata, indent=2)+'\n', encoding='utf-8')
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return metadata


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind', choices=['dem', 'osm'])
    p.add_argument('--lat', type=float, default=25.667)
    p.add_argument('--lon', type=float, default=-100.310)
    p.add_argument('--extent-m', type=float, default=2000)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    try:
        if a.kind == 'dem':
            req = Request(dem_url(a.lat, a.lon), headers={'User-Agent': AGENT})
            meta = {'source': COPERNICUS_SOURCE, 'surface_model': 'DSM',
                    'native_resolution_approx_m': 30, 'vertical_datum': 'EGM2008', 'units': 'metres',
                    'license_url': COPERNICUS_LICENCE_URL,
                    'license_full_text_reviewed': True, 'license_evidence': 'docs/sources/legal-evidence.json',
                    'derived_notice': COPERNICUS_DERIVED_NOTICE, 'liability_notice': COPERNICUS_LIABILITY,
                    'distribution_obligations': COPERNICUS_OBLIGATIONS,
                    'catalog': 'https://registry.opendata.aws/copernicus-dem/'}
            result = download(req, a.output, meta, 150*1024*1024)
        else:
            query = osm_query(a.lat, a.lon, a.extent_m)
            req = Request('https://overpass-api.de/api/interpreter',
                          data=urlencode({'data': query}).encode(), headers={'User-Agent': AGENT})
            result = download(req, a.output, {'source': 'OpenStreetMap', 'license': 'ODbL-1.0',
                              'attribution': '© OpenStreetMap contributors',
                              'license_url': 'https://www.openstreetmap.org/copyright', 'query': query}, 40*1024*1024)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as exc:
        p.exit(2, f'Acquisition failed (no synthetic substitution): {exc}\n')


if __name__ == '__main__':
    main()

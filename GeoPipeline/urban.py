"""OSM JSON to clipped road graph and building footprints. No invented geography."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import re

from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Polygon, MultiPolygon, box, mapping
from shapely import transform, line_merge

from .geo001 import CRS, center_utm, grid, sha256


def number(value):
    """Only unambiguous positive metric OSM values; preserve everything else raw."""
    if value is None or not re.fullmatch(r'\s*\d+(?:\.\d+)?\s*(?:m)?\s*', str(value)):
        return None
    result = float(str(value).strip().removesuffix('m').strip())
    return result if math.isfinite(result) and result > 0 else None


def multipolygon(relation, ways, nodes):
    """Join complete OSM member chains; retain courtyards, never repair broken rings."""
    groups = {'outer': [], 'inner': []}
    member_ids = set()
    if relation.get('tags', {}).get('type') != 'multipolygon':
        raise ValueError('Only multipolygon building relations supported')
    for member in relation.get('members', []):
        role = member.get('role') or 'outer'
        if member['type'] != 'way' or role not in groups or member['ref'] in member_ids:
            raise ValueError('Unsupported or duplicate relation member')
        refs = ways.get(member['ref'], {}).get('nodes', [])
        if len(refs) < 2 or any(n not in nodes for n in refs):
            raise ValueError('Missing relation way or nodes')
        groups[role].append([nodes[n] for n in refs])
        member_ids.add(member['ref'])
    rings = {}
    for role, lines in groups.items():
        merged = line_merge(MultiLineString(lines)) if lines else None
        parts = list(merged.geoms) if merged is not None and merged.geom_type == 'MultiLineString' else ([merged] if merged is not None else [])
        if any(not p.is_ring for p in parts):
            raise ValueError('Open or self-intersecting relation ring')
        rings[role] = [Polygon(p.coords) for p in parts]
    if not rings['outer']:
        raise ValueError('Relation has no exterior')
    holes = [[] for _ in rings['outer']]
    for hole in rings['inner']:
        owners = [i for i, outer in enumerate(rings['outer']) if outer.contains(hole)]
        if len(owners) != 1:
            raise ValueError('Hole outside or ambiguous between exteriors')
        holes[owners[0]].append(hole.exterior.coords)
    polygons = [Polygon(outer.exterior.coords, inner) for outer, inner in zip(rings['outer'], holes)]
    result = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
    if not result.is_valid:
        raise ValueError('Invalid relation polygon')
    return result, member_ids


def convert(source, output, lat=25.667, lon=-100.310, extent_m=2000, synthetic_fixture=False):
    data = json.loads(Path(source).read_text(encoding='utf-8'))
    synthetic_fixture = synthetic_fixture or bool(data.get('synthetic_fixture'))
    record = Path(source).with_suffix(Path(source).suffix+'.source.json')
    source_record = json.loads(record.read_text(encoding='utf-8')) if record.exists() else None
    if source_record and source_record.get('sha256') != sha256(source):
        raise ValueError('OSM source provenance checksum mismatch')
    if 'remark' in data or not isinstance(data.get('elements'), list):
        raise ValueError('Expected complete Overpass JSON without error remark')
    out = Path(output)
    if out.exists() and any(out.iterdir()):
        raise ValueError('Urban output must be empty')
    east, north = center_utm(lat, lon)
    left, top, _ = grid(lat, lon, extent_m)
    bounds = box(left, top-extent_m, left+extent_m, top)
    to_utm = Transformer.from_crs('EPSG:4326', CRS, always_xy=True).transform
    to_wgs = Transformer.from_crs(CRS, 'EPSG:4326', always_xy=True).transform
    nodes = {}
    for e in data['elements']:
        if e['type'] == 'node':
            if not (math.isfinite(e['lon']) and math.isfinite(e['lat']) and -180 <= e['lon'] <= 180 and -90 <= e['lat'] <= 90):
                raise ValueError('Invalid OSM node coordinate')
            nodes[e['id']] = to_utm(e['lon'], e['lat'])
    ways = [e for e in data['elements'] if e['type'] == 'way']
    roads = [e for e in ways if 'highway' in e.get('tags', {}) and e['tags']['highway'] not in ('proposed', 'construction')]
    uses = Counter(n for way in roads for n in set(way['nodes']))
    graph_nodes, edges, road_features, buildings = {}, [], [], []
    skipped = Counter()

    def world(xy):
        return [(xy[0]-east)*100, (north-xy[1])*100]

    def endpoint(way_id, xy, references):
        # Real shared OSM nodes define connectivity; crossing lines do not.
        for node_id in (references[0], references[-1]):
            if math.dist(xy, nodes[node_id]) < 1e-7:
                key = str(node_id)
                break
        else:
            key = f'clip:{way_id}:{xy[0]:.6f}:{xy[1]:.6f}'
        graph_nodes[key] = {'xy_cm': world(xy), 'z_cm': None}
        return key

    for way in roads:
        refs, tags = way['nodes'], way['tags']
        if len(refs) < 2 or any(n not in nodes for n in refs):
            skipped['incomplete_roads'] += 1
            continue
        cuts = [0] + [i for i in range(1, len(refs)-1) if uses[refs[i]] > 1] + [len(refs)-1]
        for start, stop in zip(cuts, cuts[1:]):
            segment_refs = refs[start:stop+1]
            clipped = LineString([nodes[n] for n in segment_refs]).intersection(bounds)
            pieces = list(clipped.geoms) if clipped.geom_type == 'MultiLineString' else [clipped]
            for piece in pieces:
                if piece.is_empty or piece.geom_type != 'LineString' or piece.length < .01:
                    continue
                points = list(piece.coords)
                a = endpoint(way['id'], points[0], segment_refs)
                b = endpoint(way['id'], points[-1], segment_refs)
                implied_oneway = tags.get('junction') == 'roundabout' or tags.get('highway') == 'motorway'
                value = tags.get('oneway', 'yes' if implied_oneway else 'no')
                directions = [(a, b)] if value in ('yes', '1', 'true') else ([(b, a)] if value == '-1' else ([(a, b), (b, a)] if value in ('no', '0', 'false') else []))
                road_id = f"way/{way['id']}/{len(road_features)}"
                for u, v in directions:
                    edges.append({'from': u, 'to': v, 'road_id': road_id, 'length_m': piece.length})
                road_features.append({'id': road_id, 'osm_way_id': way['id'], 'xy_cm': [world(p) for p in points],
                                      'length_m': piece.length, 'tags': tags,
                                      'direction_resolved': bool(directions), 'z_cm': None,
                                      'direction_source': 'osm_tag' if 'oneway' in tags else ('osm_implied_oneway' if implied_oneway else 'assumed_bidirectional'),
                                      'width_m_from_tag': number(tags.get('width')),
                                      'lanes_from_tag': number(tags.get('lanes'))})
    def add_building(poly, osm_type, osm_id, tags):
        poly = poly.intersection(bounds)
        if poly.is_empty:
            return
        if poly.geom_type not in ('Polygon', 'MultiPolygon') or poly.area < .01:
            skipped['degenerate_buildings'] += 1
            return
        h, levels = number(tags.get('height')), number(tags.get('building:levels'))
        parts = [poly] if poly.geom_type == 'Polygon' else list(poly.geoms)
        buildings.append({'type': 'Feature', 'id': f'{osm_type}/{osm_id}',
                          'geometry': mapping(transform(poly, to_wgs, interleaved=False)),
                          'properties': {'osm_type': osm_type, 'osm_id': osm_id, 'tags': tags, 'area_m2': poly.area,
                                         'height_m': h, 'height_source': 'osm_height_tag' if h is not None else 'unknown',
                                         'levels': levels, 'base_z_cm': None,
                                         'world_polygons_cm': [[[world(p) for p in ring.coords] for ring in [part.exterior, *part.interiors]] for part in parts]}})

    consumed_members = set()
    by_id = {w['id']: w for w in ways}
    for relation in data['elements']:
        tags = relation.get('tags', {})
        if relation['type'] != 'relation' or 'building' not in tags or tags['building'] == 'no':
            continue
        try:
            poly, members = multipolygon(relation, by_id, nodes)
        except ValueError:
            skipped['building_relations_unresolved'] += 1
            continue
        add_building(poly, 'relation', relation['id'], tags)
        consumed_members.update(members)

    for way in ways:
        tags, refs = way.get('tags', {}), way['nodes']
        if 'building' not in tags or tags['building'] == 'no' or way['id'] in consumed_members:
            continue
        if len(refs) < 4 or refs[0] != refs[-1] or any(n not in nodes for n in refs):
            skipped['incomplete_buildings'] += 1
            continue
        poly = Polygon([nodes[n] for n in refs])
        if not poly.is_valid:
            skipped['invalid_buildings'] += 1
            continue
        add_building(poly, 'way', way['id'], tags)
    result = {'schema_version': 1, 'source_sha256': sha256(source), 'source': 'OpenStreetMap' if not synthetic_fixture else 'synthetic OSM-format test fixture',
              'source_record': source_record, 'source_timestamp_utc': data.get('osm3s', {}).get('timestamp_osm_base'),
              'synthetic_fixture': synthetic_fixture, 'attribution': '© OpenStreetMap contributors' if not synthetic_fixture else 'fictional test data',
              'license': 'ODbL-1.0' if not synthetic_fixture else 'project test fixture',
              'crs': CRS, 'center_easting_northing_m': [east, north], 'extent_m': extent_m,
              'coordinates': 'local centimetres: X east, Y south; Z unknown (not zero)',
              'graph_nodes': graph_nodes, 'directed_edges': edges, 'roads': road_features,
              'building_count': len(buildings), 'skipped': dict(skipped),
              'limitations': ['No ground elevation, road surface, mesh, routing restrictions or lane graph generated',
                              'Bridge/tunnel/layer tags retained; never drape bridges onto a DSM automatically',
                              'Missing/invalid relation rings are counted; no automatic geometry repair']}
    out.mkdir(parents=True, exist_ok=True)
    (out/'urban.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (out/'buildings.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': buildings}, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--osm', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--lat', type=float, default=25.667)
    p.add_argument('--lon', type=float, default=-100.310)
    p.add_argument('--extent-m', type=float, default=2000)
    p.add_argument('--synthetic-fixture', action='store_true')
    a = p.parse_args()
    try:
        r = convert(a.osm, a.output, a.lat, a.lon, a.extent_m, a.synthetic_fixture)
        print(json.dumps({'roads': len(r['roads']), 'buildings': r['building_count'], 'skipped': r['skipped']}))
    except (OSError, ValueError, KeyError) as exc:
        p.exit(2, f'Urban conversion failed: {exc}\n')


if __name__ == '__main__':
    main()

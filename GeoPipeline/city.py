"""GEO-002: build a georeferenced, auditable urban blockout from GEO-001.1 outputs."""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

import numpy as np
import trimesh

from . import buildings3d, roads3d
from .geo001 import sha256
from .mesh import Surface, enu_to_gltf, enu_to_unreal_cm, terrain_meshes
from .validate import validate

DEFAULT_CONFIG = {'buildings': buildings3d.DEFAULTS, 'roads': roads3d.DEFAULTS, 'cells_per_axis': 8}


def validate_config(config):
    if not isinstance(config['cells_per_axis'], int) or config['cells_per_axis'] not in (1, 2, 4, 8):
        raise ValueError('cells_per_axis must be 1, 2, 4, or 8')
    for section in ('buildings', 'roads'):
        def check(value):
            if isinstance(value, dict):
                for x in value.values(): check(x)
            elif isinstance(value, list):
                if any(not 0 <= x <= 255 for x in value): raise ValueError('Invalid color')
            elif not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Configuration dimensions must be finite positive values')
        check(config[section])


def save_obj(path, meshes, pivot):
    """Explicit raw UE coordinates in cm; material colors use standard OBJ/MTL."""
    material_map = {}; palette = []
    with path.open('w', encoding='utf-8') as out:
        out.write('# GEO-002 X=east Y=south Z=up; centimetres; numeric axes must not be converted on import\n')
        out.write(f'mtllib {path.stem}.mtl\n')
        offset = 1
        for name, mesh in meshes:
            out.write(f'o {name}\n')
            points = enu_to_unreal_cm(mesh.vertices-pivot)
            for p in points: out.write('v %.8f %.8f %.8f\n' % tuple(p))
            colors = np.asarray(mesh.visual.face_colors)
            last = None
            for face, color in zip(mesh.faces[:, ::-1], colors):
                key = tuple(int(x) for x in color)
                if key not in material_map:
                    material_map[key] = len(palette); palette.append(key)
                material = material_map[key]
                if material != last:
                    out.write(f'usemtl geo_{material}\n'); last = material
                out.write('f %d %d %d\n' % tuple(face+offset))
            offset += len(mesh.vertices)
    with path.with_suffix('.mtl').open('w', encoding='utf-8') as out:
        for i, rgba in enumerate(palette):
            out.write(f'newmtl geo_{i}\nKd {rgba[0]/255:.6f} {rgba[1]/255:.6f} {rgba[2]/255:.6f}\nKa 0 0 0\nKs 0.05 0.05 0.05\nNs 10\nd 1\n\n')


def build(terrain_dir, urban_dir, output, config=None, world=False):
    start = time.perf_counter()
    config = json.loads(json.dumps(config or DEFAULT_CONFIG)); validate_config(config)
    terrain, urban_dir, out = Path(terrain_dir), Path(urban_dir), Path(output)
    if out.exists() and any(out.iterdir()): raise ValueError('Output must be empty')
    validate(terrain)
    terrain_manifest = json.loads((terrain/'manifest.json').read_text(encoding='utf-8'))
    urban = json.loads((urban_dir/'urban.json').read_text(encoding='utf-8'))
    buildings = json.loads((urban_dir/'buildings.geojson').read_text(encoding='utf-8'))
    if terrain_manifest['center_easting_northing_m'] != urban['center_easting_northing_m'] or terrain_manifest['extent_m'] != urban['extent_m']:
        raise ValueError('Terrain and urban origins or extents differ')
    if terrain_manifest['synthetic_demo_not_geographic_truth'] != urban['synthetic_fixture']:
        raise ValueError('Refusing mixed synthetic and real inputs')
    surface = Surface(terrain/terrain_manifest['reference_geotiff'], terrain_manifest)
    scene, parts, meshes, cell_meshes, obstacles = trimesh.Scene(), [], {}, defaultdict(list), []
    cells = config['cells_per_axis']; step = 2*surface.half/cells
    network = roads3d.Network(urban, surface, config['roads'])
    terrain_iterator = terrain_meshes
    if world:
        from .world import ProfileNetwork, CorrectedSurface, cut_terrain_meshes
        network = ProfileNetwork(network)
        surface = CorrectedSurface(surface, network)
        import shapely
        network.ground_obstacle=shapely.union_all([p for f in buildings['features']
            if buildings3d.heights(f['properties']['tags'],config['buildings'])['bottom_relative_ground_m']==0
            for p in buildings3d.footprint_parts(f)])
        network.terrain_surface=surface
        terrain_iterator = lambda s, c: cut_terrain_meshes(s, network, c)

    def add(name, mesh, role, info, cell=None):
        if name in meshes: raise ValueError('Duplicate mesh identifier')
        pivot = mesh.bounds.mean(axis=0)
        cell = cell or np.clip(((pivot[:2]+surface.half)/step).astype(int), 0, cells-1).tolist()
        local = mesh.copy(); local.apply_translation(-pivot)
        matrix = enu_to_gltf(); matrix[:3, 3] = enu_to_gltf()[:3, :3] @ pivot
        scene.add_geometry(local, node_name=name, geom_name=name, transform=matrix, metadata={'source': info.get('osm_id'), 'role': role})
        record = dict(info, name=name, role=role, cell=cell, vertex_count=len(mesh.vertices),
                      triangle_count=len(mesh.faces), bounds_enu_m=mesh.bounds.tolist(),
                      pivot_enu_m=pivot.tolist(), watertight=bool(mesh.is_watertight),
                      winding_consistent=bool(mesh.is_winding_consistent),
                      signed_volume_m3=float(mesh.volume) if role != 'terrain' else None,
                      minimum_triangle_area_m2=float(mesh.area_faces.min()))
        meshes[name] = mesh; parts.append(record); cell_meshes[tuple(cell)].append((name, mesh))

    for name, mesh in terrain_iterator(surface, cells):
        add(name, mesh, 'terrain', {'elevation_source': 'procedural_local_correction_layer' if world else 'unchanged_GEO001_reference_DSM', 'intentionally_open_surface': True})
    for feature in buildings['features']:
        for name, mesh, record, poly in buildings3d.generate(feature, surface, config['buildings'], graybox=world):
            add(name, mesh, 'building', record)
            if record['bottom_relative_ground_m'] == 0:
                obstacles.append(poly)
    for name, mesh, record in roads3d.generate(network, obstacles, cells):
        add(name, mesh, record['role'], record, record['cell'])
    if world:
        from .world import tunnel_walls
        for name, mesh, record in tunnel_walls(network, cells):
            add(name,mesh,record['role'],record,record['cell'])
    geometry_seconds = time.perf_counter()-start
    out.mkdir(parents=True, exist_ok=True)
    (out/'ue_cells').mkdir(); (out/'ue_terrain').mkdir()
    exports, terrain_exports = [], []
    for (x, y), pieces in sorted(cell_meshes.items()):
        pivot = np.array([-surface.half+(x+.5)*step, -surface.half+(y+.5)*step, 0.])
        for terrain_only in (False, True):
            selected = [(n,m) for n,m in pieces if (n.startswith('terrain_')) == terrain_only]
            if not selected: continue
            name = f'{"terrain" if terrain_only else "cell"}_{x}_{y}'
            path = out/('ue_terrain' if terrain_only else 'ue_cells')/f'{name}.obj'
            save_obj(path, selected, pivot)
            coordinates = np.vstack([m.bounds for _, m in selected])
            local_ue = enu_to_unreal_cm(coordinates-pivot)
            (terrain_exports if terrain_only else exports).append({'name': name, 'file': str(path.relative_to(out)),
                        'position_unreal_cm': enu_to_unreal_cm(pivot).tolist(),
                        'bounds_local_unreal_cm': [local_ue.min(axis=0).tolist(), local_ue.max(axis=0).tolist()],
                        'source_mesh_names': [n for n, _ in selected], 'sha256': sha256(path),
                        'material_file': str(path.with_suffix('.mtl').relative_to(out)), 'material_sha256': sha256(path.with_suffix('.mtl'))})
    glb = out/'monterrey_city.glb'
    glb.write_bytes(scene.export(file_type='glb'))
    semantic = network.semantic_graph(urban)
    semantic['geometry_audit'] = network.geometry_audit
    (out/'road_semantics.json').write_text(json.dumps(semantic, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    (out/'config.json').write_text(json.dumps(config, indent=2)+'\n', encoding='utf-8')
    building_records = [p for p in parts if p['role'] == 'building']
    with (out/'pcg_buildings.csv').open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Name','SourceId','PositionCm','SizeCm','BuildingClass','HeightM','HeightEstimated','HeightSource'])
        def vector(p): return f'(X={p[0]:.6f},Y={p[1]:.6f},Z={p[2]:.6f})'
        for p in building_records:
            bounds = np.asarray(p['bounds_enu_m'])
            writer.writerow([p['name'],p['osm_id'],vector(enu_to_unreal_cm(p['pivot_enu_m'])),
                             vector((bounds[1]-bounds[0])*100),p['category'],p['top_relative_ground_m'],
                             str(p['height_estimated']),p['height_source']])
    report = {
        'schema_version': 1, 'milestone': 'GEO-002', 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'synthetic': terrain_manifest['synthetic_demo_not_geographic_truth'],
        'input_terrain_manifest_sha256': sha256(terrain/'manifest.json'),
        'input_urban_sha256': sha256(urban_dir/'urban.json'), 'input_buildings_sha256': sha256(urban_dir/'buildings.geojson'),
        'source_crs': 'EPSG:32614', 'source_vertical_datum': terrain_manifest['source_vertical_datum'],
        'center_easting_northing_m': terrain_manifest['center_easting_northing_m'],
        'extent_m': terrain_manifest['extent_m'], 'coordinates_internal': 'right-handed East North Up metres; Z=source datum',
        'gltf_coordinates': 'right-handed X=east Y=up Z=south, metres; source datum zero',
        'obj_coordinates': 'Unreal numerical X=east Y=south Z=up, centimetres; cell-relative vertices',
        'gltf_enu_matrix': enu_to_gltf().tolist(), 'unreal_enu_scale': [100, -100, 100],
        'projection_scale_at_center': terrain_manifest['projection_scale_at_center'],
        'grid_convergence_at_center_degrees': terrain_manifest['grid_convergence_at_center_degrees'],
        'scale_note': '1 metre of projected grid = 100 Unreal units; UTM is not exact ground-distance scale',
        'mesh_parts': parts, 'ue_cells': exports, 'ue_terrain_cells': terrain_exports,
        'pcg_buildings_csv': 'pcg_buildings.csv', 'pcg_csv_sha256': sha256(out/'pcg_buildings.csv'),
        'road_semantics_sha256': sha256(out/'road_semantics.json'),
        'glb': glb.name, 'glb_sha256': sha256(glb),
        'summary': {'mesh_parts': len(parts), 'building_parts': len(building_records),
                    'building_features': len(buildings['features']), 'building_height_sources': dict(Counter(p['height_source'] for p in building_records)),
                    'building_categories': dict(Counter(p['category'] for p in building_records)),
                    'building_courtyards': sum(p['footprint_holes'] for p in building_records),
                    'road_segments': len(network.roads), 'road_grade_segments': dict(Counter(r['kind'] for r in network.roads)),
                    'triangles': sum(p['triangle_count'] for p in parts), 'vertices': sum(p['vertex_count'] for p in parts),
                    'closed_solids': sum(p['watertight'] for p in parts if p['role'] != 'terrain'),
                    'terrain_open_surfaces': sum(p['role'] == 'terrain' for p in parts),
                    'road_building_overlap_removed_m2': sum(r['building_overlap_removed_m2'] for r in network.geometry_audit),
                    'clearance_constraint_audit':network.clearance_audit,
                    'roads_with_sampled_grade_over_15_percent':sum(r['max_sampled_grade_percent']>15 for r in semantic['roads']),
                    'remaining_ground_road_building_overlap_m2': sum(p.get('ground_building_projected_overlap_m2') or 0 for p in parts),
                    'geometry_seconds': geometry_seconds, 'total_seconds': time.perf_counter()-start,
                    'glb_bytes': glb.stat().st_size},
        'engine_validation': {'editor_executed': False, 'landscape_imported': False, 'windows_build': False},
        'limitations': ['DSM is not bare-earth DTM; all foundations and road elevations are proxies',
                        'Estimated facade heights, floor sizes, widths, sidewalks and grade profiles are procedural blockout',
                        'No terrain excavation at tunnel portals, bridge engineering, lane graph or turn restrictions',
                        'Flat roofs and repeating panels do not reproduce real facades or monuments',
                        'Same-grade surface unions are geometric; logical graph retains only original OSM edges',
                        'UE import, World Partition, Nanite, Lumen, PCG and HLOD require editor execution']}
    (out/'manifest.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    notices = (terrain/'DATA_LICENSES.txt').read_text(encoding='utf-8') if (terrain/'DATA_LICENSES.txt').exists() else 'Synthetic terrain fixture.\n'
    notices += '\n© OpenStreetMap contributors — ODbL 1.0, https://www.openstreetmap.org/copyright\n' if not report['synthetic'] else '\nSynthetic urban fixture.\n'
    (out/'DATA_LICENSES.txt').write_text(notices, encoding='utf-8')
    if world:
        from .world import finalize_world
        finalize_world(out, report, meshes, surface, network)
    print(json.dumps(report['summary'], indent=2))
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--terrain', required=True); p.add_argument('--urban', required=True); p.add_argument('--output', required=True)
    p.add_argument('--config', help='Complete generation config; defaults are exported as config.json')
    a = p.parse_args()
    try:
        build(a.terrain, a.urban, a.output, json.loads(Path(a.config).read_text()) if a.config else None)
    except (ValueError, OSError, KeyError) as exc:
        p.exit(2, f'GEO-002 failed: {exc}\n')


if __name__ == '__main__':
    main()

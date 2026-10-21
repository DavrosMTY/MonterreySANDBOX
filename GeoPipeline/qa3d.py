"""Read the actual exported GLB/OBJ back; validate dimensions, topology and evidence."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import numpy as np
import trimesh

from .geo001 import sha256
from .mesh import enu_to_gltf


def validate_city(directory, check_obj=True):
    start = time.perf_counter(); root = Path(directory).resolve()
    m = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    glb = root/m['glb']
    if not glb.is_relative_to(root) or sha256(glb) != m['glb_sha256']:
        raise ValueError('GLB checksum mismatch')
    scene = trimesh.load_scene(glb, process=False)
    records = {p['name']: p for p in m['mesh_parts']}
    seen, solid_count, triangle_count, error = set(), 0, 0, 0.
    for node in scene.graph.nodes_geometry:
        matrix, geometry = scene.graph[node]
        if node not in records or node in seen:
            raise ValueError(f'Unexpected or duplicate GLB node: {node}')
        seen.add(node); record = records[node]; mesh = scene.geometry[geometry]
        xyz = trimesh.transform_points(mesh.vertices, matrix)
        enu = trimesh.transform_points(xyz, np.linalg.inv(enu_to_gltf()))
        bounds = np.asarray([enu.min(axis=0), enu.max(axis=0)])
        delta = np.max(np.abs(bounds-np.asarray(record['bounds_enu_m'])))
        error = max(error, float(delta))
        if delta > .002:
            raise ValueError(f'GLB coordinate/scale error {node}: {delta} metres')
        if len(mesh.faces) != record['triangle_count'] or not np.isfinite(enu).all():
            raise ValueError('GLB triangle count or finite coordinate mismatch')
        # Materials and flat colors can duplicate vertices at seams in interchange.
        # Weld positions for topology checks; do not alter the delivered mesh.
        welded = trimesh.Trimesh(mesh.vertices, mesh.faces, process=True)
        if len(welded.faces) != len(mesh.faces) or np.min(welded.area_faces) <= 1e-12:
            raise ValueError(f'Degenerate triangles after interchange: {node}')
        if not welded.is_winding_consistent:
            raise ValueError(f'Inconsistent triangle winding: {node}')
        if record['role'] != 'terrain':
            solid_count += 1
            if not welded.is_watertight or welded.volume <= 0:
                raise ValueError(f'Non-closed or negative-volume exported solid: {node}')
            if not np.isclose(welded.volume, record['signed_volume_m3'], atol=.002, rtol=.001):
                raise ValueError(f'Exported solid volume changed: {node}')
        triangle_count += len(mesh.faces)
    if seen != set(records):
        raise ValueError('Missing exported GLB parts')
    obj_checked = 0
    for cell in m['ue_cells']+m.get('ue_terrain_cells', [])+m.get('ue_system_cells', []):
        path = root/cell['file']; material = root/cell['material_file']
        if not path.resolve().is_relative_to(root) or not material.resolve().is_relative_to(root):
            raise ValueError('OBJ path escapes export directory')
        if sha256(path) != cell['sha256'] or sha256(material) != cell['material_sha256']:
            raise ValueError('OBJ/MTL checksum mismatch')
        if check_obj:
            obj = trimesh.load_scene(path, process=False)
            if not np.allclose(obj.bounds, cell['bounds_local_unreal_cm'], atol=.02, rtol=0):
                raise ValueError(f'OBJ centimetre dimensions or axes changed: {path.name}')
            expected = sum(records[n]['triangle_count'] for n in cell['source_mesh_names'])
            if sum(len(g.faces) for g in obj.geometry.values()) != expected:
                raise ValueError('OBJ triangle count changed')
            obj_checked += 1
    graph = json.loads((root/'road_semantics.json').read_text(encoding='utf-8'))
    if m.get('road_semantics_sha256') and sha256(root/'road_semantics.json')!=m['road_semantics_sha256']:
        raise ValueError('Road semantic provenance changed')
    if graph['new_geometric_crossing_connections'] != 0 or graph['lane_graph_generated']:
        raise ValueError('Unexpected synthetic road connectivity')
    if m['summary']['remaining_ground_road_building_overlap_m2'] > 1e-6:
        raise ValueError('Ground roads overlap blocking building footprints')
    return {'status': 'passed', 'glb_nodes_verified': len(seen), 'closed_solids_verified': solid_count,
            'triangles_verified': triangle_count, 'obj_cells_read_back': obj_checked,
            'max_coordinate_roundtrip_error_m': error, 'elapsed_seconds': time.perf_counter()-start,
            'engine_import_verified': False,
            'limits': ['Does not certify survey accuracy, ground datum alignment, or physical collision of all mesh pairs',
                       'Terrain is intentionally an open sampled surface; other parts are closed solids after position welding']}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('directory'); p.add_argument('--output')
    a = p.parse_args()
    try:
        result = validate_city(a.directory)
        if a.output: Path(a.output).write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError) as exc:
        p.exit(2, f'GEO-002 QA failed: {exc}\n')


if __name__ == '__main__':
    main()

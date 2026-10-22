"""Read back every web GLB and compare topology, positions, colors and IDs to GEO-003."""
import argparse
import gzip
import io
import json
from pathlib import Path

import numpy as np
import trimesh

from build_web_viewer import sha


def validate(city, site):
    city, site = Path(city), Path(site)
    original = json.loads((city / 'manifest.json').read_text())
    world = json.loads((site / 'world.json').read_text())
    source = trimesh.load(city / original['glb'], force='scene', process=False)
    features = json.loads((site / world['features_url']).read_text())
    if sha(city / original['glb']) != world['source_glb_sha256']:
        raise ValueError('Wrong source')
    expected_records = {p['name']: p for p in original['mesh_parts']}
    names, triangles, max_error = [], 0, 0.
    for sector in world['sectors']:
        path = site / sector['url']
        if sha(path) != sector['sha256']:
            raise ValueError('Sector hash mismatch')
        loaded = trimesh.load(io.BytesIO(gzip.decompress(path.read_bytes())), file_type='glb', force='scene', process=False)
        for node in loaded.graph.nodes_geometry:
            transform, geometry = loaded.graph[node]
            actual = loaded.geometry[geometry]; actual.apply_transform(transform)
            records = features[sector['id']][node]
            vertices, faces, colors, offset, face_offset = [], [], [], 0, 0
            for f in records:
                name = f['name']; names.append(name)
                if f['source'] != expected_records[name] or f['first_triangle'] != face_offset:
                    raise ValueError('Lost source ID or triangle lookup')
                matrix, g = source.graph[name]
                mesh = source.geometry[g].copy(); mesh.apply_transform(matrix)
                vertices.append(mesh.vertices); faces.append(mesh.faces + offset); colors.append(mesh.visual.vertex_colors)
                offset += len(mesh.vertices); face_offset += len(mesh.faces)
            expected_pos = np.concatenate(vertices)
            error = float(np.max(np.abs(expected_pos - actual.vertices)))
            max_error = max(max_error, error)
            if error > .0001 or not np.array_equal(np.concatenate(faces), actual.faces):
                raise ValueError('Web geometry differs beyond 0.1 mm or topology changed')
            if not np.array_equal(np.concatenate(colors), (actual.visual.vertex_colors if hasattr(actual.visual, 'vertex_colors') else actual.visual.vertex_attributes['color'])):
                raise ValueError('Original vertex colors changed')
            triangles += len(actual.faces)
    if len(names) != len(set(names)) or set(names) != set(expected_records) or triangles != world['triangles']:
        raise ValueError('Missing/duplicated source parts or triangles')
    result = {'status': 'passed', 'source_sha256': world['source_glb_sha256'], 'sectors': len(world['sectors']),
              'source_parts_preserved': len(names), 'triangles_preserved': triangles, 'maximum_position_error_m': max_error,
              'source_metadata_ids_and_colors_preserved': True, 'unreal_execution': False}
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city', default='Data/city/geo003_world001')
    p.add_argument('--site', required=True)
    p.add_argument('--receipt')
    a = p.parse_args()
    result = validate(a.city, a.site)
    if a.receipt:
        Path(a.receipt).write_text(json.dumps(result, indent=2) + '\n')

"""FREE-001: lossless geometry batching of the reviewed GEO-003 GLB for static web.

Only generated deployment assets, never a replacement for authoritative GIS/UE files.
Uses short index buffers and gzip transport; no geometry simplification or fake city.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct

import numpy as np
import trimesh

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def glb_bytes(groups, pivot):
    """Minimal GLB2: positions float32, original normalized RGBA, uint16 if possible."""
    data = bytearray()
    doc = {'asset': {'version': '2.0', 'generator': 'Monterrey FREE-001'},
           'scene': 0, 'scenes': [{'nodes': []}], 'nodes': [], 'meshes': [],
           'materials': [{'name': 'Original GEO-003 vertex colors',
                          'pbrMetallicRoughness': {'baseColorFactor': [1, 1, 1, 1],
                                                   'metallicFactor': 0, 'roughnessFactor': 1},
                          'doubleSided': False}],
           'bufferViews': [], 'accessors': []}

    def accessor(array, component, kind, target, bounds=False, normalized=False):
        while len(data) % 4:
            data.append(0)
        offset = len(data)
        data.extend(array.tobytes())
        view = len(doc['bufferViews'])
        doc['bufferViews'].append({'buffer': 0, 'byteOffset': offset,
                                  'byteLength': array.nbytes, 'target': target})
        item = {'bufferView': view, 'componentType': component, 'count': len(array), 'type': kind}
        if normalized:
            item['normalized'] = True
        if bounds:
            item.update(min=array.min(axis=0).tolist(), max=array.max(axis=0).tolist())
        doc['accessors'].append(item)
        return len(doc['accessors']) - 1

    for name, meshes in sorted(groups.items()):
        vertices, colors, indices, features = [], [], [], []
        count, faces = 0, 0
        for source_name, mesh, record in meshes:
            vertices.append(mesh.vertices - pivot)
            colors.append(np.asarray(mesh.visual.vertex_colors, dtype=np.uint8))
            indices.append(mesh.faces + count)
            features.append({'name': source_name, 'first_triangle': faces,
                             'triangle_count': len(mesh.faces), 'source': record})
            count += len(mesh.vertices)
            faces += len(mesh.faces)
        pos = np.concatenate(vertices).astype('<f4')
        color = np.concatenate(colors).astype('u1')
        index_type, component = ('<u2', 5123) if count <= 65535 else ('<u4', 5125)
        index = np.concatenate(indices).reshape(-1).astype(index_type)
        attributes = {'POSITION': accessor(pos, 5126, 'VEC3', 34962, bounds=True),
                      'COLOR_0': accessor(color, 5121, 'VEC4', 34962, normalized=True)}
        i = accessor(index, component, 'SCALAR', 34963)
        doc['meshes'].append({'name': name, 'primitives': [{'attributes': attributes,
                                                       'indices': i, 'material': 0}]})
        doc['nodes'].append({'name': name, 'mesh': len(doc['meshes']) - 1,
                             'translation': pivot.tolist(), 'extras': {'system': name}})
        doc['scenes'][0]['nodes'].append(len(doc['nodes']) - 1)
        groups[name] = features
    doc['buffers'] = [{'byteLength': len(data)}]
    encoded = json.dumps(doc, separators=(',', ':')).encode()
    encoded += b' ' * (-len(encoded) % 4)
    data.extend(b'\0' * (-len(data) % 4))
    return (struct.pack('<III', 0x46546C67, 2, 12 + 8 + len(encoded) + 8 + len(data))
            + struct.pack('<I4s', len(encoded), b'JSON') + encoded
            + struct.pack('<I4s', len(data), b'BIN\0') + data)


def build(city, output):
    city, out = Path(city), Path(output)
    manifest = json.loads((city / 'manifest.json').read_text())
    source = city / manifest['glb']
    if manifest.get('synthetic') is not False or manifest.get('milestone') != 'GEO-003 / WORLD-001':
        raise ValueError('The public viewer requires real GEO-003, never synthetic fixtures')
    if manifest.get('source_crs') != 'EPSG:32614' or manifest.get('source_vertical_datum') != 'EGM2008':
        raise ValueError('Unexpected geospatial contract')
    if sha(source) != manifest['glb_sha256']:
        raise ValueError('Source GLB checksum mismatch')
    if out.exists():
        raise FileExistsError('Preserve previous builds: output must be a new directory')
    scene = trimesh.load(source, force='scene', process=False)
    records = {p['name']: p for p in manifest['mesh_parts']}
    sectors = defaultdict(lambda: defaultdict(list))
    seen = set()
    for node in sorted(scene.graph.nodes_geometry):
        matrix, name = scene.graph[node]
        record = records[name]
        if name in seen:
            raise ValueError('Unexpected duplicated source geometry')
        seen.add(name)
        mesh = scene.geometry[name].copy()
        mesh.apply_transform(matrix)
        sectors[tuple(record['cell'])][record['system']].append((name, mesh, record))
    if seen != set(records):
        raise ValueError('Source parts were lost')
    out.mkdir(parents=True)
    shutil.copytree(ROOT / 'WebViewer/src', out, dirs_exist_ok=True)
    vendor = ROOT / 'WebViewer/node_modules/three'
    for name in ('build/three.module.min.js', 'build/three.core.min.js',
                 'examples/jsm/loaders/GLTFLoader.js', 'examples/jsm/utils/BufferGeometryUtils.js', 'LICENSE'):
        target = out / 'vendor/three' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vendor / name, target)
    # The minified module imports its corresponding minified core by relative URL.
    licenses = out / 'licenses'
    licenses.mkdir()
    for source_path, target_name in [(ROOT / 'DATA_LICENSES.md', 'DATA_LICENSES.md'),
                                     (ROOT / 'docs/sources/COPERNICUS_GLO30_LICENSE.txt', 'COPERNICUS.txt'),
                                     (ROOT / 'docs/sources/ODbL-1.0.txt', 'ODbL-1.0.txt')]:
        shutil.copy2(source_path, licenses / target_name)
    assets = out / 'assets'
    assets.mkdir()
    index = []
    features = {}
    for (cx, cy), groups in sorted(sectors.items()):
        cell_id = f'{cx}_{cy}'
        pivot = np.array([-875 + cx * 250, 550., 875 - cy * 250])
        bounds = np.vstack([m.bounds for parts in groups.values() for _, m, _ in parts])
        ntri = sum(len(m.faces) for parts in groups.values() for _, m, _ in parts)
        binary = glb_bytes(groups, pivot)
        payload = gzip.compress(binary, compresslevel=9, mtime=0)
        path = assets / f'cell_{cell_id}.glb.gz'
        path.write_bytes(payload)
        index.append({'id': cell_id, 'cell': [cx, cy], 'url': f'assets/{path.name}',
                      'center': pivot.tolist(), 'bounds': [bounds.min(axis=0).tolist(), bounds.max(axis=0).tolist()],
                      'triangles': ntri, 'meshes': len(groups), 'bytes': len(payload),
                      'uncompressed_bytes': len(binary), 'sha256': sha(path)})
        features[cell_id] = groups
    (assets / 'features.json').write_text(json.dumps(features, separators=(',', ':')))
    result = {'schema_version': 1, 'milestone': 'FREE-001', 'synthetic': False,
              'source_milestone': manifest['milestone'], 'source_glb_sha256': sha(source),
              'source_manifest_sha256': sha(city / 'manifest.json'),
              'source_release': 'geo003-world001-3f5c050a07c6',
              'source_crs': manifest['source_crs'], 'vertical_datum': manifest['source_vertical_datum'],
              'center_easting_northing_m': manifest['center_easting_northing_m'],
              'axes': 'X east, Y up (EGM2008), Z south; metres; same as source GLB',
              'extent_m': manifest['extent_m'], 'sector_size_m': 250,
              'original_bytes': source.stat().st_size, 'original_meshes': len(records),
              'triangles': sum(x['triangles'] for x in index),
              'optimized_meshes': sum(x['meshes'] for x in index),
              'transport_bytes': sum(x['bytes'] for x in index),
              'geometry_loss': False, 'max_position_rounding_bound_m': 0.0001,
              'features_url': 'assets/features.json', 'sectors': index,
              'limitations': manifest['limitations'], 'unreal_executed': False}
    if result['triangles'] != sum(p['triangle_count'] for p in records.values()):
        raise ValueError('Triangle preservation failure')
    (out / 'world.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / '.nojekyll').write_text('')
    size = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    if size > 50 * 1024**2:
        raise ValueError('FREE-001 deployment exceeds its 50 MiB site cap')
    print(json.dumps({k: result[k] for k in ('triangles', 'original_meshes', 'optimized_meshes',
                                             'original_bytes', 'transport_bytes')} | {'site_bytes': size}, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--city', default='Data/city/geo003_world001')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    build(args.city, args.output)

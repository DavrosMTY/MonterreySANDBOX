"""Package the reviewed pilot without virtualenv, caches or the 40 MB global DEM tile."""
import argparse
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--acceptance-run', required=True)
    p.add_argument('--osm-source', required=True)
    p.add_argument('--output', default='artifacts/MonterreyOpenWorld_GEO001_1.zip')
    a = p.parse_args()
    output = ROOT/a.output
    if output.exists():
        p.error('Output ZIP already exists; preserve it or choose another name')
    files = {}

    def add(path, name):
        if not path.is_file():
            raise ValueError(f'Missing package input: {path}')
        files[name] = path

    def add_tree(path, prefix):
        for file in sorted(path.rglob('*')):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix != '.pyc':
                add(file, str(Path(prefix)/file.relative_to(path)))

    for name in ('GeoPipeline', 'tests', 'docs', 'tools', 'Unreal', '.github'):
        add_tree(ROOT/name, name)
    for name in ('README.md', '.gitignore', '.python-version', 'requirements.txt', 'requirements.lock.txt', 'pytest.ini'):
        add(ROOT/name, name)
    for source in ('Data/unreal/monterrey_centro_single_v3', 'Data/unreal/monterrey_centro_tiles_v3', 'Data/urban/monterrey_centro_v3'):
        add_tree(ROOT/source, source)
    run = ROOT/a.acceptance_run
    for path in run.glob('*'):
        if path.is_file():
            add(path, 'evidence/'+path.name)
    osm = ROOT/a.osm_source
    add(osm, 'Data/raw/osm.json')
    add(Path(str(osm)+'.source.json'), 'Data/raw/osm.json.source.json')
    add(ROOT/'Data/raw/copernicus_reviewed.source.json', 'Data/raw/copernicus.source.json')
    add(ROOT/'artifacts/monterrey_centro_mapa.png', 'artifacts/monterrey_centro_mapa.png')
    notices = ('Copernicus derivatives: see Data/unreal/*/DATA_LICENSES.txt and docs/sources/COPERNICUS_GLO30_LICENSE.txt.\n'
               'OSM source extract and derived databases: © OpenStreetMap contributors, ODbL 1.0.\n'
               'Full ODbL text: docs/sources/ODbL-1.0.txt. Source extract: Data/raw/osm.json.\n'
               'No general public redistribution licence for the project code was supplied.\n')
    output.parent.mkdir(exist_ok=True, parents=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(files.items()):
            archive.write(path, 'MonterreyOpenWorld/'+name)
        archive.writestr('MonterreyOpenWorld/DATA_LICENSES.txt', notices)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity failure')
    print(json.dumps({'output': str(output), 'files': len(files)+1, 'bytes': output.stat().st_size}))


if __name__ == '__main__':
    main()

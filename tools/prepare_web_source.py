"""Extract ONLY the pinned, license-reviewed GEO-003 source from its release ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def extract(archive, output, visual=False):
    archive, output = Path(archive), Path(output)
    expected = next(x for x in json.loads((ROOT / 'manifests/github-release-verification.json').read_text())['payload_files']
                    if x['file'] == 'MonterreyOpenWorld_GEO003_WORLD001.zip')['sha256']
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise ValueError('Release archive checksum mismatch')
    if output.exists():
        raise FileExistsError('Never overwrite a source checkout')
    prefix = 'MonterreyOpenWorld/Data/city/geo003_world001/'
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read(prefix + 'manifest.json'))
        if Path(manifest['glb']).name != manifest['glb']:
            raise ValueError('Unexpected GLB path')
        glb = z.read(prefix + manifest['glb'])
        if hashlib.sha256(glb).hexdigest() != manifest['glb_sha256']:
            raise ValueError('Source GLB checksum mismatch')
        output.mkdir(parents=True)
        (output / 'manifest.json').write_bytes(z.read(prefix + 'manifest.json'))
        (output / manifest['glb']).write_bytes(glb)
        if visual:
            roads=z.read(prefix+'road_semantics.json')
            if hashlib.sha256(roads).hexdigest()!=manifest['road_semantics_sha256']:raise ValueError('Road metadata hash mismatch')
            (output/'road_semantics.json').write_bytes(roads)
    print(json.dumps({'source_glb_sha256': manifest['glb_sha256'], 'output': str(output)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--visual',action='store_true')
    a = p.parse_args()
    extract(a.archive, a.output,a.visual)

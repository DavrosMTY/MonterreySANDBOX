"""Rebuild GEO-002/003 from the committed licensed pilot and prepare Release assets.

Uses ephemeral workspace disk, no LFS, Actions artifact uploads or cache service.
--reuse-local validates retained models for a local packaging rehearsal only.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def run(args):
    print('Executing:',str(args[0]),' '.join(str(x) for x in args[1:]),flush=True)
    subprocess.run(list(map(str,args)),cwd=ROOT,check=True)


def acceptance(tool,prefix,city,renders):
    before=set((ROOT/'artifacts').glob(prefix+'*'))
    run([sys.executable,'tools/'+tool,'--city-existing',city,'--renders-existing',renders])
    created=set((ROOT/'artifacts').glob(prefix+'*'))-before
    if len(created)!=1:raise ValueError('Cannot uniquely identify acceptance evidence')
    return next(iter(created)).relative_to(ROOT)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',default='artifacts/github-release')
    p.add_argument('--reuse-local',action='store_true');a=p.parse_args()
    out=(ROOT/a.output).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('Release output must be empty')
    out.mkdir(parents=True,exist_ok=True);(ROOT/'artifacts').mkdir(exist_ok=True)
    run([sys.executable,'tools/check_publication.py'])
    cities={'GEO002':'Data/city/geo002_v4','GEO003':'Data/city/geo003_world001'}
    renders={'GEO002':'artifacts/geo002_renders_v4','GEO003':'artifacts/geo003_renders'}
    if not a.reuse_local:
        blender=shutil.which('blender')
        if not blender:raise RuntimeError('Blender is required for actual geometry images')
        for milestone,module in [('GEO002','GeoPipeline.city'),('GEO003','GeoPipeline.world')]:
            run([sys.executable,'-m',module,'--terrain','Data/unreal/monterrey_centro_single_v3',
                '--urban','Data/urban/monterrey_centro_v3','--output',cities[milestone]])
            run([blender,'--background','--factory-startup','--python-exit-code','1','--python',ROOT/'tools/render_city.py',
                '--','--city',cities[milestone],'--output',renders[milestone],'--samples','64','--threads','4'])
    two=acceptance('run_geo002.py','geo002-acceptance-',cities['GEO002'],renders['GEO002'])
    three=acceptance('run_geo003.py','geo003-acceptance-',cities['GEO003'],renders['GEO003'])
    run([sys.executable,'tools/package_geo002.py','--city',cities['GEO002'],'--renders',renders['GEO002'],
        '--acceptance',two,'--output',out/'MonterreyOpenWorld_GEO002.zip'])
    run([sys.executable,'tools/package_geo003.py','--city',cities['GEO003'],'--renders',renders['GEO003'],
        '--acceptance',three,'--output',out/'MonterreyOpenWorld_GEO003_WORLD001.zip'])
    pilot=json.loads((ROOT/'manifests/pilot-inputs.json').read_text())
    with zipfile.ZipFile(out/'MonterreyOpenWorld_GEO001_pilot.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
        for item in pilot['files']:archive.write(ROOT/item['path'],item['path'])
        for name in ('manifests/GEO001/reference.json','manifests/pilot-inputs.json','DATA_LICENSES.md',
                     'docs/sources/COPERNICUS_GLO30_LICENSE.txt','docs/sources/ODbL-1.0.txt'):
            archive.write(ROOT/name,name)
    for source,destination in [('Data/city/geo003_world001/monterrey_city.glb','Monterrey_WORLD001.glb'),
        ('artifacts/geo003_renders/monterrey_world001.blend','Monterrey_WORLD001.blend'),
        ('artifacts/geo003_renders/aerial.png','WORLD001_aerial.png'),
        ('artifacts/geo003_renders/street.png','WORLD001_street.png'),
        ('artifacts/geo003_renders/elevated.png','WORLD001_bridge.png'),('DATA_LICENSES.md','DATA_LICENSES.md')]:
        shutil.copyfile(ROOT/source,out/destination)
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip())
    if dirty:raise ValueError('Tracked source changes must be committed before publishing artifacts')
    manifest={'repository':'DavrosMTY/MonterreySANDBOX','source_commit':sha,
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),'local_model_reuse':a.reuse_local,
        'engine_executed':False,'full_world_drivable_certified':False,
        'acceptance':{'GEO002':json.loads((ROOT/two/'acceptance.json').read_text()),
                      'GEO003':json.loads((ROOT/three/'acceptance.json').read_text())},'files':[]}
    for path in sorted(out.iterdir()):
        if path.is_file():manifest['files'].append({'file':path.name,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (out/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'SHA256SUMS.txt').write_text(''.join(f'{v["sha256"]}  {v["file"]}\n' for v in manifest['files']))
    notes=f'''# Monterrey Open World — entrega reproducible

Código fuente: `{sha}`. GEO-001 piloto, GEO-002 y GEO-003 / WORLD-001.

Los ZIP son reconstrucciones verificadas desde los inputs licenciados del repositorio;
no se afirma identidad binaria con los ZIP históricos conservados localmente.
Los modelos incluyen las limitaciones descritas en README y diagnósticos: base
candidata, 97 tramos motorizados pendientes en la referencia local, no mundo completo
conducible. Unreal/Windows no compilado ni ejecutado. Renders reales de Blender.

Revisa `release-manifest.json` y `SHA256SUMS.txt` para hashes, pruebas y procedencia.
Fuente y datos: avisos Copernicus/ODbL en DATA_LICENSES.md y dentro de los paquetes.
Publicación como prerelease sobre development; no fusiona el Pull Request.
'''
    (out/'RELEASE_NOTES.md').write_text(notes)
    print(json.dumps({'status':'ready','directory':str(out),'source_commit':sha,'files':len(manifest['files']),
                      'total_bytes':sum(x['bytes'] for x in manifest['files'])},indent=2))


if __name__=='__main__':main()

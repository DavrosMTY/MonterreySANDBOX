"""New WORLD-001 review ZIP; verifies every delivered file and its acceptance target."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city',default='Data/city/geo003_world001');p.add_argument('--renders',default='artifacts/geo003_renders')
    p.add_argument('--acceptance',required=True);p.add_argument('--output',default='artifacts/MonterreyOpenWorld_GEO003_WORLD001.zip')
    a=p.parse_args();out=ROOT/a.output
    if out.exists():raise ValueError('Refusing to overwrite delivery')
    receipt=json.loads((ROOT/a.acceptance/'acceptance.json').read_text())
    model=json.loads((ROOT/a.city/'manifest.json').read_text())
    if receipt['status']!='offline_acceptance_passed_with_world_refinement_required' or receipt['model_sha256']!=model['glb_sha256']:
        raise ValueError('Missing acceptance for selected model')
    files={}
    def add(path,name):
        if not path.is_file():raise ValueError('Missing '+str(path))
        files[name]=path
    def tree(directory,prefix):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and not any(x in path.parts for x in ('__pycache__','.pytest_cache','Binaries','Intermediate','Saved','DerivedDataCache')) and path.suffix not in ('.pyc','.blend1'):
                add(path,str(Path(prefix)/path.relative_to(directory)))
    for folder in ('GeoPipeline','tools','tests','docs','Unreal','.github','manifests'):tree(ROOT/folder,folder)
    for name in ('README.md','AGENTS.md','DATA_LICENSES.md','.gitattributes','.gitignore','.python-version','requirements.txt','requirements.lock.txt','pytest.ini'):add(ROOT/name,name)
    for name in (a.city,a.renders,'Data/unreal/monterrey_centro_single_v3','Data/urban/monterrey_centro_v3'):tree(ROOT/name,name)
    tree(ROOT/a.acceptance,'evidence/WORLD001')
    raw=ROOT/'Data/raw/osm.json'
    if not raw.exists():raw=ROOT/'artifacts/geo001_1-2g9pdv5u/real/osm.json'
    add(raw,'Data/raw/osm.json');add(Path(str(raw)+'.source.json'),'Data/raw/osm.json.source.json')
    add(ROOT/'Data/raw/copernicus_reviewed.source.json','Data/raw/copernicus_reviewed.source.json')
    add(ROOT/a.city/'DATA_LICENSES.txt','DATA_LICENSES.txt')
    index={'milestone':'GEO-003 / WORLD-001','model_sha256':model['glb_sha256'],
        'full_world_drivable_certified':False,'unreal_executed':receipt['unreal_executed'],
        'excluded':'Virtualenv, caches, prior model iterations, prior ZIPs and full 1 degree DEM; original sector reference raster is included.',
        'files':[{'path':n,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for n,p in sorted(files.items())]}
    out.parent.mkdir(exist_ok=True,parents=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for name,path in sorted(files.items()):archive.write(path,'MonterreyOpenWorld/'+name,compress_type=zipfile.ZIP_STORED if path.suffix in ('.png','.blend') else zipfile.ZIP_DEFLATED)
        archive.writestr('MonterreyOpenWorld/PACKAGE_CONTENTS.json',json.dumps(index,indent=2)+'\n')
    with zipfile.ZipFile(out) as archive:
        if archive.testzip():raise ValueError('ZIP CRC failed')
        for record in index['files']:
            data=archive.read('MonterreyOpenWorld/'+record['path'])
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Packaged file hash failed')
    print(json.dumps({'file':str(out),'bytes':out.stat().st_size,'entries':len(files)+1,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'all_file_hashes_verified':True},indent=2))


if __name__=='__main__':main()

"""Create a reviewable GEO-002 delivery with source, real models, renders and evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city',default='Data/city/geo002_v4');p.add_argument('--renders',default='artifacts/geo002_renders_v4')
    p.add_argument('--acceptance',required=True)
    p.add_argument('--osm-source',help='Original Overpass extract; defaults to packaged raw data or existing cloud acquisition')
    p.add_argument('--output',default='artifacts/MonterreyOpenWorld_GEO002.zip')
    a=p.parse_args();out=ROOT/a.output
    if out.exists():p.error('Refusing to overwrite a previous delivery')
    receipt=json.loads((ROOT/a.acceptance/'acceptance.json').read_text())
    if receipt['status']!='geospatial_and_3d_acceptance_passed':raise ValueError('Acceptance did not pass')
    model=json.loads((ROOT/a.city/'manifest.json').read_text())
    if receipt['model_sha256']!=model['glb_sha256']:raise ValueError('Acceptance refers to a different model')
    files={}
    def add(path,name):
        if not path.is_file():raise ValueError(f'Missing delivery file: {path}')
        files[name]=path
    def tree(directory,prefix):
        for path in sorted(directory.rglob('*')):
            if path.is_file() and not any(x in path.parts for x in ('__pycache__','.pytest_cache','Binaries','Intermediate','Saved','DerivedDataCache')) and path.suffix not in ('.pyc','.blend1'):
                add(path,str(Path(prefix)/path.relative_to(directory)))
    for name in ('GeoPipeline','tools','tests','docs','Unreal','.github','manifests'):
        tree(ROOT/name,name)
    for name in ('README.md','AGENTS.md','DATA_LICENSES.md','.gitattributes','.gitignore','.python-version','requirements.txt','requirements.lock.txt','pytest.ini'):
        add(ROOT/name,name)
    for name in (a.city,a.renders,'Data/unreal/monterrey_centro_single_v3','Data/urban/monterrey_centro_v3'):
        tree(ROOT/name,name)
    tree(ROOT/a.acceptance,'evidence/GEO002')
    raw=ROOT/a.osm_source if a.osm_source else ROOT/'Data/raw/osm.json'
    if not raw.exists():raw=ROOT/'artifacts/geo001_1-2g9pdv5u/real/osm.json'
    add(raw,'Data/raw/osm.json');add(Path(str(raw)+'.source.json'),'Data/raw/osm.json.source.json')
    add(ROOT/'Data/raw/copernicus_reviewed.source.json','Data/raw/copernicus_reviewed.source.json')
    add(ROOT/a.city/'DATA_LICENSES.txt','DATA_LICENSES.txt')
    add(ROOT/a.city/'DATA_LICENSES.txt',str(Path(a.renders)/'DATA_LICENSES.txt'))
    index={'milestone':'GEO-002','files':[{'path':n,'bytes':v.stat().st_size,'sha256':hashlib.sha256(v.read_bytes()).hexdigest()} for n,v in sorted(files.items())],
           'excluded':'Virtualenv, caches, previous geometry iterations, and full 1-degree Copernicus DEM; reproducible pilot GeoTIFF is included.',
           'unreal_compiled_or_executed':any(receipt.get('unreal',{}).get(k,False) for k in ('editor_executed','native_module_compiled')),
           'published_or_pushed':False}
    out.parent.mkdir(exist_ok=True,parents=True)
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,path in sorted(files.items()):
            compression=zipfile.ZIP_STORED if path.suffix in ('.png','.blend') else zipfile.ZIP_DEFLATED
            z.write(path,'MonterreyOpenWorld/'+name,compress_type=compression)
        z.writestr('MonterreyOpenWorld/PACKAGE_CONTENTS.json',json.dumps(index,indent=2)+'\n')
    with zipfile.ZipFile(out) as z:
        if z.testzip():raise ValueError('ZIP CRC verification failed')
    print(json.dumps({'file':str(out),'bytes':out.stat().st_size,'entries':len(files)+1,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()},indent=2))


if __name__=='__main__':main()

"""Publish reproducible licensed GEO-004 outputs via a free public runner token."""
import argparse
import base64
import re
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import urllib.request
import zipfile


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def gh(*args):return subprocess.check_output(['gh',*args],text=True)


def publish(city,terrain,validation,site,browser,inputs):
    city,terrain,validation,site,browser,inputs=map(Path,(city,terrain,validation,site,browser,inputs))
    report=json.loads((browser/'browser-report.json').read_text());assert report['status']=='passed'and report['geo004']['status']=='passed'
    source=os.environ.get('MOW_VALIDATED_SOURCE',os.environ['GITHUB_SHA']);repository=os.environ['GITHUB_REPOSITORY'];assert repository=='DavrosMTY/MonterreySANDBOX'
    world=json.loads((site/'world.json').read_text());assert world['milestone']=='GEO-004'and not world['synthetic']
    assert json.loads((city/'manifest.json').read_text())['glb_sha256']==world['source_glb_sha256']
    out=Path('artifacts/geo004-release');out.mkdir(exist_ok=False)
    # Check official current limits before using Releases, without LFS/Artifacts.
    records=[];documents=[]
    for path in ('content/repositories/releasing-projects-on-github/about-releases.md','data/variables/releases.yml','data/variables/large_files.yml'):
        response=json.loads(gh('api','repos/github/docs/contents/'+path))
        body=base64.b64decode(response['content']);documents.append(body.decode())
        records.append({'url':'https://github.com/github/docs/blob/main/'+path,'blob_sha':response['sha'],'sha256':hashlib.sha256(body).hexdigest()})
    maximum=int(re.search(r"release_asset_limit:\s*['\"]?(\d+)",documents[1]).group(1))
    assert '2 GiB'in documents[2]and 'no limit on the total size'in documents[0].lower()
    limits={'official_sources':records,'individual_asset_limit_bytes':2*1024**3,'maximum_assets':maximum,'no_total_size_or_bandwidth_cap_per_official_docs':True,'budget_usd':0,'no_lfs_or_actions_artifacts':True}
    (out/'geo004-release-limits.json').write_text(json.dumps(limits,indent=2)+'\n')
    def archive(path,roots,extra=()):
        entries=[]
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6)as z:
            for directory,prefix in roots:
                for p in sorted(directory.rglob('*')):
                    if p.is_file():
                        name=str(Path(prefix)/p.relative_to(directory));z.write(p,name);entries.append({'file':name,'bytes':p.stat().st_size,'sha256':sha(p)})
            for p,name in extra:
                z.write(p,name);entries.append({'file':name,'bytes':p.stat().st_size,'sha256':sha(p)})
            z.writestr('GEO004_ARCHIVE_MANIFEST.json',json.dumps({'source_commit':source,'files':entries,'budget_usd':0,'unreal_executed':False},indent=2)+'\n')
        assert path.stat().st_size<limits['individual_asset_limit_bytes']
        with zipfile.ZipFile(path)as z:assert z.testzip()is None
    archive(out/'Monterrey_GEO004_Web.zip',[(site,'')])
    archive(out/'Monterrey_GEO004_Terrain_City_QA.zip',[(city,'city'),(terrain,'terrain'),(validation,'qa'),(Path('docs/geo004'),'documentation')],[(inputs/'702825404925_as.zip','source/702825404925_as.zip'),(Path('manifests/geo004-sources.json'),'geo004-sources.json'),(Path('DATA_LICENSES.md'),'DATA_LICENSES.md')])
    tag='geo004-'+source[:12];hosting=gh('api',f'repos/{repository}/git/ref/heads/gh-pages');hosting=json.loads(hosting)['object']['sha']
    if os.environ.get('MOW_VALIDATED_HOST'):assert hosting==os.environ['MOW_VALIDATED_HOST'],'Preserve a newer unexpected deployment'
    assert json.loads((validation/'validation.json').read_text())['source_model_sha256']==world['source_glb_sha256']
    record={'milestone':'GEO-004','source_commit':source,'packager_commit':os.environ['GITHUB_SHA'],'hosting_commit':hosting,'source_glb_sha256':world['source_glb_sha256'],'budget_usd':0,'unreal_executed':False,'source_year':2007,'absolute_accuracy_certified':False,'assets':[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p)}for p in sorted(out.iterdir())]}
    (out/'geo004-release-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    (out/'GEO004_SHA256SUMS.txt').write_text(''.join(sha(p)+'  '+p.name+'\n'for p in sorted(out.iterdir())))
    files=list(out.iterdir());assert len(files)<limits['maximum_assets']
    notes=out/'release-notes.tmp';notes.write_text('GEO-004: MDT LiDAR INEGI 5 m (datos 2007), transformación vertical explícita y correcciones verificadas de plataformas viales. Visor comparativo, GLB, OBJ/MTL por sistema, GeoTIFF y QA. EPV no publicada; estructuras y cimentaciones pendientes de validación independiente. Unreal no ejecutado. US$0.\n\nVisor: https://rawcdn.githack.com/'+repository+'/'+hosting+'/index.html\n')
    # Unique immutable tag. Preserve any existing delivery rather than overwriting.
    existing=subprocess.run(['gh','release','view',tag],capture_output=True,text=True)
    if existing.returncode==0:raise FileExistsError('Preserve existing release '+tag)
    gh('release','create',tag,'--target',source,'--draft','--prerelease','--title','GEO-004 · terreno INEGI y visor comparativo','--notes-file',str(notes))
    for p in files:gh('release','upload',tag,str(p))
    gh('release','edit',tag,'--draft=false','--prerelease','--latest=false')
    with tempfile.TemporaryDirectory(prefix='geo004-download-check-')as temporary:
        gh('release','download',tag,'--dir',temporary)
        for p in files:assert sha(Path(temporary)/p.name)==sha(p)
    record.update(status='passed',all_assets_downloaded_and_hash_verified=True,url=f'https://github.com/{repository}/releases/tag/{tag}')
    Path('artifacts/geo004-release-verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('city','terrain','validation','site','browser','inputs'):p.add_argument('--'+name,required=True)
    a=p.parse_args();publish(a.city,a.terrain,a.validation,a.site,a.browser,a.inputs)

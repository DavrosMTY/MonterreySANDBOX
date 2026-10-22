"""Archive the exact validated hosting commit; upload using the free runner token."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def run(*args,capture=True):
    return subprocess.check_output(args,cwd=ROOT,text=True) if capture else subprocess.run(args,cwd=ROOT,check=True)


def publish():
    config=json.loads((ROOT/'.github/publication/world002-release.json').read_text())
    host,source,tag=config['hosting_commit'],config['source_commit'],config['tag']
    assert len(host)==len(source)==40 and all(c in '0123456789abcdef'for c in host+source)
    report=json.loads((ROOT/'docs/world002/public-verification.json').read_text())
    assert report['status']=='passed' and report['world002']['status']=='passed'
    assert report['tested_url']==f'https://rawcdn.githack.com/DavrosMTY/MonterreySANDBOX/{host}/index.html'
    out=ROOT/'artifacts/world002-release';out.mkdir(parents=True,exist_ok=False)
    for commit in (host,source):run('git','fetch','origin',commit,capture=False)
    world=json.loads(run('git','show',host+':world.json'));assert world['milestone']=='WORLD-002' and not world['synthetic']
    for name in ('app.js','core.js','visual.js','materials.js','decorations.js','background.js','index.html','about.html','style.css'):
        assert run('git','rev-parse',host+':'+name)==run('git','rev-parse',source+':WebViewer/src/'+name)
    browser=json.loads(run('git','show',host+':evidence/browser-report.json'))
    assert browser['status']=='passed' and browser['world002']['status']=='passed' and browser['browser_errors']==[]
    archive=out/'Monterrey_WORLD002_Web.zip'
    run('git','archive','--format=zip','--output='+str(archive),host,capture=False)
    limits=json.loads((ROOT/'manifests/world002-release-limits.json').read_text())
    assert archive.stat().st_size<limits['individual_asset_limit_bytes']
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    record={'milestone':'WORLD-002','source_commit':source,'hosting_commit':host,'source_glb_sha256':world['source_glb_sha256'],
            'archive':{'name':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive)},'unreal_executed':False,
            'paid_services_provisioned':False,'budget_usd':0,'public_browser_workflow':report['workflow_url'],
            'build_workflow':json.loads((ROOT/'docs/world002/ci-verification.json').read_text())['workflow_url'],
            'limits_verification_file':'world002-release-limits.json'}
    (out/'world002-release-manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    (out/'WORLD002_SHA256SUMS.txt').write_text(sha(archive)+'  '+archive.name+'\n')
    (out/'world002-release-limits.json').write_text(json.dumps(limits,indent=2)+'\n')
    metadata=json.loads(run('gh','release','view',tag,'--json','isDraft,targetCommitish,assets'))
    assert metadata['isDraft'] and metadata['targetCommitish']==source,'Preserve any unexpected existing published release'
    files=list(out.iterdir());expected={p.name:p for p in files}
    assert {a['name']for a in metadata['assets']}<=set(expected),'Preserve unexpected assets'
    with tempfile.TemporaryDirectory(prefix='mow-verify-release-')as tmp:
        for item in metadata['assets']:
            run('gh','release','download',tag,'--pattern',item['name'],'--dir',tmp,capture=False)
            assert sha(Path(tmp)/item['name'])==sha(expected[item['name']]),'Preserve differing existing asset'
        existing={a['name']for a in metadata['assets']}
        for p in files:
            if p.name not in existing:run('gh','release','upload',tag,str(p),capture=False)
    run('gh','release','edit',tag,'--draft=false','--prerelease','--latest=false',capture=False)
    with tempfile.TemporaryDirectory(prefix='mow-public-release-')as tmp:
        run('gh','release','download',tag,'--dir',tmp,capture=False)
        for p in files:assert sha(Path(tmp)/p.name)==sha(p),'Published release checksum mismatch'
    record.update(status='passed',url=f'https://github.com/DavrosMTY/MonterreySANDBOX/releases/tag/{tag}',
                  workflow_url='https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],
                  all_assets_downloaded_and_hash_verified=True)
    (out/'release-verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':publish()

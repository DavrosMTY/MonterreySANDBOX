"""Idempotent PR creation and append-only Release publishing via existing gh auth.

Executed by the repository's GitHub Actions runner when the cloud API is blocked.
No merge, force-push, credential export or replacement of existing Release assets.
"""
import argparse
import json
from pathlib import Path
import subprocess

REPOSITORY='DavrosMTY/MonterreySANDBOX'


def invoke(args,check=True):
    result=subprocess.run(['gh',*args],capture_output=True,text=True)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or 'GitHub CLI operation failed')
    return result


def pull_request(body):
    result=invoke(['pr','list','--repo',REPOSITORY,'--base','main','--head','development','--state','open','--json','url'])
    existing=json.loads(result.stdout)
    if existing:return {'status':'existing','url':existing[0]['url']}
    result=invoke(['pr','create','--repo',REPOSITORY,'--base','main','--head','development',
        '--title','Incorporar GEO-001 a GEO-003 / WORLD-001 y flujo de desarrollo en GitHub','--body-file',str(body)])
    return {'status':'created','url':result.stdout.strip()}


def release(directory):
    root=Path(directory);manifest=json.loads((root/'release-manifest.json').read_text())
    sha=manifest['source_commit'];tag='geo003-world001-'+sha[:12]
    visibility=json.loads(invoke(['repo','view',REPOSITORY,'--json','isPrivate']).stdout)
    if visibility['isPrivate']:raise RuntimeError('Publication requires a new quota check after changing repository visibility')
    existing=invoke(['release','view',tag,'--repo',REPOSITORY,'--json','url'],check=False)
    if existing.returncode==0:raise RuntimeError('Release already exists; refusing to replace assets')
    if 'not found' not in existing.stderr.lower() and '404' not in existing.stderr:
        raise RuntimeError(existing.stderr.strip() or 'Cannot verify that release tag is unused')
    files=[]
    for item in manifest['files']:
        path=root/item['file']
        if not path.is_file() or path.stat().st_size>=2*1024**3:raise ValueError('Missing or oversized Release asset')
        import hashlib
        if hashlib.sha256(path.read_bytes()).hexdigest()!=item['sha256']:raise ValueError('Release asset checksum changed')
        files.append(path)
    files.extend([root/'release-manifest.json',root/'SHA256SUMS.txt'])
    if len(files)>1000:raise ValueError('Release asset count exceeds checked GitHub limit')
    invoke(['release','create',tag,*map(str,files),'--repo',REPOSITORY,'--target',sha,
        '--prerelease','--title','Monterrey Open World — GEO-003 / WORLD-001 (graybox candidato)',
        '--notes-file',str(root/'RELEASE_NOTES.md')])
    return {'status':'created','url':f'https://github.com/{REPOSITORY}/releases/tag/{tag}',
            'assets':len(files),'source_commit':sha}


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='operation',required=True)
    pr=sub.add_parser('pr');pr.add_argument('--body',default='.github/publication/initial-pr.md')
    rel=sub.add_parser('release');rel.add_argument('directory')
    a=p.parse_args()
    try:result=pull_request(Path(a.body)) if a.operation=='pr' else release(a.directory)
    except (RuntimeError,ValueError,OSError) as exc:
        message=str(exc).replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print('::error::GitHub publication blocked: '+message,flush=True)
        print(json.dumps({'status':'blocked','operation':a.operation,'reason':str(exc)},ensure_ascii=False));raise SystemExit(2)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()

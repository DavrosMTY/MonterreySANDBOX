"""Publish generated small static hosting assets on an isolated gh-pages branch.

No force push, project branches, cloud resources or workflow artifact storage.
An existing branch must be marked as this generated site before any replacement.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def publish(site, repository):
    site = Path(site).resolve()
    if repository != 'DavrosMTY/MonterreySANDBOX':
        raise ValueError('Unexpected deployment repository')
    if not (site / 'world.json').is_file() or not (site / 'index.html').is_file():
        raise ValueError('Missing validated real world deployment')
    world = json.loads((site / 'world.json').read_text())
    if world.get('synthetic') is not False or world.get('source_milestone') not in ('GEO-003 / WORLD-001','GEO-004'):
        raise ValueError('Only provenance-validated real GEO-003/GEO-004 may be published')
    files = [p for p in site.rglob('*') if p.is_file()]
    if any('.git' in p.relative_to(site).parts or p.is_symlink() for p in files):
        raise ValueError('Unexpected deployment path')
    if sum(p.stat().st_size for p in files) > 50 * 1024**2:
        raise ValueError('Free deployment capped at 50 MiB')
    remote = f'https://github.com/{repository}.git'
    with tempfile.TemporaryDirectory(prefix='mow-free001-deploy-') as tmp:
        path = Path(tmp)
        def git(*args, capture=False):
            # gh's credential helper reads the existing integration/GH_TOKEN; no token in URLs or logs.
            command = ['git', '-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential', *args]
            return subprocess.run(command, cwd=path, check=True, capture_output=capture, text=True)
        git('init', '-b', 'gh-pages')
        git('remote', 'add', 'origin', remote)
        exists = bool(git('ls-remote', '--heads', 'origin', 'gh-pages', capture=True).stdout.strip())
        if exists:
            git('fetch', '--depth=1', 'origin', 'gh-pages')
            git('checkout', '-B', 'gh-pages', 'FETCH_HEAD')
            marker = path / 'free001-deployment.json'
            if not marker.exists() or json.loads(marker.read_text()).get('generator') != 'FREE-001':
                raise ValueError('Existing deployment is not ours; preserve it')
            previous = json.loads(marker.read_text())['managed_files']
            for name in previous:
                target = (path / name).resolve()
                if not target.is_relative_to(path) or '.git' in Path(name).parts:
                    raise ValueError('Invalid previous generated path')
                if target.is_file():
                    target.unlink()
        managed = []
        for source in files:
            name = source.relative_to(site)
            target = path / name
            # Never replace files not owned by the previous generated manifest.
            if target.exists():
                raise FileExistsError(f'Preserve unexpected deployment file: {name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            managed.append(str(name))
        (path / 'free001-deployment.json').write_text(json.dumps({'generator': 'FREE-001',
            'milestone':world['milestone'],'source_glb_sha256': world['source_glb_sha256'], 'managed_files': managed}, indent=2) + '\n')
        git('config', 'user.name', 'Monterrey build automation')
        git('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
        git('add', '--all')
        if not subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=path).returncode:
            print('Static deployment unchanged')
            return
        git('commit', '-m', 'deploy('+world['milestone'].lower()+'): publish validated real geospatial web viewer')
        git('push', 'origin', 'HEAD:refs/heads/gh-pages')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site', required=True)
    p.add_argument('--repository', default='DavrosMTY/MonterreySANDBOX')
    a = p.parse_args()
    publish(a.site, a.repository)

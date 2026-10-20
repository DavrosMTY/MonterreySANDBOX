"""Validate Git's exact publication set and the license-reviewed pilot inventory."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
FORBIDDEN_PARTS={'.venv','__pycache__','.pytest_cache','.cache','Binaries','Intermediate','Saved','DerivedDataCache'}
SECRET_PATTERNS=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
                 re.compile(rb'gh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{40,}')]


def check_paths(paths,inventory):
    inputs={r['path']:r for r in inventory['files']}
    total=0
    for name in paths:
        path=ROOT/name
        if any(p in FORBIDDEN_PARTS for p in Path(name).parts):raise ValueError('Excluded directory in Git: '+name)
        if name.startswith('artifacts/') or (name.startswith('Data/') and name not in inputs and path.name!='.gitkeep'):
            raise ValueError('Unreviewed data or artifact in Git: '+name)
        if path.suffix.lower() in ('.zip','.glb','.blend','.obj','.pbf'):raise ValueError('Large-delivery format in Git: '+name)
        data=path.read_bytes();total+=len(data)
        if len(data)>10*1024**2:raise ValueError('File exceeds small-repository policy: '+name)
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):raise ValueError('Potential credential material in '+name)
        if name in inputs and hashlib.sha256(data).hexdigest()!=inputs[name]['sha256']:raise ValueError('Pilot input checksum changed: '+name)
    if not set(inputs).issubset(paths):raise ValueError('Reviewed pilot inputs are missing from Git')
    return {'status':'passed','tracked_files':len(paths),'total_bytes':total,'license_reviewed_pilot_files':len(inputs),
            'lfs_uploads':False,'large_models_or_archives_in_git':False}


def main():
    names=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
    inventory=json.loads((ROOT/'manifests/pilot-inputs.json').read_text())
    print(json.dumps(check_paths([n for n in names if n],inventory),indent=2))


if __name__=='__main__':main()

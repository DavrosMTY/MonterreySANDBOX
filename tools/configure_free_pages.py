"""Try the authorized free Pages activation; preserve exact permission blockers."""
import json
import os
from pathlib import Path
import subprocess

repo = 'repos/' + os.environ['GITHUB_REPOSITORY']

def api(path, body=None):
    args = ['gh', 'api', repo + path]
    if body is not None:
        args += ['--method', 'POST', '--input', '-']
    r = subprocess.run(args, input=json.dumps(body) if body is not None else None, text=True, capture_output=True)
    return {'exit_code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}

result = {'budget_usd': 0, 'paid_fallback_authorized': False, 'read': api('/pages')}
result['activation'] = result['read'] if not result['read']['exit_code'] else api('/pages', {'source': {'branch': 'gh-pages', 'path': '/'}, 'build_type': 'legacy'})
if not result['activation']['exit_code']:
    result['build'] = api('/pages/builds', {})
else:
    result['blocker'] = 'Pages activation requires the repository permissions documented by GitHub; no paid fallback.'
path = Path('artifacts/free001-site/evidence/pages.json')
path.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))

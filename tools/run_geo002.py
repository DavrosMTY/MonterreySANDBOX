"""One-command GEO-002 acceptance: tests, build/reuse, geometry, geography and real renders."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--terrain',default='Data/unreal/monterrey_centro_single_v3')
    p.add_argument('--urban',default='Data/urban/monterrey_centro_v3')
    p.add_argument('--city-existing',help='Reuse a validated generated model instead of rebuilding')
    p.add_argument('--renders-existing',help='Reuse renders only if their model hashes match')
    a=p.parse_args();artifacts=ROOT/'artifacts';artifacts.mkdir(exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix='geo002-acceptance-',dir=artifacts))
    steps=[]
    def execute(label,args,expected=(0,)):
        with (run/f'{label}.log').open('w',encoding='utf-8') as log:
            result=subprocess.run([str(v) for v in args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        steps.append({'name':label,'exit_code':result.returncode,'expected_exit_codes':list(expected)})
        if result.returncode not in expected:raise RuntimeError(f'{label} failed; see preserved log')
    result={'status':'started','generated_at_utc':datetime.now(timezone.utc).isoformat(),'steps':steps,
            'run_directory':str(run.relative_to(ROOT)),'unreal_executed':False,'windows_build':False}
    try:
        execute('pytest',[sys.executable,'-m','pytest','-q',f'--junitxml={run/"tests.xml"}'])
        suites=ET.parse(run/'tests.xml').getroot()
        result['tests']={k:sum(int(s.get(k,0)) for s in suites.iter('testsuite')) for k in ('tests','errors','failures','skipped')}
        if result['tests']['tests']==0:raise RuntimeError('Zero-test run')
        city=(ROOT/a.city_existing).resolve() if a.city_existing else run/'city'
        if not a.city_existing:
            execute('build',[sys.executable,'-m','GeoPipeline.city','--terrain',a.terrain,'--urban',a.urban,'--output',city])
        execute('geometry',[sys.executable,'-m','GeoPipeline.qa3d',city,'--output',run/'geometry.json'])
        execute('geography',[sys.executable,'tools/audit_geo002.py','--city',city,'--terrain',a.terrain,'--urban',a.urban,'--output',run/'geography.json'])
        execute('unreal',[sys.executable,'tools/run_unreal_geo002.py','--city',city,'--terrain',a.terrain,'--receipt',run/'unreal.json'],expected=(0,2))
        render=(ROOT/a.renders_existing).resolve() if a.renders_existing else run/'renders'
        if not a.renders_existing:
            blender=shutil.which('blender')
            if not blender:raise RuntimeError('Real image acceptance requires Blender; geometry evidence was retained')
            execute('render',[blender,'--background','--factory-startup','--python-exit-code','1','--python',ROOT/'tools/render_city.py',
                              '--','--city',city,'--output',render,'--samples','64','--threads','8'])
        manifest=json.loads((city/'manifest.json').read_text());evidence=json.loads((render/'render_evidence.json').read_text())
        if evidence['input_glb_sha256']!=manifest['glb_sha256'] or evidence['imported_triangle_count']!=manifest['summary']['triangles']:
            raise RuntimeError('Stale or wrong model render evidence')
        if evidence['ai_generated_images'] or evidence['unreal_executed'] or evidence['renderer']!='Blender Cycles CPU':
            raise RuntimeError('Unexpected renderer evidence')
        if {v['name'] for v in evidence['views']}!={'aerial','street','elevated'}:raise RuntimeError('Missing views')
        from PIL import Image
        import numpy as np
        for view in evidence['views']:
            path=render/view['file']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=view['sha256']:raise RuntimeError('Image checksum mismatch')
            with Image.open(path) as im:
                if list(im.size)!=view['resolution'] or np.asarray(im).std()<1:raise RuntimeError('Empty or incorrect render')
        geographic=json.loads((run/'geography.json').read_text())
        if geographic['exported_mesh_crossings_potential_solid_overlap']:
            raise RuntimeError('Potential grade crossings remain in exported model')
        ue_status=json.loads((run/'unreal.json').read_text())
        result.update(status='geospatial_and_3d_acceptance_passed',city_directory=str(city),renders_directory=str(render),
                      model_sha256=manifest['glb_sha256'],summary=manifest['summary'],
                      geometry=json.loads((run/'geometry.json').read_text()),geography={k:v for k,v in geographic.items() if k!='crossings'},
                      render=evidence,unreal=ue_status,unreal_executed=ue_status.get('editor_executed',False),
                      engine_integration_status='editor_receipt_verified' if ue_status.get('world_partition_validated') else 'blocked_pending_UE5_Windows_runner',
                      publication_or_push_performed=False)
    except Exception as exc:
        result.update(status='failed',error=str(exc));raise
    finally:
        (run/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':result['status'],'evidence_directory':str(run)},indent=2))


if __name__=='__main__':main()

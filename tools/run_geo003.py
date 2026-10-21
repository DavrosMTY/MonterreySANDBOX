"""Reproducible WORLD-001 acceptance; separates offline results from UE execution."""
import argparse
from datetime import datetime,timezone
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
    p.add_argument('--city-existing');p.add_argument('--renders-existing')
    p.add_argument('--terrain',default='Data/unreal/monterrey_centro_single_v3')
    p.add_argument('--urban',default='Data/urban/monterrey_centro_v3')
    a=p.parse_args();(ROOT/'artifacts').mkdir(exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix='geo003-acceptance-',dir=ROOT/'artifacts'))
    report={'status':'started','generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'unreal_executed':False,'windows_build':False,'full_world_drivable_certified':False,'steps':[]}
    def execute(label,args,allowed=(0,)):
        with (run/f'{label}.log').open('w') as log:
            r=subprocess.run([str(v) for v in args],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        report['steps'].append({'name':label,'exit_code':r.returncode,'allowed_exit_codes':list(allowed)})
        if r.returncode not in allowed:raise RuntimeError(f'{label} failed; preserved evidence at {run}')
    try:
        execute('tests',[sys.executable,'-m','pytest','-q','--junitxml='+str(run/'tests.xml')])
        xml=ET.parse(run/'tests.xml').getroot()
        report['tests']={k:sum(int(s.get(k,0)) for s in xml.iter('testsuite')) for k in ('tests','failures','errors','skipped')}
        if report['tests']['tests']==0:raise ValueError('No tests executed')
        city=(ROOT/a.city_existing).resolve() if a.city_existing else run/'city'
        if not a.city_existing:execute('generate',[sys.executable,'-m','GeoPipeline.world','--terrain',a.terrain,'--urban',a.urban,'--output',city])
        execute('exports',[sys.executable,'-m','GeoPipeline.qa3d',city,'--output',run/'exports.json'])
        execute('world',[sys.executable,'-m','GeoPipeline.qa_world','--city',city,'--terrain',a.terrain,'--urban',a.urban,'--output',run/'world.json'])
        execute('routes',[sys.executable,'tools/prepare_world_routes.py','--city',city,'--qa',run/'world.json','--output',run/'route'])
        execute('unreal',[sys.executable,'tools/run_unreal_geo003.py','--city',city,'--terrain',a.terrain,'--receipt',run/'unreal.json','--probes',run/'route/traversal_probes.json'],(0,2))
        renders=(ROOT/a.renders_existing).resolve() if a.renders_existing else run/'renders'
        if not a.renders_existing:
            blender=shutil.which('blender')
            if not blender:raise RuntimeError('Real geometry renders require Blender')
            execute('renders',[blender,'--background','--factory-startup','--python-exit-code','1','--python',ROOT/'tools/render_city.py',
                '--','--city',city,'--output',renders,'--samples','64','--threads','8'])
        m=json.loads((city/'manifest.json').read_text());v=json.loads((renders/'render_evidence.json').read_text())
        if v['input_glb_sha256']!=m['glb_sha256'] or v['imported_triangle_count']!=m['summary']['triangles']:raise ValueError('Stale render model')
        if v['ai_generated_images'] or v['unreal_executed'] or v['renderer']!='Blender Cycles CPU':raise ValueError('Unexpected render provenance')
        if {x['name'] for x in v['views']}!={'aerial','street','elevated'}:raise ValueError('Missing actual model views')
        from PIL import Image
        import numpy as np
        for view in v['views']:
            image=renders/view['file']
            if hashlib.sha256(image.read_bytes()).hexdigest()!=view['sha256']:raise ValueError('Changed render image')
            with Image.open(image) as im:
                if list(im.size)!=view['resolution'] or np.asarray(im).std()<1:raise ValueError('Empty render')
        q=json.loads((run/'world.json').read_text());ue=json.loads((run/'unreal.json').read_text())
        if q['crossings_potential_center_solid_overlap']:raise ValueError('Exported grade crossing potential center overlap')
        if q['terrain_unmatched_seam_vertices_at_mm_precision']:raise ValueError('Terrain cell seam mismatch')
        report.update(status='offline_acceptance_passed_with_world_refinement_required',model_sha256=m['glb_sha256'],
            city_directory=str(city),renders_directory=str(renders),unreal=ue,
            motorized_roads_requiring_refinement=q['motorized_roads_requiring_refinement'],
            road_readiness_counts=q['road_readiness_counts'],
            unreal_executed=ue.get('editor_executed',False),
            remaining='See per-road QA and diagnosis. Offline candidate is not runtime traversal approval.')
    except Exception as exc:
        report.update(status='failed',error=str(exc));raise
    finally:
        (run/'acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'evidence_directory':str(run),**report},indent=2))


if __name__=='__main__':main()

"""Validate, compile, import, play, package and launch UE-001; exit 2 means blocked.

No engine installation, service provisioning, registry access or download occurs.
Every invocation needs a new output directory; historical evidence is never reused.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.ue001 import ROOT,PROJECT,MAP,structure,import_plan,engine_install,digest,validate_play_receipt
from tools.audit_ue001 import inventory


def batch_command(script, arguments, host):
    values=[str(script),*map(str,arguments)]
    if host!='Windows':return ['bash',*values]
    if any(any(c in value for c in '&|<>^%!"\r\n') for value in values):raise ValueError('Unsafe batch argument')
    return 'cmd.exe /d /s /c "'+subprocess.list2cmdline(values)+'"'


def execute(name, args, output, env, result, timeout=7200):
    log=output/(name+'.log')
    with log.open('x',encoding='utf-8') as stream:
        try:code=subprocess.run(args,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout).returncode
        except subprocess.TimeoutExpired:
            result['steps'].append({'step':name,'status':'timeout','log':log.name});raise RuntimeError(name+' timed out')
    result['steps'].append({'step':name,'exit_code':code,'log':log.name,'log_sha256':digest(log)})
    if code:raise RuntimeError(name+' failed; see '+str(log))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city',default='Data/city/geo003_world001')
    p.add_argument('--terrain',default='Data/unreal/monterrey_centro_single_v3')
    p.add_argument('--urban',default='Data/urban/monterrey_centro_v3')
    p.add_argument('--probes',required=True)
    p.add_argument('--engine-root',default=os.environ.get('UE_ROOT'))
    p.add_argument('--output',required=True)
    p.add_argument('--through',choices=['validate','compile','import','play','package','all'],default='all')
    a=p.parse_args();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=False)
    result={'schema_version':1,'run_id':uuid.uuid4().hex,'started_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
        'levels':{key:{'status':'not_run'} for key in 'ABCDE'},'steps':[],
        'commercial_target':'Win64','engine_executed':False,'windows_executable_tested':False}
    code=0;phase='A';env=os.environ.copy()
    try:
        (out/'infrastructure.json').write_text(json.dumps(inventory(),indent=2)+'\n',encoding='utf-8')
        plan=import_plan(ROOT/a.city,ROOT/a.terrain,ROOT/a.probes)
        plan_path=out/'import-plan.json';plan_path.write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
        (out/'spawn-candidates.json').write_text(json.dumps(plan['spawn_candidates'],indent=2)+'\n',encoding='utf-8')
        execute('external-tests',[sys.executable,'-m','pytest','-q','--junitxml='+str(out/'tests.xml')],out,env,result,600)
        xml=ET.parse(out/'tests.xml').getroot();suites=list(xml.iter('testsuite'))
        counts={key:sum(int(s.attrib.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}
        if not counts['tests'] or counts['failures'] or counts['errors']:raise RuntimeError('Incomplete external test evidence')
        execute('geometry-qa',[sys.executable,'-m','GeoPipeline.qa3d',str(ROOT/a.city),'--output',str(out/'geometry-qa.json')],out,env,result,600)
        execute('world-qa',[sys.executable,'-m','GeoPipeline.qa_world','--city',str(ROOT/a.city),
            '--terrain',str(ROOT/a.terrain),'--urban',str(ROOT/a.urban),'--output',str(out/'world-qa.json')],out,env,result,600)
        result['levels']['A']={'status':'passed','tests':counts,'plan_sha256':digest(plan_path),
            'cells':len(plan['cells']),'source_parts':plan['source_parts'],'engine_executed':False,
            'geometry_qa_sha256':digest(out/'geometry-qa.json'),'world_qa_sha256':digest(out/'world-qa.json'),
            'scope':'External tests, numeric/provenance preflight and GLB/OBJ/world audits; known WORLD-001 issues remain'}
        phase='B';result['levels']['B']=structure()
        if a.through=='validate':return 0
        phase='C'
        try:engine=engine_install(a.engine_root)
        except (OSError,ValueError) as exc:
            code=2
            for key in 'CDE':result['levels'][key]={'status':'blocked','reason':str(exc)}
            return code
        result['engine_installation']={'version':engine['version'],'platform':engine['platform']}
        compile_args=['MonterreyOpenWorldEditor',engine['platform'],'Development',str(PROJECT),'-WaitMutex','-NoHotReloadFromIDE']
        execute('compile-editor',batch_command(engine['build'],compile_args,platform.system()),out,env,result)
        # Build the runtime target separately: editor compilation cannot certify it.
        compile_args[0]='MonterreyOpenWorld'
        execute('compile-game',batch_command(engine['build'],compile_args,platform.system()),out,env,result)
        result['levels']['C']={'status':'passed','engine_version':'5.6.1','platform':engine['platform'],
            'targets':['MonterreyOpenWorldEditor','MonterreyOpenWorld']}
        if a.through=='compile':return 0
        phase='D';receipt=out/'editor-import.json';content=PROJECT.parent/'Content/Python'
        env.update(MOW_CITY_DIR=str((ROOT/a.city).resolve()),MOW_TERRAIN_DIR=str((ROOT/a.terrain).resolve()),
            MOW_UE_RECEIPT=str(receipt),MOW_MAP_PATH=MAP,MOW_ASSET_ROOT='/Game/UE001',
            MOW_TERRAIN_MODE='static_mesh',MOW_UE001_PLAN=str(plan_path))
        flags=[str(engine['editor']),str(PROJECT),'-unattended','-nosplash','-stdout','-FullStdOutLogOutput']
        result['engine_executed']=True
        execute('import',flags+['-ExecutePythonScript='+str(content/'import_ue001.py')],out,env,result)
        imported=json.loads(receipt.read_text(encoding='utf-8'))
        if imported.get('status')!='ue001_imported_pending_partition' or imported.get('provenance_assets')!=len(plan['cells']) or not imported.get('spawn_collision',{}).get('passed'):
            raise RuntimeError('Editor import receipt incomplete')
        execute('partition',flags+[MAP,'-run=WorldPartitionConvertCommandlet','-ConversionSuffix','-SCCProvider=None','-AllowCommandletRendering'],out,env,result)
        execute('verify-map',flags+['-ExecutePythonScript='+str(content/'verify_ue001.py')],out,env,result)
        loaded=json.loads(receipt.read_text(encoding='utf-8'))
        if loaded.get('status')!='ue001_map_loaded_pending_play' or not loaded.get('world_partition_validated'):
            raise RuntimeError('Converted map receipt incomplete')
        result['map_loaded_in_editor']=True
        if a.through=='import':
            result['levels']['D']={'status':'partial','map_loaded':True,'movement_tested':False};return 0
        def play(name, command):
            native=out/(name+'.json');screenshot=out/(name+'.png');run_id=uuid.uuid4().hex
            execute(name,[*map(str,command),'-unattended','-nosplash','-stdout','-FullStdOutLogOutput',
                '-windowed','-ResX=1280','-ResY=720','-UE001Smoke','-UE001RunId='+run_id,
                '-UE001Receipt='+str(native),'-UE001Screenshot='+str(screenshot)],out,env,result,180)
            return validate_play_receipt(native,screenshot,run_id)
        runtime=play('editor-play',[engine['gui'],PROJECT,MAP+'_WP','-game'])
        result['levels']['D']={'status':'passed','map_loaded':True,'runtime_evidence':runtime,'scope':'Short native game-process walking/running/camera/floor smoke'}
        if a.through=='play':return 0
        phase='E'
        args=['BuildCookRun','-project='+str(PROJECT),'-noP4','-platform='+engine['platform'],
            '-clientconfig=Development','-build','-cook','-map='+MAP+'_WP','-stage','-pak','-iostore',
            '-archive','-archivedirectory='+str(out/'package'),'-unattended','-utf8output']
        execute('package',batch_command(engine['uat'],args,platform.system()),out,env,result)
        if a.through=='package':result['levels']['E']={'status':'partial','packaged':True,'launched':False};return 0
        suffix='.exe' if engine['platform']=='Win64' else ''
        candidates=list((out/'package').rglob('Binaries/'+engine['platform']+'/MonterreyOpenWorld'+suffix))
        if len(candidates)!=1:raise RuntimeError('Cannot identify unique packaged game executable')
        runtime=play('packaged-play',[candidates[0],MAP+'_WP'])
        result['levels']['E']={'status':'passed','platform':engine['platform'],'runtime_evidence':runtime,
            'executable_sha256':digest(candidates[0])}
        result['windows_executable_tested']=engine['platform']=='Win64'
    except Exception as exc:
        result['levels'][phase]={'status':'failed','reason':str(exc)};result['error']=str(exc);code=1
    finally:
        result['finished_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
        (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2))
    return code


if __name__=='__main__':raise SystemExit(main())

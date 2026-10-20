"""Compile/import/convert/verify on a licensed Windows UE5.6 runner, when present."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city', default='Data/city/geo002_v4')
    p.add_argument('--terrain', default='Data/unreal/monterrey_centro_single_v3')
    p.add_argument('--editor', default=os.environ.get('UE_EDITOR'))
    p.add_argument('--receipt', default='artifacts/geo002_unreal_status.json')
    p.add_argument('--map', default='/Game/Maps/GEO002')
    p.add_argument('--asset-root', default='/Game/GEO002')
    p.add_argument('--terrain-mode',choices=['landscape','static_mesh'],default='landscape')
    p.add_argument('--build-hlod',action='store_true')
    p.add_argument('--probes',help='Optional QA-gated WORLD001 trace probes JSON')
    a = p.parse_args()
    receipt = ROOT/a.receipt; receipt.parent.mkdir(parents=True,exist_ok=True)
    editor = a.editor or shutil.which('UnrealEditor-Cmd.exe') or shutil.which('UnrealEditor-Cmd')
    if not editor or not Path(editor).is_file() or platform.system()!='Windows':
        status={'status':'blocked','editor_executed':False,'native_module_compiled':False,
                'landscape_imported':False,'world_partition_validated':False,'hlod_built':False,
                'reason':'A licensed Windows UE5.6 editor and C++ build toolchain are required; unavailable here'}
        receipt.write_text(json.dumps(status,indent=2)+'\n'); print(json.dumps(status,indent=2)); return 2
    editor = Path(editor).resolve(); engine_root = editor.parents[3]
    project = ROOT/'Unreal/MonterreyOpenWorld/MonterreyOpenWorld.uproject'
    build = engine_root/'Engine/Build/BatchFiles/Build.bat'
    if not build.is_file(): raise RuntimeError('Cannot locate Unreal Build.bat')
    if any(char in str(build)+str(project) for char in '&|<>^"\n'):
        raise RuntimeError('Unsupported characters in Windows batch paths')
    if not a.map.startswith('/Game/Maps/') or not a.asset_root.startswith('/Game/'):
        raise RuntimeError('Generated assets must stay under /Game and maps under /Game/Maps')
    env = os.environ.copy()
    env.update(MOW_CITY_DIR=str((ROOT/a.city).resolve()),MOW_TERRAIN_DIR=str((ROOT/a.terrain).resolve()),
               MOW_UE_RECEIPT=str(receipt.resolve()),MOW_MAP_PATH=a.map,MOW_ASSET_ROOT=a.asset_root,
               MOW_TERRAIN_MODE=a.terrain_mode)
    if a.probes:env['MOW_PROBES_FILE']=str((ROOT/a.probes).resolve())
    steps = []
    def execute(name, args):
        with (receipt.parent/f'geo002_ue_{name}.log').open('w',encoding='utf-8') as log:
            result = subprocess.run([str(v) for v in args],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        steps.append({'step':name,'exit_code':result.returncode})
        if result.returncode: raise RuntimeError(f'UE step failed: {name}; see preserved log')
    execute('compile',['cmd.exe','/d','/c',build,'MonterreyOpenWorldEditor','Win64','Development',project,'-WaitMutex','-NoHotReloadFromIDE'])
    content = project.parent/'Content/Python'
    flags = [editor,project,'-unattended','-nosplash','-stdout','-FullStdOutLogOutput']
    execute('import',flags+['-ExecutePythonScript='+str(content/'import_geo002.py')])
    result = json.loads(receipt.read_text())
    if result.get('status')!='imported_pending_world_partition_conversion': raise RuntimeError('Import receipt incomplete')
    # Official converter reads a same-name map INI; preserve existing user configuration.
    source_ini = project.parent/('Content/Maps/WORLD001.ini' if a.map=='/Game/Maps/WORLD001' else 'Content/Maps/GEO002.ini')
    map_ini = project.parent/'Content'/Path(a.map.removeprefix('/Game/')+'.ini')
    if map_ini != source_ini and not map_ini.exists():
        map_ini.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source_ini,map_ini)
    execute('partition',flags+[a.map,'-run=WorldPartitionConvertCommandlet','-ConversionSuffix','-SCCProvider=None','-AllowCommandletRendering'])
    execute('verify',flags+['-ExecutePythonScript='+str(content/'verify_geo002.py')])
    if a.build_hlod:
        execute('hlod',flags+[a.map+'_WP','-run=WorldPartitionBuilderCommandlet','-builder=WorldPartitionHLODsBuilder','-SetupHLODs','-BuildHLODs','-AllowCommandletRendering'])
    result = json.loads(receipt.read_text()); result.update(steps=steps,hlod_built=a.build_hlod)
    receipt.write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2)); return 0


if __name__=='__main__': raise SystemExit(main())

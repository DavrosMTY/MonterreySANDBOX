"""Read-only host inventory; no installation, engine launch or credential discovery."""
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil


def text_file(path):
    try: return Path(path).read_text().strip()
    except OSError: return None


def inventory(workspace=None):
    workspace=Path(workspace or Path(__file__).resolve().parents[1])
    mem={}
    for line in (text_file('/proc/meminfo') or '').splitlines():
        key, value=line.split(':',1)
        if key in ('MemTotal','MemAvailable','SwapTotal'):mem[key]=int(value.split()[0])*1024
    quota=text_file('/sys/fs/cgroup/cpu.max')
    effective=float(quota.split()[0])/int(quota.split()[1]) if quota and not quota.startswith('max') else os.cpu_count()
    memory_limit=text_file('/sys/fs/cgroup/memory.max')
    candidates=[]
    if os.environ.get('UE_EDITOR'):candidates.append(Path(os.environ['UE_EDITOR']))
    if os.environ.get('UE_ROOT'):candidates.extend(Path(os.environ['UE_ROOT'])/'Engine/Binaries'/p for p in ('Win64/UnrealEditor-Cmd.exe','Linux/UnrealEditor-Cmd'))
    for name in ('UnrealEditor','UnrealEditor-Cmd','UnrealEditor.exe','UnrealEditor-Cmd.exe'):
        if shutil.which(name):candidates.append(Path(shutil.which(name)))
    for base in ('/opt','/workspace','/usr/local','C:/Program Files/Epic Games'):
        directory=Path(base)
        if directory.is_dir():
            for engine in directory.iterdir():
                if engine.is_dir():
                    for name in ('Linux/UnrealEditor','Linux/UnrealEditor-Cmd','Win64/UnrealEditor.exe','Win64/UnrealEditor-Cmd.exe'):
                        path=engine/'Engine/Binaries'/name
                        if path.is_file():candidates.append(path)
    tools={name:shutil.which(name) for name in ('g++','clang++','cl','cmake','dotnet','wine','docker','vulkaninfo','nvidia-smi','gh')}
    usage=shutil.disk_usage(workspace)
    return {'checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'os':platform.platform(),'os_release':text_file('/etc/os-release'),
            'logical_cpu_visible':os.cpu_count(),'effective_cpu_quota':effective,
            'memory':mem,'cgroup_memory_limit_bytes':int(memory_limit) if memory_limit and memory_limit!='max' else None,
            'workspace_disk':{'total_bytes':usage.total,'free_bytes':usage.free},
            'gpu_device_nodes':[str(p) for pattern in ('/dev/dri/renderD*','/dev/nvidia[0-9]*') for p in Path('/').glob(pattern.lstrip('/'))],
            'display_configured':bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')),
            'tools':tools,'detected_editor_candidates':sorted({str(p.resolve()) for p in candidates if p.is_file()}),
            'editor_executed':False,'engine_functional_test':'not_attempted_by_inventory',
            'target':'Windows PC','engine_contract':'5.6.1'}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    args=parser.parse_args();target=Path(args.output)
    result=inventory();target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

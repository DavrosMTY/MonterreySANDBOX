"""Publish a source/evidence prerelease; never label this package as a playable game."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.ue001 import ROOT,digest

REPO='DavrosMTY/MonterreySANDBOX'
TAG='ue001-0.1.0-source-preflight'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True);parser.add_argument('--output',required=True)
    parser.add_argument('--publish',action='store_true');a=parser.parse_args()
    evidence=Path(a.evidence);proof=json.loads((evidence/'validation.json').read_text())
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if proof['source_commit']!=commit or proof['source_dirty'] or subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip():
        raise ValueError('Evidence must correspond to this exact clean source commit')
    levels=proof['levels']
    if levels['A']['status']!='passed' or levels['B']['status']!='passed_static_structure':
        raise ValueError('External/static validation did not pass')
    if proof['engine_executed'] or any(levels[key]['status']!='blocked' for key in 'CDE'):
        raise ValueError('This source-preflight release requires explicit engine blockers; use a different release for engine results')
    for step in proof['steps']:
        if step.get('exit_code')!=0 or digest(evidence/step['log'])!=step['log_sha256']:raise ValueError('Evidence log changed')
    if digest(evidence/'import-plan.json')!=levels['A']['plan_sha256']:raise ValueError('Import plan changed')
    if digest(evidence/'geometry-qa.json')!=levels['A']['geometry_qa_sha256'] or digest(evidence/'world-qa.json')!=levels['A']['world_qa_sha256']:
        raise ValueError('QA receipt changed')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
    files=[p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\x00') if p]
    archive=out/'MonterreyOpenWorld_UE001_SOURCES_ONLY.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in files:z.writestr('MonterreyOpenWorld_UE001/'+name,subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT))
        for p in sorted(evidence.iterdir()):
            if p.is_file():z.write(p,'MonterreyOpenWorld_UE001/evidence/UE001/'+p.name)
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('Project ZIP integrity failed')
    payload=[archive]
    for source,target in [('validation.json','UE001_validation.json'),('import-plan.json','UE001_import-plan.json')]:
        shutil.copy2(evidence/source,out/target);payload.append(out/target)
    manifest={'repository':REPO,'tag':TAG,'source_commit':commit,'validation_source_commit':commit,
        'artifact_kind':'source_project_and_external_evidence_only','engine_version_prepared':'5.6.1',
        'engine_executed':False,'cpp_compiled':False,'map_generated':False,'executable_generated':False,
        'levels':{key:value['status'] for key,value in levels.items()},'tests':levels['A']['tests'],
        'source_files':len(files),'files':[{'file':p.name,'bytes':p.stat().st_size,'sha256':digest(p)} for p in payload]}
    m=out/'release-manifest.json';m.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8');payload.append(m)
    sums=out/'SHA256SUMS.txt';sums.write_text(''.join(digest(p)+'  '+p.name+'\n' for p in payload),encoding='utf-8');payload.append(sums)
    notes=out/'RELEASE_NOTES.md'
    notes.write_text('''# UE-001 — proyecto nativo y evidencia externa

**FUENTES SOLAMENTE: no contiene ejecutable, mapa .umap ni capturas de Unreal.**

UE5.6.1: Character/GameMode/HUD C++, cámara, caminar/correr/saltar, cápsula,
spawn/iluminación preparados, procedencia por 279 sectores y automatización
build/importación/World Partition/juego/cooking. No se instaló ni ejecutó UE.

A: suite externa y QA GLB/407 OBJ aprobados. B: estructura estática aprobada;
sin UHT/APIs UE verificadas. C/D/E: bloqueados por ausencia de engine/toolchain.
El ZIP incluye proyecto, piloto licenciado, logs/JUnit, auditorías y plan.
No incluye Unreal, dependencias, cachés ni modelos nuevos. Los modelos GEO-003
se recuperan automáticamente con SHA256 fijo desde su Release anterior.

Código y evidencia de este runner: `'''+commit+'''`.
Ver release-manifest.json, UE001_validation.json y SHA256SUMS.txt.
PR: https://github.com/DavrosMTY/MonterreySANDBOX/pull/2, sin merge automático.
Siguiente requisito: runner Windows con UE5.6.1 licenciado, VS2022/SDK y GPU.
''',encoding='utf-8')
    if a.publish:
        repo=json.loads(subprocess.check_output(['gh','repo','view',REPO,'--json','isPrivate'],text=True))
        if repo['isPrivate']:raise ValueError('Quota policy requires this repository to remain public')
        policy=json.loads((ROOT/'manifests/github-storage-policy.json').read_text())
        if len(payload)>policy['release_max_assets'] or any(p.stat().st_size>=policy['release_max_asset_bytes_exclusive'] for p in payload):raise ValueError('Release limit exceeded')
        existing=subprocess.run(['gh','release','view',TAG,'--repo',REPO,'--json','url'],capture_output=True,text=True)
        if existing.returncode==0:raise ValueError('Release exists; refusing replacement')
        if 'not found' not in existing.stderr.lower() and '404' not in existing.stderr:raise RuntimeError(existing.stderr)
        subprocess.run(['gh','release','create',TAG,*map(str,payload),'--repo',REPO,'--target',commit,'--prerelease',
            '--title','UE-001 — proyecto nativo UE5.6.1 (fuentes, sin ejecutable)','--notes-file',str(notes)],check=True)
    print(json.dumps({'tag':TAG,'source_commit':commit,'assets':len(payload),'published':a.publish}))


if __name__=='__main__':main()

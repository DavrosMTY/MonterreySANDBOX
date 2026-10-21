"""Engine-independent UE-001 contracts, import preflight and evidence validation."""
import configparser
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT/'Unreal/MonterreyOpenWorld/MonterreyOpenWorld.uproject'
ENGINE_VERSION = (5, 6, 1)
MAP = '/Game/Maps/UE001_Centro'
SYSTEMS = {'Landscape','Buildings','Roads','Sidewalks','Bridges','Tunnels'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_file(root, relative, expected):
    root=Path(root).resolve();path=(root/relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Source escapes root or is missing: '+relative)
    if digest(path)!=expected:raise ValueError('Source checksum mismatch: '+relative)
    return path


def vector(value, length=3):
    if not isinstance(value,list) or len(value)!=length or not all(isinstance(x,(float,int)) and math.isfinite(x) for x in value):
        raise ValueError('Invalid numeric coordinate vector')
    return value


def obj_geometry(path):
    bounds=[[math.inf]*3,[-math.inf]*3];names=[];vertices=0
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            if line.startswith('v '):
                values=vector([float(x) for x in line.split()[1:]])
                vertices+=1
                for i in range(3):bounds[0][i]=min(bounds[0][i],values[i]);bounds[1][i]=max(bounds[1][i],values[i])
            elif line.startswith('o '):names.append(line[2:].strip())
    if not vertices:raise ValueError('Empty OBJ geometry')
    return bounds,names


def import_plan(city, terrain, probes):
    """Check actual OBJ vertices/IDs/transforms, not only manifest declarations."""
    city=Path(city);terrain=Path(terrain)
    m=json.loads((city/'manifest.json').read_text(encoding='utf-8'))
    t=json.loads((terrain/'manifest.json').read_text(encoding='utf-8'))
    if m.get('milestone')!='GEO-003 / WORLD-001' or m.get('synthetic'):
        raise ValueError('UE-001 requires the real WORLD-001 pilot')
    if m['source_crs']!='EPSG:32614' or m['source_vertical_datum']!='EGM2008':
        raise ValueError('Unsupported geographic contract')
    if digest(terrain/'manifest.json')!=m['input_terrain_manifest_sha256']:
        raise ValueError('Terrain provenance changed')
    if t['source_vertical_datum']!=m['source_vertical_datum'] or t['center_easting_northing_m']!=m['center_easting_northing_m'] or t['extent_m']!=m['extent_m']:
        raise ValueError('Terrain/city origin, extent or datum differs')
    if m['unreal_enu_scale']!=[100,-100,100]:raise ValueError('Unreal units/axes changed')
    source_file(city,m['glb'],m['glb_sha256'])
    source_file(city,m['pcg_buildings_csv'],m['pcg_csv_sha256'])
    source_file(city,'road_semantics.json',m['road_semantics_sha256'])
    for item in m['correction_layer_files']+m['auxiliary_files']:source_file(city,item['file'],item['sha256'])
    parts={p['name']:p for p in m['mesh_parts']}
    if len(parts)!=len(m['mesh_parts']):raise ValueError('Duplicate source part identifiers')
    covered=set();cells=[];names=set();max_error=0.
    for cell in m['ue_system_cells']:
        name=cell['name']
        if name in names or not re.fullmatch(r'[A-Za-z0-9_]+',name):raise ValueError('Invalid/duplicate sector name')
        names.add(name)
        if cell['system'] not in SYSTEMS:raise ValueError('Unknown system')
        path=source_file(city,cell['file'],cell['sha256'])
        source_file(city,cell['material_file'],cell['material_sha256'])
        translation=vector(cell['position_unreal_cm']);bounds,objects=obj_geometry(path)
        if sorted(objects)!=sorted(cell['source_mesh_names']):raise ValueError('OBJ source identifiers changed')
        expected=cell['bounds_local_unreal_cm']
        vector(expected[0]);vector(expected[1])
        error=max(abs(bounds[j][i]-expected[j][i]) for j in range(2) for i in range(3))
        if error>.2:raise ValueError('OBJ unit/axis/bounds mismatch')
        max_error=max(max_error,error)
        source_ids=set()
        for part_name in objects:
            if part_name not in parts or part_name in covered:raise ValueError('Missing/duplicated source part')
            part=parts[part_name];covered.add(part_name)
            if part['system']!=cell['system']:raise ValueError('System separation changed')
            if part.get('osm_id'):source_ids.add(part['osm_id'])
            source_ids.update(part.get('source_road_ids',[]))
            enu=part['bounds_enu_m'];world=[[enu[0][0]*100,-enu[1][1]*100,enu[0][2]*100],
                [enu[1][0]*100,-enu[0][1]*100,enu[1][2]*100]]
            if any(world[0][i]<bounds[0][i]+translation[i]-.2 or world[1][i]>bounds[1][i]+translation[i]+.2 for i in range(3)):
                raise ValueError('Actor transform changes geographic placement')
        cells.append({**cell,'source_ids':sorted(source_ids),'actor_scale':[1.,1.,1.],
            'actor_rotation_degrees':[0.,0.,0.]})
    if covered!=set(parts) or {c['system'] for c in cells}!=SYSTEMS:raise ValueError('Incomplete WORLD-001 coverage')
    probe_data=json.loads(Path(probes).read_text(encoding='utf-8'))
    if probe_data['model_sha256']!=m['glb_sha256'] or not probe_data['probes']:raise ValueError('Spawn candidates refer to another/empty model')
    for p in probe_data['probes']:vector(p['position_unreal_cm'])
    return {'schema_version':1,'engine_version':'5.6.1','source_manifest_sha256':digest(city/'manifest.json'),
        'model_sha256':m['glb_sha256'],'terrain_manifest_sha256':digest(terrain/'manifest.json'),
        'horizontal_crs':'EPSG:32614','vertical_datum':'EGM2008',
        'center_easting_northing_m':m['center_easting_northing_m'],'extent_m':m['extent_m'],
        'unreal_units_per_grid_metre':100,'axes':'X east / Y south / Z up',
        'terrain_mode':'excavated_static_mesh','map':MAP,'partitioned_map':MAP+'_WP',
        'asset_root':'/Game/UE001','cells':cells,'source_parts':len(parts),'obj_max_bounds_error_cm':max_error,
        'spawn_candidates_sha256':digest(probes),'spawn_candidates':probe_data,
        'spawn_collision_verified':False,'editor_import_executed':False,
        'data_licenses':'Copernicus GLO-30 and OSM ODbL; see DATA_LICENSES.md'}


def structure(project=PROJECT):
    project=Path(project);directory=project.parent;m=json.loads(project.read_text(encoding='utf-8'))
    if m.get('FileVersion')!=3 or m.get('EngineAssociation')!='5.6':raise ValueError('Wrong engine association/descriptor')
    if m['Modules']!=[{'Name':'MonterreyOpenWorld','Type':'Runtime','LoadingPhase':'Default'}]:raise ValueError('Runtime module descriptor mismatch')
    plugins={p['Name']:p for p in m['Plugins']}
    for name in ('PythonScriptPlugin','EditorScriptingUtilities','MonterreyGeo','PCG','GeoReferencing'):
        if not plugins.get(name,{}).get('Enabled'):raise ValueError('Missing plugin '+name)
    for name in ('PythonScriptPlugin','EditorScriptingUtilities'):
        if plugins[name].get('TargetAllowList')!=['Editor']:raise ValueError('Editor-only dependency leaks into game')
    required=['Source/MonterreyOpenWorld.Target.cs','Source/MonterreyOpenWorldEditor.Target.cs',
        'Source/MonterreyOpenWorld/MonterreyOpenWorld.Build.cs','Source/MonterreyOpenWorld/MonterreyOpenWorld.cpp',
        'Source/MonterreyOpenWorld/Public/MonterreyExplorerCharacter.h',
        'Source/MonterreyOpenWorld/Public/MonterreyExplorerGameMode.h',
        'Source/MonterreyOpenWorld/Public/MonterreySectorMetadata.h',
        'Source/MonterreyOpenWorld/Public/MonterreyBuildingRow.h',
        'Config/DefaultInput.ini','Content/Maps/UE001_Centro.ini','Content/Python/import_ue001.py']
    for name in required:
        if not (directory/name).is_file():raise ValueError('Missing project file '+name)
    for header in (directory/'Source').rglob('*.h'):
        lines=header.read_text().splitlines();includes=[line for line in lines if line.startswith('#include')]
        if any('GENERATED_BODY' in line for line in lines) and (not includes or '.generated.h"' not in includes[-1]):raise ValueError('UHT generated include order: '+header.name)
    plugin=directory/'Plugins/MonterreyGeo/MonterreyGeo.uplugin';p=json.loads(plugin.read_text())
    if any(x['Type']!='Editor' for x in p['Modules']):raise ValueError('Editor plugin exposed to runtime')
    config=configparser.ConfigParser(strict=False);config.read(directory/'Config/DefaultEngine.ini')
    maps=config['/Script/EngineSettings.GameMapsSettings']
    if maps['GameDefaultMap']!=MAP+'_WP' or maps['GlobalDefaultGameMode']!='/Script/MonterreyOpenWorld.MonterreyExplorerGameMode':raise ValueError('Startup map/game mode mismatch')
    return {'status':'passed_static_structure','descriptor':str(project.relative_to(ROOT)) if project.is_relative_to(ROOT) else str(project),
        'engine_version':'5.6.1','editor_executed':False,'uht_executed':False,'cpp_compiled':False,
        'maps_generated':False,'scope':'Descriptor, files, plugin boundaries, generated-header order and startup configuration; not UE API validation'}


def engine_install(root, host=None):
    host=host or platform.system()
    if host not in ('Windows','Linux'):raise ValueError('Unsupported build host')
    if not root:raise FileNotFoundError('No licensed UE_ROOT supplied; no engine is downloaded automatically')
    root=Path(root).resolve();version=json.loads((root/'Engine/Build/Build.version').read_text())
    actual=tuple(version[k] for k in ('MajorVersion','MinorVersion','PatchVersion'))
    if actual!=ENGINE_VERSION:raise ValueError('Expected UE 5.6.1; installed version is '+'.'.join(map(str,actual)))
    target='Win64' if host=='Windows' else 'Linux'
    suffix='.exe' if host=='Windows' else ''
    editor=root/'Engine/Binaries'/target/('UnrealEditor-Cmd'+suffix)
    gui=root/'Engine/Binaries'/target/('UnrealEditor'+suffix)
    batch=root/'Engine/Build/BatchFiles';build=batch/('Build.bat' if host=='Windows' else 'Linux/Build.sh')
    uat=batch/('RunUAT.bat' if host=='Windows' else 'RunUAT.sh')
    for path in (editor,gui,build,uat):
        if not path.is_file():raise FileNotFoundError('Incomplete engine installation: '+str(path))
    return {'root':root,'version':version,'editor':editor,'gui':gui,'build':build,'uat':uat,'platform':target}


def validate_play_receipt(path, screenshot, run_id):
    result=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if result.get('run_id')!=run_id:raise ValueError('Stale or unrelated runtime receipt')
    if result.get('status')!='passed' or not result.get('world_partition') or not result.get('render_viewport'):
        raise ValueError('Runtime did not approve movement/map/rendering')
    if not result.get('engine_version','').startswith('5.6.1-') or 'UE001_Centro_WP' not in result.get('map',''):
        raise ValueError('Wrong runtime engine/map')
    if result.get('walk_distance_cm',0)<=50 or result.get('run_distance_cm',0)<=80:raise ValueError('No measured walking/running')
    png=Path(screenshot).read_bytes()
    if png[:8]!=b'\x89PNG\r\n\x1a\n' or len(png)<24 or min(struct.unpack('>II',png[16:24]))<128:
        raise ValueError('No authentic-size PNG captured by the runtime')
    return {**result,'screenshot_sha256':digest(screenshot),'receipt_sha256':digest(path)}

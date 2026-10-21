"""External contract tests only. These never emulate a compiled Unreal project."""
import copy
import json
from pathlib import Path

import pytest

from tools.ue001 import ROOT,PROJECT,digest,import_plan,structure,engine_install,validate_play_receipt
from tools.run_ue001 import batch_command


@pytest.fixture
def miniature_world(tmp_path):
    """Six tiny descriptor fixtures for corruption tests, not geographic evidence."""
    city=tmp_path/'city';city.mkdir();terrain=tmp_path/'terrain';terrain.mkdir()
    t={'source_vertical_datum':'EGM2008','center_easting_northing_m':[360000,2839000],'extent_m':2000}
    (terrain/'manifest.json').write_text(json.dumps(t))
    for name in ('city.glb','points.csv','road_semantics.json'):(city/name).write_text('contract fixture\n')
    cells=[];parts=[]
    for i,system in enumerate(('Landscape','Buildings','Roads','Sidewalks','Bridges','Tunnels')):
        name=system+'_0_0';part='part_'+str(i)
        (city/(name+'.obj')).write_text('o '+part+'\nv 0 0 50000\nv 100 0 50000\nv 0 100 50000\nf 1 2 3\n')
        (city/(name+'.mtl')).write_text('newmtl fixture\n')
        cells.append({'name':name,'system':system,'cell':[0,0],'file':name+'.obj','sha256':digest(city/(name+'.obj')),
            'material_file':name+'.mtl','material_sha256':digest(city/(name+'.mtl')),'source_mesh_names':[part],
            'position_unreal_cm':[1000,2000,0],'bounds_local_unreal_cm':[[0,0,50000],[100,100,50000]]})
        parts.append({'name':part,'system':system,'bounds_enu_m':[[10,-21,500],[11,-20,500]],'source_road_ids':['way/'+str(i)]})
    m={'milestone':'GEO-003 / WORLD-001','synthetic':False,**t,'source_crs':'EPSG:32614',
       'unreal_enu_scale':[100,-100,100],'input_terrain_manifest_sha256':digest(terrain/'manifest.json'),
       'glb':'city.glb','glb_sha256':digest(city/'city.glb'),'pcg_buildings_csv':'points.csv',
       'pcg_csv_sha256':digest(city/'points.csv'),'road_semantics_sha256':digest(city/'road_semantics.json'),
       'correction_layer_files':[],'auxiliary_files':[],'ue_system_cells':cells,'mesh_parts':parts}
    probes=tmp_path/'probes.json';probes.write_text(json.dumps({'model_sha256':m['glb_sha256'],
        'probes':[{'road_id':'way/0','position_unreal_cm':[1000,2000,50000]}]}))
    def write(): (city/'manifest.json').write_text(json.dumps(m))
    write();return city,terrain,probes,m,write


def test_plan_preserves_all_systems_ids_and_positions_without_approving_spawn(miniature_world):
    city,terrain,probes,_,_=miniature_world
    p=import_plan(city,terrain,probes)
    assert p['source_parts']==6 and len(p['cells'])==6
    assert p['cells'][0]['position_unreal_cm']==[1000,2000,0]
    assert p['cells'][0]['source_ids']==['way/0']
    assert p['cells'][0]['actor_scale']==[1,1,1]
    assert not p['spawn_collision_verified'] and not p['editor_import_executed']


@pytest.mark.parametrize('corruption',['checksum','axis','transform','part','sector','datum','nan','synthetic','missing_system'])
def test_preflight_rejects_independent_source_or_coordinate_corruption(miniature_world,corruption):
    city,terrain,probes,m,write=miniature_world
    if corruption=='checksum':(city/m['ue_system_cells'][0]['file']).write_text('tampered')
    if corruption=='axis':m['unreal_enu_scale']=[100,100,100]
    if corruption=='transform':m['ue_system_cells'][0]['position_unreal_cm'][0]+=1000
    if corruption=='part':m['ue_system_cells'][0]['source_mesh_names']=['unknown']
    if corruption=='sector':m['ue_system_cells'][0]['name']=m['ue_system_cells'][1]['name']
    if corruption=='datum':m['source_vertical_datum']='ellipsoidal'
    if corruption=='nan':m['ue_system_cells'][0]['position_unreal_cm'][0]=float('nan')
    if corruption=='synthetic':m['synthetic']=True
    if corruption=='missing_system':m['ue_system_cells'].pop()
    write()
    with pytest.raises(ValueError):import_plan(city,terrain,probes)


def test_path_escape_rejected_even_with_a_matching_hash(miniature_world,tmp_path):
    city,terrain,probes,m,write=miniature_world
    outside=tmp_path/'outside.obj';outside.write_bytes((city/m['ue_system_cells'][0]['file']).read_bytes())
    m['ue_system_cells'][0]['file']='../outside.obj';write()
    with pytest.raises(ValueError,match='escapes'):import_plan(city,terrain,probes)


def test_spawn_candidates_must_belong_to_this_model(miniature_world):
    city,terrain,probes,_,_=miniature_world
    p=json.loads(probes.read_text());p['model_sha256']='0'*64;probes.write_text(json.dumps(p))
    with pytest.raises(ValueError,match='Spawn candidates'):import_plan(city,terrain,probes)


def test_native_project_static_structure_explicitly_does_not_certify_cpp_or_maps():
    result=structure()
    assert result['status']=='passed_static_structure'
    assert not result['cpp_compiled'] and not result['uht_executed'] and not result['maps_generated']


def test_editor_plugins_cannot_be_accidentally_enabled_in_packaged_game(tmp_path):
    m=json.loads(PROJECT.read_text());m['Plugins'][0].pop('TargetAllowList')
    project=tmp_path/PROJECT.name;project.write_text(json.dumps(m))
    with pytest.raises(ValueError,match='Editor-only'):structure(project)


def test_wrong_patch_rejected_before_engine_execution(tmp_path):
    build=tmp_path/'Engine/Build';build.mkdir(parents=True)
    (build/'Build.version').write_text(json.dumps({'MajorVersion':5,'MinorVersion':6,'PatchVersion':2}))
    with pytest.raises(ValueError,match='5.6.1'):engine_install(tmp_path,'Windows')


def test_missing_engine_is_a_blocker_and_never_downloads_one():
    with pytest.raises(FileNotFoundError,match='No licensed'):engine_install(None,'Linux')


def test_stale_runtime_receipt_rejected_before_a_screenshot_can_count(tmp_path):
    path=tmp_path/'runtime.json';path.write_text(json.dumps({'status':'passed','run_id':'old'}))
    with pytest.raises(ValueError,match='Stale'):validate_play_receipt(path,tmp_path/'absent.png','new')


def test_map_load_without_movement_cannot_approve_runtime(tmp_path):
    path=tmp_path/'runtime.json';path.write_text(json.dumps({'status':'passed','run_id':'now',
        'world_partition':True,'render_viewport':True,'engine_version':'5.6.1-test','map':'UE001_Centro_WP'}))
    with pytest.raises(ValueError,match='walking/running'):validate_play_receipt(path,tmp_path/'absent.png','now')


def test_batch_paths_with_shell_injection_are_rejected():
    with pytest.raises(ValueError):batch_command('C:/UE/Build.bat',['a&b'],'Windows')
    assert batch_command('/UE/Build.sh',['path with spaces'],'Linux')==['bash','/UE/Build.sh','path with spaces']


def test_release_extraction_rejects_traversal_and_writes_nothing(tmp_path):
    import zipfile
    from tools.fetch_ue001_world import extract_world,PREFIX
    archive=tmp_path/'bad.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(PREFIX+'../../escape','malicious fixture')
    with pytest.raises(ValueError,match='Unsafe ZIP path'):extract_world(archive,tmp_path/'out',digest(archive))
    assert not (tmp_path/'out').exists() and not (tmp_path/'escape').exists()


def test_release_extraction_cannot_overwrite_existing_work(tmp_path):
    from tools.fetch_ue001_world import extract_world
    out=tmp_path/'existing';out.mkdir();(out/'user.txt').write_text('preserve')
    with pytest.raises(FileExistsError):extract_world(tmp_path/'missing.zip',out)
    assert (out/'user.txt').read_text()=='preserve'


def test_release_extraction_ignores_old_scripts_and_extracts_only_pinned_data(tmp_path):
    import zipfile
    from tools.fetch_ue001_world import extract_world,PREFIX,PROBES
    archive=tmp_path/'inputs.zip'
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr(PREFIX+'manifest.json','{}');z.writestr(PROBES,'{}')
        z.writestr('MonterreyOpenWorld/tools/old-script.py','raise Exception()')
    result=extract_world(archive,tmp_path/'out',digest(archive))
    assert result['files_extracted']==2
    assert not list((tmp_path/'out').rglob('*.py'))

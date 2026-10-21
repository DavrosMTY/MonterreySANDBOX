"""Executed only by the real UE5.6.1 editor after external preflight and C++ build."""
import hashlib
import json
import math
import os
from pathlib import Path
import runpy

import unreal


def main():
    plan_path=Path(os.environ['MOW_UE001_PLAN'])
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    receipt=Path(os.environ['MOW_UE_RECEIPT'])
    city=Path(os.environ['MOW_CITY_DIR'])
    if hashlib.sha256((city/'manifest.json').read_bytes()).hexdigest()!=plan['source_manifest_sha256']:
        raise RuntimeError('Preflight plan is stale')
    # This shared importer refuses overwrites, imports all excavated system cells,
    # verifies bounds, configures collision and stores the geographic DataAsset.
    runpy.run_path(str(Path(__file__).with_name('import_geo002.py')),run_name='__main__')
    result=json.loads(receipt.read_text(encoding='utf-8'))
    try:
        actors=unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        cells={c['file']:c for c in plan['cells']}
        for record in result['assets']:
            cell=cells[record['source']]
            provenance={key:plan[key] for key in ('source_manifest_sha256','model_sha256','horizontal_crs',
                'vertical_datum','center_easting_northing_m','axes','unreal_units_per_grid_metre','data_licenses')}
            provenance.update(cell=cell)
            mesh=unreal.load_asset(record['asset'])
            if not unreal.MonterreyGeoLibrary.set_sector_provenance(mesh,json.dumps(provenance)):
                raise RuntimeError('Cookable source provenance could not be attached')
        # Native floor ray + actual capsule overlap must succeed before any PlayerStart.
        candidates=plan_path.with_name('spawn-candidates.json')
        spawn=json.loads(unreal.MonterreyGeoLibrary.find_explorer_spawn(str(candidates)))
        if not spawn.get('passed') or not spawn.get('capsule_overlap_checked'):
            raise RuntimeError('No collision-validated spawn: '+json.dumps(spawn))
        position=spawn['position_unreal_cm']
        start=actors.spawn_actor_from_class(unreal.PlayerStart,unreal.Vector(*position))
        start.set_actor_label('UE001_CollisionValidatedSpawn')
        start.set_editor_property('tags',[unreal.Name('UE001_SafeSpawn')])
        start.set_editor_property('is_spatially_loaded',False)
        probes=plan['spawn_candidates']['probes'];i=spawn['candidate_index']
        next_position=next((p['position_unreal_cm'] for p in probes[i+1:]
            if math.dist(p['position_unreal_cm'][:2],position[:2])>10),[position[0]+100,position[1],position[2]])
        yaw=math.degrees(math.atan2(next_position[1]-position[1],next_position[0]-position[0]))
        start.set_actor_rotation(unreal.Rotator(0,yaw,0),False)
        sun=actors.spawn_actor_from_class(unreal.DirectionalLight,unreal.Vector(0,0,100000))
        sun.set_actor_rotation(unreal.Rotator(-45,-30,0),False)
        light=sun.get_component_by_class(unreal.DirectionalLightComponent)
        light.set_editor_property('intensity',40000.)
        light.set_editor_property('atmosphere_sun_light',True)
        light.set_mobility(unreal.ComponentMobility.MOVABLE)
        sky=actors.spawn_actor_from_class(unreal.SkyLight,unreal.Vector(0,0,100000))
        sky_component=sky.get_component_by_class(unreal.SkyLightComponent)
        sky_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        sky_component.set_editor_property('real_time_capture',True)
        atmosphere=actors.spawn_actor_from_class(unreal.SkyAtmosphere,unreal.Vector(0,0,0))
        for actor in (sun,sky,atmosphere):actor.set_editor_property('is_spatially_loaded',False)
        world=unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        mode=unreal.load_class(None,'/Script/MonterreyOpenWorld.MonterreyExplorerGameMode')
        if not mode:raise RuntimeError('Native exploration GameMode unavailable')
        world.get_world_settings().set_editor_property('default_game_mode',mode)
        if not unreal.EditorLoadingAndSavingUtils.save_map(world,plan['map']):raise RuntimeError('Map save failed')
        if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True):raise RuntimeError('Asset save failed')
        result.update(status='ue001_imported_pending_partition',spawn_collision=spawn,
            native_game_mode='/Script/MonterreyOpenWorld.MonterreyExplorerGameMode',
            provenance_assets=len(result['assets']),lighting_created=True,gameplay_tested=False)
    except Exception as exc:
        result.update(status='failed',error=str(exc));raise
    finally:
        receipt.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


main()

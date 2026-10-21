"""Prepared UE5.6 editor automation; NOT executed in the cloud machine.

Invoked by tools/run_unreal_geo002.py with standard-library-only environment input.
Fails rather than accepting an import whose numeric axes or units changed.
"""
import hashlib
import json
import os
from pathlib import Path

import unreal


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    city = Path(os.environ['MOW_CITY_DIR']).resolve()
    terrain = Path(os.environ['MOW_TERRAIN_DIR']).resolve()
    receipt = Path(os.environ['MOW_UE_RECEIPT'])
    asset_root = os.environ.get('MOW_ASSET_ROOT', '/Game/GEO002')
    map_path = os.environ.get('MOW_MAP_PATH', '/Game/Maps/GEO002')
    terrain_mode = os.environ.get('MOW_TERRAIN_MODE', 'landscape')
    result = {'status':'started','editor_executed':True,'native_module_compiled':hasattr(unreal,'MonterreyGeoLibrary'),
              'city_manifest_sha256':digest(city/'manifest.json'),'landscape_imported':False,
              'world_partition_validated':False,'windows_game_build':False,'assets':[]}
    try:
        if not result['native_module_compiled']: raise RuntimeError('Native GEO plugin is unavailable')
        m = json.loads((city/'manifest.json').read_text(encoding='utf-8'))
        is_world = m.get('milestone') == 'GEO-003 / WORLD-001'
        if is_world and terrain_mode != 'static_mesh':
            raise RuntimeError('WORLD001 requires excavated static terrain; uncut Landscape would close tunnels')
        t = json.loads((terrain/'manifest.json').read_text(encoding='utf-8'))
        if t['schema_version'] != 3 or t['source_vertical_datum'] != m['source_vertical_datum']:
            raise RuntimeError('Terrain schema/datum mismatch')
        if digest(city/m['glb']) != m['glb_sha256']: raise RuntimeError('GLB provenance changed')
        if digest(city/m['pcg_buildings_csv']) != m['pcg_csv_sha256']: raise RuntimeError('PCG CSV provenance changed')
        if m['extent_m'] != t['extent_m'] or m['center_easting_northing_m'] != t['center_easting_northing_m']:
            raise RuntimeError('Terrain/city origins differ')
        if unreal.EditorAssetLibrary.does_asset_exist(map_path) or unreal.EditorAssetLibrary.list_assets(asset_root, recursive=True):
            raise RuntimeError('Refusing to overwrite an existing map or populated asset directory')
        for tile in t['tiles']:
            name = tile['r16']; path = (terrain/name).resolve()
            if not path.is_relative_to(terrain) or path.stat().st_size != 505*505*2 or digest(path) != tile['r16_sha256']:
                raise RuntimeError('Landscape source bytes failed preflight')
        world = unreal.EditorLoadingAndSavingUtils.new_blank_map(False)
        if world is None: raise RuntimeError('Could not create editor world')
        tasks = m['ue_system_cells'] if is_world else m['ue_cells']+(m['ue_terrain_cells'] if terrain_mode=='static_mesh' else [])
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        actor_tools = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        mesh_tools = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
        nanite = []
        for cell in tasks:
            source = (city/cell['file']).resolve()
            if not source.is_relative_to(city) or digest(source) != cell['sha256']:
                raise RuntimeError('OBJ checksum or path changed')
            if digest(city/cell['material_file']) != cell['material_sha256']:
                raise RuntimeError('MTL checksum changed')
            options = unreal.FbxImportUI()
            options.set_editor_property('import_mesh', True)
            options.set_editor_property('import_as_skeletal', False)
            options.set_editor_property('import_materials', True)
            options.set_editor_property('import_textures', False)
            options.set_editor_property('mesh_type_to_import', unreal.FBXImportType.FBXIT_STATIC_MESH)
            options.set_editor_property('automated_import_should_detect_type', False)
            data = options.get_editor_property('static_mesh_import_data')
            for key, value in [('combine_meshes',True),('convert_scene',False),('convert_scene_unit',False),
                               ('force_front_x_axis',False),('import_uniform_scale',1.),
                               ('transform_vertex_to_absolute',True),('bake_pivot_in_vertex',False)]:
                data.set_editor_property(key,value)
            task = unreal.AssetImportTask()
            task.set_editor_property('filename',str(source))
            destination=asset_root+'/'+cell.get('system','Cells')+'/'+cell['name'] if is_world else asset_root+'/'+cell['name']
            task.set_editor_property('destination_path',destination)
            task.set_editor_property('destination_name',cell['name'])
            task.set_editor_property('factory',unreal.FbxFactory())
            task.set_editor_property('options',options)
            task.set_editor_property('automated',True); task.set_editor_property('replace_existing',False)
            task.set_editor_property('save',True)
            asset_tools.import_asset_tasks([task])
            meshes = [obj for obj in task.get_objects() if isinstance(obj,unreal.StaticMesh)]
            if len(meshes) != 1: raise RuntimeError('Expected one combined static mesh per cell')
            mesh = meshes[0]; actual = mesh.get_bounding_box()
            values = [[actual.min.x,actual.min.y,actual.min.z],[actual.max.x,actual.max.y,actual.max.z]]
            error = max(abs(values[j][i]-cell['bounds_local_unreal_cm'][j][i]) for j in range(2) for i in range(3))
            if error > .2: raise RuntimeError(f'Imported cell scale/axis mismatch: {cell["name"]}: {error} cm')
            if not is_world and not cell['name'].startswith('terrain_'):
                # API differences remain explicit failures/pending capabilities in the receipt.
                try:
                    settings = mesh_tools.get_nanite_settings(mesh)
                    settings.set_editor_property('enabled',True)
                    mesh_tools.set_nanite_settings(mesh,settings,True)
                    nanite.append({'asset':mesh.get_path_name(),'enabled':True})
                except Exception as exc:
                    nanite.append({'asset':mesh.get_path_name(),'enabled':False,'error':str(exc)})
            actor = actor_tools.spawn_actor_from_class(unreal.StaticMeshActor,unreal.Vector(*cell['position_unreal_cm']))
            actor.set_actor_label(('WORLD001_' if is_world else 'GEO002_')+cell['name'])
            actor.static_mesh_component.set_static_mesh(mesh)
            actor.static_mesh_component.set_mobility(unreal.ComponentMobility.STATIC)
            if is_world:
                if not unreal.MonterreyGeoLibrary.configure_static_world_collision(mesh):
                    raise RuntimeError('Native static triangle collision configuration failed')
                actor.static_mesh_component.set_collision_profile_name('BlockAll')
                actor.set_folder_path(unreal.Name('WORLD001/'+cell['system']))
                actor.set_editor_property('tags',[unreal.Name('WORLD001'),unreal.Name(cell['system'])])
                result.setdefault('collision_configuration',[]).append({'asset':mesh.get_path_name(),
                    'policy':'complex_as_simple_static_only','runtime_collision_tested':False})
            result['assets'].append({'source':cell['file'],'asset':mesh.get_path_name(),'bounds_error_cm':error})
        if terrain_mode == 'landscape':
            count = unreal.MonterreyGeoLibrary.import_landscape(str(terrain))
            if count != len(t['tiles']): raise RuntimeError('Landscape tile count failed')
            controls = json.loads(unreal.MonterreyGeoLibrary.validate_landscape_controls(str(terrain)))
            if not controls.get('passed'): raise RuntimeError('Landscape control points failed')
            result.update(landscape_imported=True,landscape_controls=controls)
        factory = unreal.DataTableFactory()
        factory.set_editor_property('struct',unreal.load_object(None,'/Script/MonterreyOpenWorld.MonterreyBuildingRow'))
        table = asset_tools.create_asset('WORLD001_BuildingPoints' if is_world else 'GEO002_BuildingPoints',asset_root+'/PCG' if is_world else asset_root,unreal.DataTable,factory)
        if table is None or not unreal.DataTableFunctionLibrary.fill_data_table_from_csv_file(table,str(city/m['pcg_buildings_csv'])):
            raise RuntimeError('Could not import PCG source DataTable')
        result['pcg_source_datatable'] = table.get_path_name(); result['pcg_graph_executed'] = False
        if is_world:
            factory=unreal.DataAssetFactory()
            factory.set_editor_property('data_asset_class',unreal.load_class(None,'/Script/MonterreyOpenWorld.MonterreyWorldData'))
            metadata=asset_tools.create_asset('WORLD001_Georeference',asset_root+'/DataAssets',unreal.DataAsset,factory)
            if metadata is None: raise RuntimeError('Georeference DataAsset creation failed')
            for key,value in [('revision',m['milestone']),('model_sha256',m['glb_sha256']),
                              ('horizontal_epsg',32614),('vertical_datum',str(m['source_vertical_datum'])),
                              ('projected_center_metres',unreal.Vector2D(*m['center_easting_northing_m']))]:
                metadata.set_editor_property(key,value)
            result.update(world_metadata_asset=metadata.get_path_name(),terrain_mode='excavated_static_mesh',
                          runtime_traversal_validated=False,nanite_policy='disabled_pending_collision_fallback_validation')
            probes=os.environ.get('MOW_PROBES_FILE')
            if probes:
                probe_data=json.loads(Path(probes).read_text())
                if probe_data['model_sha256']!=m['glb_sha256']:raise RuntimeError('Trace probes refer to another model')
                trace_result=json.loads(unreal.MonterreyGeoLibrary.validate_world_probes(probes))
                result['native_collision_trace_result']=trace_result
                if not trace_result.get('passed'):raise RuntimeError('Native world collision traces failed')
        if not unreal.EditorLoadingAndSavingUtils.save_map(world,map_path): raise RuntimeError('Map save failed')
        if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages(True,True): raise RuntimeError('Package save failed')
        result.update(status='imported_pending_world_partition_conversion',map_path=map_path,nanite=nanite)
    except Exception as exc:
        result.update(status='failed',error=str(exc)); raise
    finally:
        receipt.parent.mkdir(parents=True,exist_ok=True)
        receipt.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')


main()

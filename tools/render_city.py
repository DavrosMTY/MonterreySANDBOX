"""Run with Blender --background --python this_file -- --city DIR --output DIR.

Uses only the exported model, CPU Cycles, and actual camera renders. No AI images.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

import bpy
from mathutils import Vector


def filehash(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--city', required=True); p.add_argument('--output', required=True)
    p.add_argument('--samples', type=int, default=24)
    p.add_argument('--width', type=int, default=1440); p.add_argument('--height', type=int, default=960)
    p.add_argument('--threads', type=int, default=8)
    args = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    start = time.perf_counter(); city, output = Path(args.city).resolve(), Path(args.output).resolve()
    if output.exists() and any(output.iterdir()): raise ValueError('Render output must be empty')
    manifest = json.loads((city/'manifest.json').read_text(encoding='utf-8'))
    model = city/manifest['glb']
    if filehash(model) != manifest['glb_sha256']: raise ValueError('Model checksum mismatch')
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(model))
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 1.
    meshes = [o for o in scene.objects if o.type == 'MESH']
    material_by_attribute = {}
    for obj in meshes:
        if not obj.data.color_attributes:
            raise ValueError('GLB lost its generated vertex color attribute')
        layer = obj.data.color_attributes[0].name
        if layer not in material_by_attribute:
            mat = bpy.data.materials.new('GEO002_Blockout_VertexColors_'+layer); mat.use_nodes = True
            shader = mat.node_tree.nodes.get('Principled BSDF')
            attribute = mat.node_tree.nodes.new('ShaderNodeVertexColor'); attribute.layer_name = layer
            mat.node_tree.links.new(attribute.outputs['Color'], shader.inputs['Base Color'])
            shader.inputs['Roughness'].default_value = .88; shader.inputs['Metallic'].default_value = 0.
            material_by_attribute[layer] = mat
        obj.data.materials.clear(); obj.data.materials.append(material_by_attribute[layer])
    source_triangles = 0; vertices_world = []
    for obj in meshes:
        obj.data.calc_loop_triangles(); source_triangles += len(obj.data.loop_triangles)
        vertices_world.extend(obj.matrix_world @ Vector(p) for p in obj.bound_box)
        for face in obj.data.polygons: face.use_smooth = False
    bounds = [[min(p[i] for p in vertices_world) for i in range(3)],
              [max(p[i] for p in vertices_world) for i in range(3)]]
    expected = [[min(p['bounds_enu_m'][0][i] for p in manifest['mesh_parts']) for i in range(3)],
                [max(p['bounds_enu_m'][1][i] for p in manifest['mesh_parts']) for i in range(3)]]
    if max(abs(bounds[j][i]-expected[j][i]) for j in range(2) for i in range(3)) > .02:
        raise ValueError('Blender import changed axes, units or bounds')
    if source_triangles != manifest['summary']['triangles']:
        raise ValueError('Blender triangle count does not match generated model')
    scene.render.engine = 'CYCLES'; scene.cycles.device = 'CPU'
    # The system Blender build lacks OpenImageDenoise. CPU path tracing works;
    # use actual samples rather than requesting an unavailable denoiser.
    scene.cycles.samples = args.samples; scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 4; scene.cycles.diffuse_bounces = 2; scene.cycles.glossy_bounces = 2
    scene.render.threads_mode = 'FIXED'; scene.render.threads = args.threads
    scene.render.resolution_x = args.width; scene.render.resolution_y = args.height
    scene.render.resolution_percentage = 100; scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'; scene.render.film_transparent = False
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.70, .79, .86, 1)
    background.inputs['Strength'].default_value = .55
    sun_data = bpy.data.lights.new('Sun_GEO002', type='SUN'); sun_data.energy = 2.5; sun_data.angle = .06
    sun = bpy.data.objects.new('Sun_GEO002', sun_data); scene.collection.objects.link(sun)
    sun.rotation_euler = (.48, -.32, -.7)
    scene.view_settings.view_transform = 'AgX'
    camera_data = bpy.data.cameras.new('GEO002_Camera'); camera = bpy.data.objects.new('GEO002_Camera', camera_data)
    scene.collection.objects.link(camera); scene.camera = camera
    camera_data.clip_start = .1; camera_data.clip_end = 15000
    deps = bpy.context.evaluated_depsgraph_get(); deps.update()
    base = (bounds[0][2]+min(bounds[1][2], 580))/2
    semantic = json.loads((city/'road_semantics.json').read_text(encoding='utf-8'))

    def ground(x, y):
        hit, location, normal, index, obj, matrix = scene.ray_cast(deps, Vector((x,y,3000)), Vector((0,0,-1)), distance=6000)
        return (location, obj) if hit else (None, None)

    candidates = [r for r in semantic['roads'] if r['kind']=='surface' and r['role']=='carriageway'
                  and r['tags'].get('highway') in ('residential','tertiary','secondary')]
    centers = [((p['bounds_enu_m'][0][0]+p['bounds_enu_m'][1][0])/2,
                (p['bounds_enu_m'][0][1]+p['bounds_enu_m'][1][1])/2)
               for p in manifest['mesh_parts'] if p['role']=='building' and p['category']!='canopy']
    scored = []
    for road in candidates:
        points = [Vector(p) for p in road.get('source_centerline_enu_m',road['centerline_enu_m'])]
        for a, b in zip(points[:-1], points[1:]):
            if (b-a).length < 45: continue
            point = a.lerp(b,.3)
            density = sum((x-point.x)**2+(y-point.y)**2 < 90**2 for x,y in centers)
            scored.append((density,road,a,b))
    scored.sort(key=lambda x:x[0], reverse=True)
    street = None
    for density, road, a, b in scored:
        p0 = a.lerp(b,.3)
        if max(abs(p0.x), abs(p0.y)) > 800: continue
        hit, obj = ground(p0.x, p0.y)
        if hit is None or not obj.name.startswith('surface_'): continue
        direction = (b-a).normalized()
        position = Vector((p0.x,p0.y,hit.z+1.75))
        target = position+Vector((direction.x*45,direction.y*45,.1))
        street = ('street',position,target,24.,road['id']); break
    if street is None: raise ValueError('Could not place a verified street camera on a generated surface road')
    views = [('aerial', Vector((2100,-2400,base+2300)), Vector((0,0,base+25)), 38., None),
             street,
             ('elevated', Vector((190,-350,base+150)), Vector((30,150,base+20)), 26., None)]
    if manifest.get('milestone')=='GEO-003 / WORLD-001':
        bridges=[r for r in semantic['roads'] if r['kind']=='bridge' and r['role']=='carriageway'
                 and len(r['centerline_enu_m'])>20]
        bridges.sort(key=lambda r:len(r['centerline_enu_m']),reverse=True)
        if bridges:
            road=bridges[0];point=Vector(road['centerline_enu_m'][len(road['centerline_enu_m'])//2])
            views[2]=('elevated',point+Vector((100,-150,85)),point+Vector((0,0,3)),32.,road['id'])
    output.mkdir(parents=True, exist_ok=True)
    if (city/'DATA_LICENSES.txt').is_file():
        (output/'DATA_LICENSES.txt').write_text((city/'DATA_LICENSES.txt').read_text(encoding='utf-8'),encoding='utf-8')
    evidence = {'milestone':manifest.get('milestone','GEO-002'),'renderer':'Blender Cycles CPU','blender_version':bpy.app.version_string,
                'generated_at_utc':datetime.now(timezone.utc).isoformat(),'input_glb_sha256':filehash(model),
                'imported_triangle_count':source_triangles,'bounds_enu_m':bounds,
                'synthetic_input':manifest['synthetic'],'views':[],'unreal_executed':False,'ai_generated_images':False,
                'denoising_enabled':False,'material_source':'exported GLB COLOR_0 vertex attributes'}
    for label, position, target, lens, road_id in views:
        camera.location = position; camera.rotation_euler = (target-position).to_track_quat('-Z','Y').to_euler()
        camera_data.lens = lens; scene.render.filepath = str(output/f'{label}.png')
        view_start = time.perf_counter(); bpy.ops.render.render(write_still=True)
        path = output/f'{label}.png'
        if not path.exists() or path.stat().st_size < 10000: raise ValueError('Render image missing or empty')
        evidence['views'].append({'name':label,'file':path.name,'sha256':filehash(path),
                                  'camera_enu_m':list(position),'target_enu_m':list(target),'lens_mm':lens,
                                  'samples':args.samples,'resolution':[args.width,args.height],
                                  'road_id':road_id,'render_seconds':time.perf_counter()-view_start})
        (output/'render_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    blend_name='monterrey_world001.blend' if manifest.get('milestone')=='GEO-003 / WORLD-001' else 'monterrey_geo002.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(output/blend_name), compress=True)
    evidence['blend_file']=blend_name
    evidence['blend_sha256'] = filehash(output/blend_name)
    evidence['total_seconds'] = time.perf_counter()-start
    (output/'render_evidence.json').write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
    print('GEO002_RENDER_COMPLETE', json.dumps(evidence))


if __name__ == '__main__': main()

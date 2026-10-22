"""Compose validated GEO-003/GEO-004 worlds and scientific inspection sidecar."""
import argparse
import gzip
import json
from pathlib import Path
import shutil

import numpy as np
import rasterio

from build_world002 import build_world
from build_web_viewer import sha,ROOT


def build(city,terrain,before,after,output,baseline,dem,validation=None):
    city,terrain,before,after,out,baseline=map(Path,(city,terrain,before,after,output,baseline))
    world=build_world(city,out,dem)
    temporary=out.parent/(out.name+'-geo003-source')
    old=build_world(baseline,temporary,dem)
    target=out/'geo003';target.mkdir();shutil.copytree(temporary/'assets',target/'assets')
    for record in old['sectors']:record['url']='geo003/'+record['url']
    old['features_url']='geo003/'+old['features_url']
    for name in ('visual_overlay','background'):
        old[name]['url']='geo003/'+old[name]['url']
    old['current_model']='geo003';old['comparison']={'geo004':{'url':'world.json'},'geo003':{'url':'geo003/world.json'}}
    (target/'world.json').write_text(json.dumps(old,indent=2)+'\n')
    def grid(path,interpolation):
        with rasterio.open(path)as ds:data=ds.read(1)
        return {'n':data.shape[0],'heights_m':np.round(data.astype(float),4).ravel().tolist(),'interpolation':interpolation}
    source=json.loads((terrain/'manifest.json').read_text())
    baseline_summary=json.loads((before/'audit.json').read_text());after_summary=json.loads((after/'audit.json').read_text())
    before_features=json.loads((before/'issues.geojson').read_text())['features']
    selected=sorted((f for f in before_features if f['properties']['kind']=='at_grade_procedural_skirt'),key=lambda f:f['properties']['measurement_m_or_percent'],reverse=True)
    cases=[]
    for f in selected:
        x,n,h=f['properties']['position_enu_m'];z=-n
        if any(np.hypot(x-c['target'][0],z-c['target'][2])<180 for c in cases):continue
        cases.append({'label':f'Faldón {f["properties"]["measurement_m_or_percent"]:.1f} m · {f["geometry"]["coordinates"][1]:.5f}, {f["geometry"]["coordinates"][0]:.5f}',
                      'camera':[x+45,h+55,z+65],'target':[x,h,z],'source_issue':f['properties']})
        if len(cases)==3:break
    models={
     'geo001':{'grid':grid(ROOT/'Data/unreal/monterrey_centro_single_v3/terrain_reference.tif','bilinear'),'source':'Copernicus GLO-30 DSM, remuestreado, sin ajustes GEO-003','native_resolution_m':30,'source_year':None},
     'geo003':{'grid':grid(baseline/'correction_layers/corrected_DSM.tif','bilinear'),'heat':json.loads((before/'heat.json').read_text()),
       'label':'DSM ~30 m · remuestreo 3,97 m · ajustes procedurales GEO-003','source':'Copernicus GLO-30 DSM + procedural GEO-003','native_resolution_m':30,'source_year':None},
     'geo004':{'grid':grid(terrain/'terrain_reference.tif','native_triangles'),'heat':json.loads((after/'heat.json').read_text()),
       'label':'MDT LiDAR INEGI 5 m · datos 2007 · EGM2008 transformado · EPV desconocida','source':'INEGI G14C26A3_MT LiDAR 5m, source NAVD88, project GGM10/EGM2008 transform','native_resolution_m':5,'source_year':2007}}
    data={'schema_version':1,'center':world['center_easting_northing_m'],'models':models,'cases':cases,
          'uncertainty':'2007 source, no EPV; GGM05/GGM10 realization uncertainty; model sampling/decimals are not survey accuracy.',
          'source_manifest':source,'before_summary':{k:v for k,v in baseline_summary.items()if k!='mesh_metrics'},
          'after_summary':{k:v for k,v in after_summary.items()if k!='mesh_metrics'}}
    if validation:
        validation=Path(validation)
        reviewed=json.loads((validation/'review-issues.geojson').read_text())['features']
        heat=models['geo004']['heat']['values']
        for f in reviewed:
            x,y,_=f['properties']['position_enu_m'];row=min(79,max(0,int((1000-y)/25)));col=min(79,max(0,int((x+1000)/25)))
            heat[row*80+col]=max(heat[row*80+col],f['properties']['severity'])
        data['extended_validation']=json.loads((validation/'validation.json').read_text())
    path=out/'assets/topography.json.gz' ;path.write_bytes(gzip.compress(json.dumps(data,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    world['current_model']='geo004';world['comparison']=old['comparison'];world['topography']={'url':'assets/'+path.name,'bytes':path.stat().st_size,'sha256':sha(path)}
    from GeoPipeline.geo004 import PlanarDTM
    field=PlanarDTM(terrain/'terrain_reference.tif',source)
    world['street_camera_m']=[-76.36123249,float(field([[-76.36123249,48.25964916]])[0])+1.82,-48.25964916]
    (out/'world.json').write_text(json.dumps(world,indent=2)+'\n')
    reports=out/'reports';reports.mkdir()
    for folder,label in ((before,'geo003'),(after,'geo004')):
        for name in ('audit.json','issues.geojson','anomaly-map.png'):
            shutil.copy2(folder/name,reports/(label+'-'+name))
    if validation:
        for p in validation.iterdir():
            if p.is_file():shutil.copy2(p,reports/p.name)
    (reports/'README.txt').write_text('Mapas y perfiles son gráficos científicos de datos y mallas, no capturas del motor. Los puntos QA indican revisión pendiente, no precisión absoluta. Las capturas auténticas se encuentran en ../evidence/.\n')
    (out/'licenses/INEGI.txt').write_text('Fuente: INEGI, MDT LiDAR G14C26A3 5m (datos 2007, edición 2012). https://www.inegi.org.mx/inegi/terminos.html\nEl proyecto reproyecta y transforma NAVD88 a EGM2008 (GGM10 / EGM2008); no es trabajo avalado por INEGI. EPV no publicada; GGM05 aparece en los metadatos históricos y su realización permanece incierta. Se conservan originales y se identifican los derivados.\nGGM10 © INEGI, CC BY 4.0 (OSGeo PROJ-data). EGM2008 US NGA: dominio público.\n')
    shutil.copytree(ROOT/'docs/geo004/source-metadata',out/'licenses/inegi-source-metadata')
    (out/'licenses/geo004-sources.json').write_bytes((ROOT/'manifests/geo004-sources.json').read_bytes())
    about=out/'about.html';about.write_text(about.read_text().replace('El terreno es la malla excavada GEO-003.', 'GEO-004 utiliza MDT INEGI 5 m sin deformación vial; el selector GEO-003 conserva la malla excavada anterior.').replace('No son un levantamiento ni un DTM medido.', 'Las vías y edificios no son levantamientos; el nuevo terreno es un MDT derivado de LiDAR de 2007 con EPV no publicada.').replace('El terreno incluye modificaciones procedurales GEO-003.', 'El modo GEO-003 conserva modificaciones procedurales; el MDT nuevo usa INEGI.').replace('</html>','<p>GEO-004: Fuente INEGI, MDT LiDAR G14C26A3 5 m, datos 2007, edición 2012. EPV no publicada. Transformación del proyecto NAVD88/GGM10 a EGM2008; realización GGM05 de origen pendiente de control. <a href="licenses/INEGI.txt">Avisos</a> · <a href="licenses/geo004-sources.json">Fuentes y SHA</a> · <a href="reports/validation.json">QA y limitaciones</a> · <a href="evidence/">Capturas auténticas</a>.</p></html>'))
    size=sum(p.stat().st_size for p in out.rglob('*')if p.is_file())
    if size>50*1024**2:raise ValueError('Combined hosting exceeds free 50 MiB cap')
    print(json.dumps({'combined_site_bytes':size,'topography_bytes':path.stat().st_size,'cases':len(cases),'geo003_triangles':old['triangles'],'geo004_triangles':world['triangles']},indent=2))
    return world


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('city','terrain','before','after','output'):p.add_argument('--'+arg,required=True)
    p.add_argument('--baseline',default='Data/city/geo003_world001');p.add_argument('--dem',default='/tmp/mow-world002/regional-dem.tif')
    p.add_argument('--validation');a=p.parse_args();build(a.city,a.terrain,a.before,a.after,a.output,a.baseline,a.dem,a.validation)

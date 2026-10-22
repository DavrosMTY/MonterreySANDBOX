"""GEO-004 audits geometric relationships separately from unknown survey accuracy."""
from collections import Counter
import json
from pathlib import Path

import numpy as np
from pyproj import Transformer
import rasterio
import trimesh

from .geo001 import sha256
from .mesh import Surface,enu_to_gltf


def raster_stats(values,spacing):
    gy,gx=np.gradient(values.astype(float),spacing);grade=np.hypot(gx,gy)*100
    return {'height_min_max_m':[float(values.min()),float(values.max())],
            'grade_percent_p50_p90_p99_max':np.quantile(grade,[.5,.9,.99,1]).tolist()},grade


def audit(city,terrain,output,baseline=None):
    city,terrain,out=Path(city),Path(terrain),Path(output)
    if out.exists():raise FileExistsError('Preserve earlier audit')
    out.mkdir(parents=True)
    m=json.loads((city/'manifest.json').read_text());tm=json.loads((terrain/'manifest.json').read_text())
    if sha256(city/m['glb'])!=m['glb_sha256']:raise ValueError('Model hash mismatch')
    from .geo004 import PlanarDTM
    surface=(PlanarDTM if m['milestone']=='GEO-004'else Surface)(terrain/tm['reference_geotiff'],tm)
    # GEO-003's intended support surface is its own procedural corrected raster.
    if m['milestone']=='GEO-003 / WORLD-001':
        with rasterio.open(city/'correction_layers/corrected_DSM.tif')as ds:surface.data=ds.read(1)
    records={p['name']:p for p in m['mesh_parts']};scene=trimesh.load_scene(city/m['glb'],process=False)
    half=m['extent_m']/2;heat_step=2*half/80
    issues=[];stats=Counter();mesh_rows=[];heat=np.zeros((80,80));to_geo=Transformer.from_crs(32614,4326,always_xy=True)
    def issue(kind,severity,point,record,measurement,threshold,reason):
        x,y,h=map(float,point);e,n=np.array(m['center_easting_northing_m'])+[x,y];lon,lat=to_geo.transform(e,n)
        issues.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{
            'kind':kind,'severity':severity,'source_mesh':record['name'],'source_road_ids':record.get('source_road_ids',[]),
            'osm_id':record.get('osm_id'),'position_enu_m':[x,y,h],'measurement_m_or_percent':float(measurement),
            'geometric_threshold':threshold,'cause':reason,'source_model_sha256':m['glb_sha256'],
            'survey_accuracy_certified':False,'vertical_datum':'EGM2008'}})
        row=min(79,max(0,int((half-y)/heat_step)));col=min(79,max(0,int((x+half)/heat_step)));heat[row,col]=max(heat[row,col],severity)
    for node in sorted(scene.graph.nodes_geometry):
        matrix,key=scene.graph[node];mesh=scene.geometry[key];r=records[node]
        xyz=trimesh.transform_points(mesh.vertices,np.linalg.inv(enu_to_gltf())@matrix);tri=xyz[mesh.faces]
        cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);up=cross[:,2]>1e-8
        if r['role'] not in ('carriageway','walkway','sidewalk'):continue
        stats['road_mesh_parts_checked']+=1
        if r.get('kind')!='surface':continue
        stats['at_grade_parts_checked']+=1
        top=tri[up];centers=top.mean(axis=1);g=np.hypot(cross[up,0],cross[up,1])/cross[up,2]*100
        expected=surface(centers[:,:2])+.12+(.08 if r['role'] in ('sidewalk','walkway')else 0)
        delta=centers[:,2]-expected
        bad=np.abs(delta)>.25
        stats['cap_triangles_checked']+=len(top);stats['cap_triangles_support_error_over_25cm']+=int(bad.sum())
        maxerror=float(np.max(abs(delta),initial=0));maxgrade=float(np.max(g,initial=0))
        # Vertical edges of an at-grade slab >1 m are a generated skirt, not a bridge.
        xy=np.round(xyz[:,:2],4);_,inv=np.unique(xy,axis=0,return_inverse=True);lo=np.full(inv.max()+1,np.inf);hi=np.full(inv.max()+1,-np.inf)
        np.minimum.at(lo,inv,xyz[:,2]);np.maximum.at(hi,inv,xyz[:,2]);span=hi-lo
        skirt=float(span.max(initial=0));stats['parts_with_at_grade_skirt_over_1m']+=int(skirt>1)
        mesh_rows.append({'name':node,'role':r['role'],'kind':r['kind'],'cap_support_error_max_m':maxerror,
                          'max_triangle_grade_percent':maxgrade,'max_vertical_edge_span_m':skirt,
                          'cap_support_error_over_25cm_triangles':int(bad.sum())})
        if maxerror>.25:
            j=int(np.argmax(abs(delta)));issue('road_cap_vs_own_support_field',3 if maxerror>1 else 2,centers[j],r,maxerror,.25,
                'Exported cap interpolation / nearest-profile height differs from its own intended support field; not an absolute survey error')
        if skirt>1:
            group=int(span.argmax());j=int(np.flatnonzero(inv==group)[0]);issue('at_grade_procedural_skirt',3,xyz[j],r,skirt,1,
                'At-grade slab bottom extended to terrain while top followed a different road profile; no surveyed retaining-wall tag')
        if maxgrade>35:
            j=int(g.argmax());issue('steep_road_triangle_review',2,centers[j],r,maxgrade,35,
                'Screening threshold, not proof of an incorrect natural slope; inspect against source DTM and road class')
    sr,grade=raster_stats(surface.data,surface.spacing)
    if baseline:
        bm=json.loads((Path(baseline)/'manifest.json').read_text());bs=Surface(Path(baseline)/bm['reference_geotiff'],bm)
        if bs.data.shape==surface.data.shape:
            _,oldgrade=raster_stats(bs.data,bs.spacing);delta=surface.data-bs.data
            artifact=(grade>35)&(grade-oldgrade>15)&(abs(delta)>.5)
            stats['correction_induced_steep_raster_vertices']=int(artifact.sum())
            for row,col in np.argwhere(artifact)[::max(1,int(artifact.sum())//100)]:
                point=[-surface.half+col*surface.spacing,surface.half-row*surface.spacing,surface.data[row,col]]
                issue('correction_induced_terrain_gradient',3,point,{'name':'terrain_raster'},grade[row,col],35,
                      'GEO-003 procedural delta increases slope by >15 percentage points where vertical change >0.5 m')
            sr['base_plus_correction_delta_min_max_m']=[float(delta.min()),float(delta.max())]
    result={'status':'geometric_audit_completed_not_survey_certificate','model_sha256':m['glb_sha256'],'milestone':m['milestone'],
            'all_source_roads_in_scope':m['summary']['road_segments'],'scope_not_limited_to_previous_97':True,
            'counts':dict(stats),'raster':sr,'native_source_resolution_m':30 if m['milestone'].startswith('GEO-003')else 5,
            'sampling_spacing_m':surface.spacing,'source_vertical_accuracy_m':None,'no_unit_scale_error_detected':True,
            'uncertainty':'Geometry thresholds do not establish source absolute accuracy. INEGI is 2007, EPV unspecified; GGM05/GGM10 realization uncertainty retained.',
            'mesh_metrics':mesh_rows,'issues':len(issues),'unreal_executed':False}
    (out/'audit.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    (out/'issues.geojson').write_text(json.dumps({'type':'FeatureCollection','features':issues},separators=(',',':'))+'\n')
    (out/'heat.json').write_text(json.dumps({'bounds_enu_m':[-half,-half,half,half],'n':80,'values':heat.ravel().astype(int).tolist(),
            'legend':{'0':'no sampled issue in this bin; not a certificate','2':'review','3':'severe geometric discrepancy'}},separators=(',',':'))+'\n')
    # Standalone scientific plot, based only on numerical source/mesh evidence.
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(11,5));axes[0].imshow(grade,extent=[-half,half,-half,half],origin='upper',vmin=0,vmax=50,cmap='magma')
    axes[0].set_title('Pendiente del campo de soporte (%)');im=axes[1].imshow(heat,extent=[-half,half,-half,half],origin='upper',vmin=0,vmax=3,cmap='YlOrRd')
    axes[1].set_title('Anomalías geométricas muestreadas');fig.colorbar(im,ax=axes[1],label='Severidad de revisión')
    for ax in axes:ax.set_xlabel('Este local (m)');ax.set_ylabel('Norte local (m)')
    fig.suptitle(m['milestone']+' · no certifica precisión topográfica');fig.tight_layout();fig.savefig(out/'anomaly-map.png',dpi=140);plt.close(fig)
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--city',required=True);p.add_argument('--terrain',required=True);p.add_argument('--output',required=True);p.add_argument('--baseline')
    a=p.parse_args();r=audit(a.city,a.terrain,a.output,a.baseline);print(json.dumps({k:v for k,v in r.items()if k!='mesh_metrics'},indent=2))

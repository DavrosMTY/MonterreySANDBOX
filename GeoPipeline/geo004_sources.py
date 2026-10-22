"""GEO-004: pinned licensed INEGI DTM, explicit vertical operation and strict NoData.

Original delivery ZIP and global geoid grids are never overwritten. Target heights
remain EGM2008; unknown source accuracy/age/realization differences remain explicit.
"""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import warnings
import zipfile

import numpy as np
import pyproj
from pyproj.transformer import TransformerGroup,AreaOfInterest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject,Resampling

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb')as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()


def acquire(record,path,cap):
    path=Path(path)
    if path.exists():
        if sha(path)!=record['sha256']:raise ValueError('Preserve unexpected existing source: '+str(path))
        return path
    request=urllib.request.Request(record['url'],headers={'User-Agent':'MonterreyOpenWorld/GEO004 open geodata'})
    with urllib.request.urlopen(request,timeout=60)as r:data=r.read(cap+1)
    if len(data)>cap or hashlib.sha256(data).hexdigest()!=record['sha256']:raise ValueError('Source size/hash mismatch')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return path


def xyz_grid(points,spacing=5.):
    points=np.asarray(points);x,y=np.unique(points[:,0]),np.unique(points[:,1])
    if not np.isfinite(points).all()or not np.allclose(np.diff(x),spacing)or not np.allclose(np.diff(y),spacing):raise ValueError('Invalid regular XYZ grid')
    c=np.rint((points[:,0]-x[0])/spacing).astype(int);r=np.rint((y[-1]-points[:,1])/spacing).astype(int)
    indices=r*len(x)+c
    if len(np.unique(indices))!=len(points):raise ValueError('Duplicate XYZ samples')
    result=np.full((len(y),len(x)),np.nan,dtype=np.float32);result[r,c]=points[:,2]
    return result,from_origin(x[0]-spacing/2,y[-1]+spacing/2,spacing,spacing)


def vertical_transform(grids):
    pyproj.datadir.append_data_dir(str(Path(grids).resolve()))
    with warnings.catch_warnings(record=True)as found:
        group=TransformerGroup('EPSG:4487+5703','EPSG:32614+3855',always_xy=True,
            area_of_interest=AreaOfInterest(-100.33,25.65,-100.29,25.68),allow_ballpark=False)
    operations=[t for t in group.transformers if 'mx_inegi_ggm10.tif'in t.definition and 'us_nga_egm08_25.tif'in t.definition
                and 'us_noaa_'not in t.definition and 'ballpark'not in t.description.lower()]
    if len(operations)!=1:raise ValueError('Unique verified Mexico vertical operation is unavailable')
    return operations[0],[str(w.message)for w in found]


def write_grid(path,values,transform,datum,**tags):
    with rasterio.open(path,'w',driver='GTiff',width=values.shape[1],height=values.shape[0],count=1,
            crs='EPSG:32614',transform=transform,dtype='float32',nodata=np.nan,compress='deflate')as dst:
        dst.write(values.astype('float32'),1);dst.set_band_unit(1,'m');dst.update_tags(AREA_OR_POINT='Point',VERTICAL_DATUM=datum,**tags)


def build(output,inputs='artifacts/geo004-inputs',reference='Data/unreal/monterrey_centro_single_v3'):
    out,inputs,reference=Path(output),Path(inputs),Path(reference)
    if out.exists():raise FileExistsError('Preserve previous DTM: choose a new output')
    config=json.loads((ROOT/'manifests/geo004-sources.json').read_text());dtm=config['inegi_dtm']
    archive=acquire(dtm,inputs/dtm['filename'],40*1024**2)
    for g in config['grids']:acquire(g,inputs/'grids'/g['file'],100*1024**2)
    with zipfile.ZipFile(archive)as z:
        if z.testzip():raise ValueError('Corrupt provider ZIP')
        with z.open(dtm['data_member'])as f:points=np.loadtxt(f)
        metadata={Path(n.replace('\\','/')).name:z.read(n)for n in dtm['metadata_members']}
    values,source_transform=xyz_grid(points)
    m=json.loads((reference/'manifest.json').read_text());center=m['center_easting_northing_m'];half=m['extent_m']/2
    spacing=5.;n=int(round(2*half/spacing))+1
    target_transform=from_origin(center[0]-half-spacing/2,center[1]+half+spacing/2,spacing,spacing)
    # Horizontal-only reprojection. NAVD88 remains NAVD88 until the explicit step below.
    target=np.full((n,n),np.nan,dtype=np.float32)
    reproject(values,target,src_transform=source_transform,src_crs='EPSG:4487',src_nodata=np.nan,
              dst_transform=target_transform,dst_crs='EPSG:32614',dst_nodata=np.nan,resampling=Resampling.bilinear)
    if not np.isfinite(target).all():raise ValueError('INEGI does not completely cover pilot; NoData must not be filled by guesswork')
    op,warnings_seen=vertical_transform(inputs/'grids')
    row,col=np.mgrid[:n,:n];east=center[0]-half+col*spacing;north=center[1]+half-row*spacing
    # Query the same physical locations in the source horizontal frame.
    to_source=pyproj.Transformer.from_crs(32614,4487,always_xy=True,allow_ballpark=False)
    sx,sy=to_source.transform(east,north,errcheck=True)
    tx,ty,height=op.transform(sx,sy,target.astype(float),errcheck=True)
    if not np.isfinite(height).all()or np.max(abs(tx-east))>.001 or np.max(abs(ty-north))>.001:raise ValueError('Invalid datum transformation or horizontal registration')
    rx,ry,rz=op.transform(tx,ty,height,direction=pyproj.enums.TransformDirection.INVERSE,errcheck=True)
    roundtrip=float(np.max(abs(rz-target)))
    if roundtrip>1e-5:raise ValueError('Vertical roundtrip failed')
    # Sample GEO-001 only for an explicit source-replacement delta; no original file edits.
    baseline=np.full((n,n),np.nan,dtype=np.float32)
    with rasterio.open(reference/m['reference_geotiff'])as ds:
        reproject(rasterio.band(ds,1),baseline,src_transform=ds.transform,src_crs=ds.crs,src_nodata=ds.nodata,
                  dst_transform=target_transform,dst_crs=32614,dst_nodata=np.nan,resampling=Resampling.bilinear)
    if not np.isfinite(baseline).all():raise ValueError('Reference NoData')
    out.mkdir(parents=True)
    for filename,data,datum in [('inegi_NAVD88.tif',target,'NAVD88'),('terrain_reference.tif',height,'EGM2008'),
            ('vertical_operation_delta_m.tif',height-target,'EGM2008_minus_NAVD88'),
            ('baseline_DSM_on_5m_grid.tif',baseline,'EGM2008'),('source_replacement_delta_m.tif',height-baseline,'EGM2008')]:
        write_grid(out/filename,data,target_transform,datum,source='INEGI G14C26A3_MT 2007; project transforms, not INEGI endorsement',accuracy_epv='unknown')
    meta=out/'source_metadata';meta.mkdir()
    for name,data in metadata.items():(meta/name).write_bytes(data)
    result={**m,'milestone':'GEO-004 DTM','source_dem':dtm['url'],'source_dem_sha256':dtm['sha256'],'source_record':dtm,
        'reference_geotiff':'terrain_reference.tif','reference_geotiff_sha256':sha(out/'terrain_reference.tif'),
        'source_vertical_datum':'EGM2008','original_source_vertical_datum':'NAVD88','vertical_datum_conversion_applied':True,
        'sample_spacing_m':spacing,'native_product_spacing_m':5,'resolution_vertices':[n,n],'mosaic_resolution_vertices':[n,n],
        'source_date_year':2007,'source_model':'INEGI bare-earth MDT derived from LiDAR, 5 m grid',
        'height_min_m':float(height.min()),'height_max_m':float(height.max()),'vertical_accuracy_epv_m':None,
        'vertical_accuracy_warning':'EPV absent; GGM05 in source metadata vs registered GGM10 operation remains a realization uncertainty. No exact absolute alignment certified.',
        'vertical_operation':{'description':op.description,'definition':op.definition,'published_accuracy_m':None if op.accuracy<0 else op.accuracy,
            'numeric_roundtrip_max_m':roundtrip,'delta_min_max_m':[float((height-target).min()),float((height-target).max())],
            'grids':config['grids'],'warnings':warnings_seen,'no_ballpark_fallback':True},
        'no_data_in_pilot':0,'original_source_missing_cells':int(np.isnan(values).sum()),'source_original_grid_shape':list(values.shape),
        'resampling':'bilinear at product 5 m spacing, no invented finer measurements','new_engine_import_verified':False,'unreal_x_scale_cm':500.,'unreal_y_scale_cm':500.}
    # GEO-001 landscape-specific quantization metadata cannot describe this new grid.
    for k in ('tiles','r16_sha256','heightmap_png_sha256','unreal_topology','unreal_z_scale_cm','unreal_landscape_actor_z_cm','max_quantization_error_m'):
        result.pop(k,None)
    result['files']=[{'file':p.name,'sha256':sha(p)}for p in sorted(out.glob('*.tif'))]
    (out/'manifest.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--inputs',default='artifacts/geo004-inputs')
    a=p.parse_args();r=build(a.output,a.inputs);print(json.dumps({k:r[k]for k in ('height_min_m','height_max_m','vertical_operation','no_data_in_pilot')},indent=2))

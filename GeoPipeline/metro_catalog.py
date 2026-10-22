"""Build an engine-independent metropolitan snapshot from pinned, licensed sources.

Source coverage is never equated with a reconstructed or surveyed city. Native
source geometries and raw attributes survive in append-only GeoPackage versions.
"""
from collections import Counter
import datetime,json,math
from pathlib import Path

import numpy as np
from pyproj import Transformer,Geod
import rasterio
from rasterio.features import shapes
import shapely
from shapely.geometry import box,shape,mapping,Point,LineString,Polygon

from .metro import project,TO_WGS,official_union,tiles,coverage,digest,building_fidelity
from .geopackage import Master
from .urban import multipolygon


def dump(path,value):Path(path).write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n')
def fc(features):return {'type':'FeatureCollection','features':features}
def feature(g,properties):return {'type':'Feature','geometry':mapping(g),'properties':properties}


def inventory(metro,inputs,source_inputs):
    records=[];geometries={}
    for filename,spacing in [('js_capas_malla10k_T5_min.geojson',5),('js_capas_malla10k_T1_5_min.geojson',1.5)]:
        p=Path(source_inputs)/filename;j=json.loads(p.read_text());tx=Transformer.from_crs(3857,32614,always_xy=True)
        for category in sorted({f['properties']['s']for f in j['features']}):
            raw=shapely.union_all([shape(f['geometry'])for f in j['features']if f['properties']['s']==category])
            if not raw.is_valid:raise ValueError('Invalid official coverage catalog')
            clipped=project(raw,tx).intersection(metro);key=f'inegi_DTM_{spacing}m_{category}'
            geometries[key]=clipped;records.append({'id':key,'coverage_state':'official_catalog_availability_not_downloaded_or_NoData_checked','product_grid_spacing_m':spacing,'technology':'LiDAR'if category=='L'else'photogrammetric','model':'DTM','source_file':filename,'source_sha256':digest(p),'observed_date':None,'vertical_accuracy_m':None,**coverage(clipped,metro)})
    available=[];catalog=(Path(inputs)/'copernicus_tileList.txt').read_text().splitlines();minx,miny,maxx,maxy=project(metro,TO_WGS).bounds
    for lat in range(math.floor(miny),math.ceil(maxy)):
        for lon in range(math.floor(minx),math.ceil(maxx)):
            name=f'Copernicus_DSM_COG_10_N{lat:02d}_00_W{abs(lon):03d}_00_DEM'
            if name in catalog:
                available.append(project(shapely.segmentize(box(lon,lat,lon+1,lat+1),.01)))
    g=shapely.union_all(available).intersection(metro);geometries['copernicus_GLO30_available']=g
    records.append({'id':'copernicus_GLO30_available','coverage_state':'actual_public_tile_catalog_not_all_downloaded','model':'DSM','native_product_spacing_m':30,'vertical_datum':'EGM2008','observed_date':'2011–2015 nominal acquisition mission; tile observation not independently checked','catalog_sha256':digest(Path(inputs)/'copernicus_tileList.txt'),'available_tile_count':len(available),**coverage(g,metro)})
    g=project(shapely.segmentize(box(-101,25,-100,26),.01)).intersection(metro);geometries['copernicus_downloaded_N25W101']=g
    records.append({'id':'copernicus_downloaded_N25W101','coverage_state':'one_acquired_tile_footprint_not_entire_metro_DTM','model':'DSM','native_product_spacing_m':30,**coverage(g,metro)})
    return records,geometries


def osm_entities(path,aoi,master,source_id):
    raw=json.loads(Path(path).read_text());nodes={e['id']:(e['lon'],e['lat'])for e in raw['elements']if e['type']=='node'};ways={e['id']:e for e in raw['elements']if e['type']=='way'};counts=Counter();skips=Counter();consumed=set()
    def entity(tags):
        if tags.get('building')not in (None,'no'):return 'building'
        if 'highway'in tags:return 'road'if tags['highway']not in ('traffic_signals','street_lamp','crossing','bus_stop')else'transport_control'
        if 'railway'in tags or 'public_transport'in tags:return 'transport_infrastructure'
        if 'waterway'in tags or tags.get('natural')=='water':return 'hydrography'
        if tags.get('leisure')in ('park','garden','pitch','stadium','sports_centre'):return 'green_or_public_space'
        if 'natural'in tags:return 'natural_feature'
        if 'landuse'in tags:return 'landuse'
        return None
    elements=sorted(raw['elements'],key=lambda e:(e['type']!='relation',e['type'],e['id']))
    for e in elements:
        tags=e.get('tags',{});kind=entity(tags)
        if kind is None or (e['type']=='way'and e['id']in consumed):continue
        try:
            if e['type']=='node':g=Point(e['lon'],e['lat'])
            elif e['type']=='relation':
                g,members=multipolygon(e,ways,nodes);consumed.update(members)
            else:
                refs=e['nodes']
                if len(refs)<2 or any(n not in nodes for n in refs):raise ValueError('incomplete way')
                coords=[nodes[n]for n in refs];closed=refs[0]==refs[-1]and len(refs)>=4
                area=closed and(kind in ('building','landuse','green_or_public_space')or tags.get('area')=='yes'or tags.get('natural')in ('water','wood','scrub'))
                g=Polygon(coords)if area else LineString(coords)
            if not g.is_valid:raise ValueError('invalid native geometry')
            utm=project(g).intersection(aoi)
            if utm.is_empty:continue
            if not utm.is_valid:raise ValueError('invalid clipped geometry')
        except (ValueError,KeyError)as ex:skips[str(ex)]+=1;continue
        state='historical_or_disused'if any(k.startswith(('disused:','abandoned:','demolished:'))for k in tags)else'planned'if tags.get('highway')=='proposed' or 'proposed'in tags else'construction'if tags.get('highway')=='construction'else'mapped_existing_not_field_verified'
        attrs={'raw_osm_element':e,'osm_edit_timestamp_not_observation':e.get('timestamp'),'fidelity':building_fidelity(tags)if kind=='building'else None,'direction_known':('oneway'in tags)if kind=='road'else None,'lane_count_known':('lanes'in tags)if kind=='road'else None}
        master.feature(f"osm:{e['type']}/{e['id']}",kind,source_id,e['id'],mapping(g),'EPSG:4326',project(utm,TO_WGS),utm,attrs,tier='C'if kind=='building'else None,life_cycle=state)
        counts[kind]+=1
    return {'mapped_versions_by_entity':dict(counts),'unresolved_native_geometries':dict(skips),'physical_observation_dates_unknown':True}


def build(output,inputs,research,selection_path,regions):
    out=Path(output)
    if out.exists():raise FileExistsError('Preserve previous metropolitan snapshot')
    inputs=Path(inputs);selection=json.loads(Path(selection_path).read_text());boundary_path=inputs/'inegi_nl_municipal.geojson';raw=json.loads(boundary_path.read_text())
    assert digest(boundary_path)==selection['municipal_geometry_sha256']
    metro,municipalities,original=official_union(raw,selection);out.mkdir(parents=True)
    master=Master(out/'monterrey_master.gpkg');now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    source={'source_id':'inegi_mgem_2025_12','url':'https://gaia.inegi.org.mx/wscatgeo/v2/geo/mgem/19','sha256':digest(boundary_path),'license':'INEGI free information terms; credit and transformation notice','acquired_at':selection['boundaries_acquired_at'],'observed_from':'2025-12','observed_to':'2025-12','horizontal_crs':'EPSG:4326','vertical_datum':None,'known_horizontal_accuracy_m':None,'known_vertical_accuracy_m':None,'metadata':raw.get('metadatos'),'boundary_warning':'Statistical Marco Geoestadístico, not certified legal/cadastral jurisdiction'};master.source(source)
    for code,g in municipalities.items():
        f=original[code];master.feature('inegi:municipality/'+code,'municipality',source['source_id'],code,f['geometry'],'EPSG:4326',shape(f['geometry']),g,f['properties'],verification='official_statistical_source',confidence='official source; no survey control')
    master.feature('metro:Monterrey/2020','metropolitan_definition',source['source_id'],'Monterrey2020',mapping(project(metro,TO_WGS)),'EPSG:4326',project(metro,TO_WGS),metro,selection,verification='official_membership_union_2025_geometry',operation='Exact union of listed official municipal polygons; no simplification')
    areas=[];region_index=[];entities={}
    for region in regions:
        cm=json.loads((Path(region['city'])/'manifest.json').read_text());tm=json.loads((Path(region['terrain'])/'manifest.json').read_text());e,n=cm['center_easting_northing_m'];half=cm['extent_m']/2;g=box(e-half,n-half,e+half,n+half);areas.append(g)
        record=json.loads(Path(region['osm']+'.source.json').read_text());assert digest(region['osm'])==record['sha256']
        osm_source={'source_id':'osm_'+record['sha256'][:16],'url':record.get('url')or'https://www.openstreetmap.org','sha256':record['sha256'],'license':'ODbL-1.0','acquired_at':record.get('retrieved_at_utc')or record.get('retrieved_at')or record.get('acquired_at_utc')or'unknown; preserve acquisition record','horizontal_crs':'EPSG:4326','vertical_datum':None,'observation_date_warning':'OSM edit and download dates are not physical observation dates','raw_record':record};master.source(osm_source)
        entities[region['id']]=osm_entities(region['osm'],g,master,osm_source['source_id'])
        terrain_source={'source_id':'dtm_'+tm['reference_geotiff_sha256'][:16],'url':tm['source_dem'],'sha256':tm['reference_geotiff_sha256'],'license':'INEGI free information terms + GGM10 CC-BY-4.0 + NGA public domain','acquired_at':now,'observed_from':'2007','observed_to':'2007','horizontal_crs':'EPSG:32614','vertical_datum':'EGM2008 via explicit GGM10 operation; source NAVD88/GGM05 realization uncertainty','known_vertical_accuracy_m':None,'source_archive_sha256':tm['source_dem_sha256'],'metadata':tm['source_record']};master.source(terrain_source)
        region_index.append({'id':region['id'],'label':region['label'],'area_km2':g.area/1e6,'center_easting_northing_m':[e,n],'extent_m':2*half,'geometry':mapping(project(g,TO_WGS)),'source_glb_sha256':cm['glb_sha256'],'source_dtm_sha256':tm['reference_geotiff_sha256'],'counts':cm['summary'],'dtm_year':2007,'dtm_product_spacing_m':5,'absolute_accuracy_m':None,'building_tiers':{'A':0,'B':0,'C':cm['summary']['building_features']},'structure_heights':'estimated_not_verified','bounds_utm_m':g.bounds})
    processed=shapely.union_all(areas);records,available=inventory(metro,inputs,research)
    tile_count=partial=0;index=[]
    for t in tiles(metro):
        g=t['geometry'];fraction=processed.intersection(g).area/g.area;availability={k:round(v.intersection(g).area/g.area,6)for k,v in available.items()if v.intersects(g)};master.tile(t,fraction,availability);tile_count+=1;partial+=0<fraction<.999999
        if fraction>0:index.append({'id':t['id'],'processed_fraction':fraction,'bounds_utm_m':t['grid_bounds_utm_m']})
    db=master.db
    unique=dict(db.execute('SELECT entity_type,count(*)FROM objects GROUP BY entity_type'));tiers=dict(db.execute('SELECT building_tier,count(DISTINCT object_id)FROM versions WHERE building_tier IS NOT NULL GROUP BY building_tier'))
    unknown_direction=db.execute("SELECT count(*)FROM versions WHERE object_id IN(SELECT object_id FROM objects WHERE entity_type='road')AND json_extract(attributes_json,'$.direction_known')=0").fetchone()[0]
    master.close()
    geodesic_area=abs(Geod(ellps='WGS84').geometry_area_perimeter(project(metro,TO_WGS))[0])/1e6
    summary={'milestone':'GEO-005 / METRO-001','budget_usd':0,'epoch_target':'Contemporary 2026, source inventory cutoff 2026-10-22; not a synchronized 2026 survey','definition':selection,'area_grid_km2':metro.area/1e6,'area_ellipsoidal_km2':geodesic_area,'area_difference_warning':'Published 2020 area and computed 2025 statistical-boundary area use different boundary vintages/methods','municipality_count':len(municipalities),'tiles':{'size_m':500,'count':tile_count,'partial_processed_tiles':partial,'processed_index':index,'id_basis':'global fixed EPSG:32614 grid, clipped to official membership union'},'processed_coverage':coverage(processed,metro),'urban_builtup_extent_km2':None,'urban_builtup_extent_warning':'Municipal area is not built-up urban area; no current official urban footprint yet validated','source_coverage':records,'sources_available_vs_processed_are_distinct':True,'entities':unique,'building_tiers_unique':{'A':tiers.get('A',0),'B':tiers.get('B',0),'C':tiers.get('C',0),'D':'unprocessed/incomplete coverage, not a count of invented buildings'},'roads_independently_verified_percent':0,'known_independently_verified_building_heights':0,'road_versions_without_explicit_direction':unknown_direction,'horizontal_control_point_rmse_m':None,'vertical_control_point_rmse_m':None,'regions':region_index,'entity_import':entities,'master':{'file':'monterrey_master.gpkg','sha256':digest(out/'monterrey_master.gpkg'),'bytes':(out/'monterrey_master.gpkg').stat().st_size},'unreal_executed':False,'full_metropolis_reconstructed':False}
    dump(out/'coverage.json',summary)
    dump(out/'municipalities.geojson',fc([feature(project(g,TO_WGS),{'code':code,'name':original[code]['properties']['nomgeo'],'area_grid_km2':g.area/1e6})for code,g in municipalities.items()]))
    dump(out/'metropolitan.geojson',fc([feature(project(metro,TO_WGS),{'definition':'Metropolis de Mexico 2020 / Marco Geoestadistico diciembre 2025','source_sha256':digest(boundary_path)})]))
    dump(out/'source-coverage.geojson',fc([feature(project(g,TO_WGS),{'id':key,'available_not_reconstructed':True})for key,g in available.items()if not g.is_empty]))
    dump(out/'regions.geojson',fc([feature(project(g,TO_WGS),{'id':r['id'],'label':r['label'],'building_tier':'C','absolute_accuracy_m':None})for g,r in zip(areas,regions)]))
    return summary

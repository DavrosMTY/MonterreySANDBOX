import json,sqlite3
import numpy as np
import pytest
from shapely.geometry import box,mapping,Polygon
from GeoPipeline.metro import tiles,tile_id,coverage,project,TO_WGS,building_fidelity,choose_ground_source,official_union
from GeoPipeline.geopackage import Master,unblob


def test_metric_tiles_preserve_holes_and_partial_borders_and_stable_ids():
    polygon=Polygon([(0,0),(1100,0),(1100,1100),(0,1100)],holes=[[(450,450),(650,450),(650,650),(450,650)]])
    rows=list(tiles(polygon));assert sum(r['geometry'].area for r in rows)==polygon.area
    assert all(not r['geometry'].intersects(box(451,451,649,649))for r in rows)
    assert tile_id(700,5600)=='utm14n_500_e700_n5600'
    assert 0<rows[-1]['metropolitan_fraction']<1
    assert coverage(box(0,0,500,500),polygon)['fraction']<1


def test_official_membership_requires_evidence_and_exact_codes():
    b={'features':[{'properties':{'cvegeo':'19039'},'geometry':mapping(box(-100.32,25.66,-100.30,25.68))}]}
    with pytest.raises(ValueError,match='evidence'):official_union(b,{'municipality_codes':['19039']})
    with pytest.raises(ValueError,match='Missing'):official_union(b,{'official_definition_url':'https://official','definition_evidence_sha256':'a'*64,'municipality_codes':['19039','19006']})


def test_explicit_osm_height_alone_never_assigns_verified_tiers():
    assert building_fidelity({'height':'40'})['tier']=='C'
    proof={'validated':True,'source_url':'https://official/control'}
    assert building_fidelity({'height':'40'},proof)['tier']=='B'
    assert building_fidelity({'height':'40'},proof,proof)['tier']=='A'


def test_ground_selection_rejects_finer_dsm_and_unknown_vertical_operation():
    base={'license_reviewed':True,'horizontal_crs':'EPSG:32614','vertical_operation_available':True,'coverage_verified':True,'vertical_accuracy_m':None}
    dsm={**base,'id':'roof','model':'DSM','native_spacing_m':1.5}
    dtm={**base,'id':'ground','model':'DTM','native_spacing_m':5}
    unknown={**dtm,'id':'unknown','native_spacing_m':1,'vertical_operation_available':False}
    assert choose_ground_source([dsm,dtm,unknown])['id']=='ground'
    assert choose_ground_source([dsm,unknown])is None


def test_geopackage_keeps_native_geometry_provenance_and_append_only_versions(tmp_path):
    path=tmp_path/'master.gpkg';m=Master(path)
    source={'source_id':'test','url':'https://official','sha256':'a'*64,'license':'test fixture','acquired_at':'2026-10-22','horizontal_crs':'EPSG:4326'}
    m.source(source);g=box(-100.32,25.66,-100.31,25.67);u=project(g)
    m.feature('test:building','building','test','1',mapping(g),'EPSG:4326',g,u,{'height_unknown':True},tier='C');m.close()
    db=sqlite3.connect(path);assert db.execute('PRAGMA application_id').fetchone()[0]==0x47504B47
    assert unblob(db.execute('SELECT geom FROM features_utm').fetchone()[0]).equals_exact(u,1e-9)
    assert json.loads(db.execute('SELECT native_geometry_json FROM versions').fetchone()[0])==json.loads(json.dumps(mapping(g)))
    with pytest.raises(sqlite3.IntegrityError,match='preserve'):db.execute("UPDATE versions SET native_geometry_json='{}'")
    db.close()

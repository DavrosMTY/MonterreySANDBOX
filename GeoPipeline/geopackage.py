"""Local GeoPackage 1.3 with native geometry, provenance and append-only revisions."""
import datetime,hashlib,json,sqlite3,struct
from pathlib import Path

from pyproj import CRS
import shapely


def blob(g,srid):return b'GP\x00\x01'+struct.pack('<i',srid)+shapely.to_wkb(g,byte_order=1,output_dimension=2)
def unblob(data):return shapely.from_wkb(data[8:])


class Master:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.exists():raise FileExistsError('Preserve existing master database; write a versioned snapshot')
        self.path.parent.mkdir(parents=True,exist_ok=True);self.db=sqlite3.connect(self.path);self.db.execute('PRAGMA foreign_keys=ON');self.db.execute('PRAGMA application_id=1196444487');self.db.execute('PRAGMA user_version=10300')
        self.db.executescript('''
        CREATE TABLE gpkg_spatial_ref_sys(srs_name TEXT NOT NULL,srs_id INTEGER NOT NULL PRIMARY KEY,organization TEXT NOT NULL,organization_coordsys_id INTEGER NOT NULL,definition TEXT NOT NULL,description TEXT);
        CREATE TABLE gpkg_contents(table_name TEXT NOT NULL PRIMARY KEY,data_type TEXT NOT NULL,identifier TEXT UNIQUE,description TEXT DEFAULT '',last_change DATETIME NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),min_x DOUBLE,min_y DOUBLE,max_x DOUBLE,max_y DOUBLE,srs_id INTEGER,FOREIGN KEY(srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id));
        CREATE TABLE gpkg_geometry_columns(table_name TEXT NOT NULL,column_name TEXT NOT NULL,geometry_type_name TEXT NOT NULL,srs_id INTEGER NOT NULL,z TINYINT NOT NULL,m TINYINT NOT NULL,PRIMARY KEY(table_name,column_name),FOREIGN KEY(table_name) REFERENCES gpkg_contents(table_name),FOREIGN KEY(srs_id) REFERENCES gpkg_spatial_ref_sys(srs_id));
        CREATE TABLE sources(source_id TEXT PRIMARY KEY,url TEXT NOT NULL,sha256 TEXT NOT NULL,license TEXT NOT NULL,acquired_at TEXT NOT NULL,observed_from TEXT,observed_to TEXT,horizontal_crs TEXT NOT NULL,vertical_datum TEXT,known_horizontal_accuracy_m REAL,known_vertical_accuracy_m REAL,metadata_json TEXT NOT NULL);
        CREATE TABLE objects(object_id TEXT PRIMARY KEY,entity_type TEXT NOT NULL);
        CREATE TABLE versions(fid INTEGER PRIMARY KEY,object_id TEXT NOT NULL,source_id TEXT NOT NULL,source_feature_id TEXT NOT NULL,revision INTEGER NOT NULL,native_geometry_json TEXT,native_crs TEXT NOT NULL,attributes_json TEXT NOT NULL,verification_state TEXT NOT NULL,confidence_basis TEXT NOT NULL,observation_date TEXT,life_cycle_state TEXT NOT NULL,building_tier TEXT,UNIQUE(object_id,source_id,revision),FOREIGN KEY(object_id) REFERENCES objects(object_id),FOREIGN KEY(source_id) REFERENCES sources(source_id));
        CREATE TABLE features_wgs84(fid INTEGER PRIMARY KEY,object_id TEXT NOT NULL,version_fid INTEGER NOT NULL,geom GEOMETRY NOT NULL,FOREIGN KEY(version_fid) REFERENCES versions(fid));
        CREATE TABLE features_utm(fid INTEGER PRIMARY KEY,object_id TEXT NOT NULL,version_fid INTEGER NOT NULL,geom GEOMETRY NOT NULL,FOREIGN KEY(version_fid) REFERENCES versions(fid));
        CREATE TABLE modifications(id INTEGER PRIMARY KEY,version_fid INTEGER NOT NULL,operation TEXT NOT NULL,parameters_json TEXT NOT NULL,original_geometry_sha256 TEXT,processed_geometry_sha256 TEXT,created_at TEXT NOT NULL,FOREIGN KEY(version_fid) REFERENCES versions(fid));
        CREATE TABLE tiles(fid INTEGER PRIMARY KEY,tile_id TEXT UNIQUE NOT NULL,size_m INTEGER NOT NULL,processed_fraction REAL NOT NULL,source_availability_json TEXT NOT NULL,geom GEOMETRY NOT NULL);
        CREATE INDEX versions_object_id ON versions(object_id);
        CREATE INDEX versions_source_id ON versions(source_id);
        CREATE INDEX features_utm_object_id ON features_utm(object_id);
        CREATE TRIGGER immutable_original_update BEFORE UPDATE ON versions BEGIN SELECT RAISE(ABORT,'append a revision; preserve original geometry');END;
        CREATE TRIGGER immutable_original_delete BEFORE DELETE ON versions BEGIN SELECT RAISE(ABORT,'preserve original geometry');END;
        CREATE TRIGGER immutable_source_update BEFORE UPDATE ON sources BEGIN SELECT RAISE(ABORT,'append a source version');END;
        ''')
        for code,name in [(-1,'Undefined Cartesian'),(0,'Undefined geographic')]:self.db.execute('INSERT INTO gpkg_spatial_ref_sys VALUES(?,?,?,?,?,?)',(name,code,'NONE',code,'undefined',''))
        for code in (4326,32614):
            crs=CRS.from_epsg(code);self.db.execute('INSERT INTO gpkg_spatial_ref_sys VALUES(?,?,?,?,?,?)',(crs.name,code,'EPSG',code,crs.to_wkt('WKT1_GDAL'),''))
        for table,srid in [('features_wgs84',4326),('features_utm',32614),('tiles',32614)]:
            self.db.execute('INSERT INTO gpkg_contents(table_name,data_type,identifier,srs_id)VALUES(?,?,?,?)',(table,'features',table,srid));self.db.execute('INSERT INTO gpkg_geometry_columns VALUES(?,?,?,?,0,0)',(table,'geom','GEOMETRY',srid))
        for table in ('sources','objects','versions','modifications'):self.db.execute('INSERT INTO gpkg_contents(table_name,data_type,identifier)VALUES(?,?,?)',(table,'attributes',table))
    def source(self,record):
        required=('source_id','url','sha256','license','acquired_at','horizontal_crs')
        if any(not record.get(k)for k in required):raise ValueError('Incomplete provenance')
        self.db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',tuple(record.get(k)for k in ('source_id','url','sha256','license','acquired_at','observed_from','observed_to','horizontal_crs','vertical_datum','known_horizontal_accuracy_m','known_vertical_accuracy_m'))+(json.dumps(record,ensure_ascii=False),))
    def feature(self,object_id,entity_type,source_id,source_feature_id,native,native_crs,wgs,utm,attributes,verification='source_mapped_not_independently_verified',confidence='source provenance; no independent control',observation_date=None,life_cycle='mapped_state_not_field_verified',tier=None,operation='CRS transform and explicit AOI clip'):
        self.db.execute('INSERT OR IGNORE INTO objects VALUES(?,?)',(object_id,entity_type))
        revision=self.db.execute('SELECT coalesce(max(revision),-1)+1 FROM versions WHERE object_id=?AND source_id=?',(object_id,source_id)).fetchone()[0]
        native_json=json.dumps(native,separators=(',',':'))if native else None
        cur=self.db.execute('INSERT INTO versions(object_id,source_id,source_feature_id,revision,native_geometry_json,native_crs,attributes_json,verification_state,confidence_basis,observation_date,life_cycle_state,building_tier)VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(object_id,source_id,str(source_feature_id),revision,native_json,native_crs,json.dumps(attributes,ensure_ascii=False),verification,confidence,observation_date,life_cycle,tier));fid=cur.lastrowid
        for table,g,srid in [('features_wgs84',wgs,4326),('features_utm',utm,32614)]:
            if g is not None and not g.is_empty:self.db.execute(f'INSERT INTO {table}(object_id,version_fid,geom)VALUES(?,?,?)',(object_id,fid,blob(g,srid)))
        self.db.execute('INSERT INTO modifications(version_fid,operation,parameters_json,original_geometry_sha256,processed_geometry_sha256,created_at)VALUES(?,?,?,?,?,?)',(fid,operation,json.dumps({'native_crs':native_crs,'processed_crs':'EPSG:32614','coordinates':'2D; unknown heights never filled with zero'}),hashlib.sha256(native_json.encode()).hexdigest()if native_json else None,hashlib.sha256(shapely.to_wkb(utm)).hexdigest()if utm is not None else None,datetime.datetime.now(datetime.timezone.utc).isoformat()))
    def tile(self,record,processed_fraction,availability):self.db.execute('INSERT INTO tiles(tile_id,size_m,processed_fraction,source_availability_json,geom)VALUES(?,?,?,?,?)',(record['id'],record['size_m'],processed_fraction,json.dumps(availability),blob(record['geometry'],32614)))
    def close(self):
        for table in ('features_wgs84','features_utm','tiles'):
            bounds=[unblob(row[0]).bounds for row in self.db.execute(f'SELECT geom FROM {table}')]
            if bounds:self.db.execute('UPDATE gpkg_contents SET min_x=?,min_y=?,max_x=?,max_y=?WHERE table_name=?',(min(b[0]for b in bounds),min(b[1]for b in bounds),max(b[2]for b in bounds),max(b[3]for b in bounds),table))
        self.db.commit();assert self.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not self.db.execute('PRAGMA foreign_key_check').fetchall();self.db.close()

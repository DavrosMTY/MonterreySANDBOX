"""Publish only licensed raw INEGI/OSM/Copernicus catalog facts; no search pages."""
import base64,hashlib,json,os,re,subprocess,zipfile
from pathlib import Path


def gh(*args):return subprocess.check_output(['gh',*args],text=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


if __name__=='__main__':
 r=json.loads(Path('docs/geo005/official-discovery.json').read_text());by={v['key']:v for v in r['records']}
 assert by['boundaries'].get('features_count')==51 and by['terms'].get('http_status')==200
 assert any('explotar comercialmente'in s for s in by['terms']['excerpts'])
 # Current official limits before publishing, no LFS/Actions artifact storage.
 limits=json.loads(gh('api','repos/github/docs/contents/data/variables/releases.yml'));assert "1000"in base64.b64decode(limits['content']).decode()
 large=json.loads(gh('api','repos/github/docs/contents/data/variables/large_files.yml'));assert '2 GiB'in base64.b64decode(large['content']).decode()
 entries=[('artifacts/geo005-research/boundaries.body','inegi_nl_municipal.geojson'),('artifacts/geo005-research/municipalities.body','inegi_nl_municipal_catalog.json'),('artifacts/geo005-research/copernicus_catalog.body','copernicus_tileList.txt')]
 for p in Path('artifacts/geo005-sector-inputs').glob('osm.json*'):entries.append((str(p),'north/'+p.name))
 out=Path('artifacts/geo005-source-snapshot');out.mkdir(exist_ok=False)
 manifest={'budget_usd':0,'source_commit':os.environ['GITHUB_SHA'],'files':[{'file':name,'bytes':Path(path).stat().st_size,'sha256':sha(path)}for path,name in entries],'inegi_terms':'https://www.inegi.org.mx/inegi/terminos.html','osm_terms':'https://www.openstreetmap.org/copyright','licenses':'INEGI free information terms / OpenStreetMap ODbL 1.0; Copernicus catalog only; retain provider metadata and attribute derivatives','search_pages_not_distributed':True,'geometry_is_INEGI_statistical_framework_not_legal_cadastral_boundary':True}
 archive=out/'GEO005_Licensed_Source_Snapshot.zip'
 with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED)as z:
  for path,name in entries:z.write(path,name)
  z.writestr('source-manifest.json',json.dumps(manifest,indent=2)+'\n')
 assert archive.stat().st_size<2*1024**3
 tag='geo005-inputs-'+os.environ['GITHUB_SHA'][:12]
 gh('release','create',tag,'--target',os.environ['GITHUB_SHA'],'--prerelease','--title','GEO-005 · fuentes oficiales y snapshot de adquisición','--notes','Fuentes públicas INEGI, catálogo Copernicus y OSM (ODbL). Snapshot de adquisición; no representa una metrópoli procesada ni precisión certificada. US$0.',str(archive))
 target=out/'verify';target.mkdir();gh('release','download',tag,'--pattern',archive.name,'--dir',str(target));assert sha(target/archive.name)==sha(archive)
 r['licensed_source_snapshot']={'tag':tag,'file':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'url':'https://github.com/DavrosMTY/MonterreySANDBOX/releases/tag/'+tag,'download_verified':True,'files':manifest['files']}
 Path('docs/geo005/official-discovery.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')

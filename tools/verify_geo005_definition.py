"""Read the official definition; publish statistical facts/excerpts, not the book."""
import datetime,hashlib,json,urllib.request
from pathlib import Path
from pypdf import PdfReader
url='https://www.gob.mx/cms/uploads/sedatu/MM2020_19102023.pdf';expected='8320f18a6342be7a3855cc104a4a3416964a4dfffd5b2d83bbd1fc9e37bcb7a2'
p=Path('artifacts/geo005-official-definition.pdf');p.parent.mkdir(exist_ok=True)
with urllib.request.urlopen(url,timeout=60)as r,p.open('wb')as out:
 size=0
 while True:
  data=r.read(1024**2)
  if not data:break
  size+=len(data)
  if size>200_000_000:raise ValueError('Official document cap')
  out.write(data)
assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
reader=PdfReader(p);evidence=[]
for i,page in enumerate(reader.pages):
 text=page.extract_text()or''
 if 'Monterrey'in text or '19006'in text:
  if 'Apodaca'in text or '19006'in text:evidence.append({'pdf_page_1based':i+1,'text':text[:18000]})
print('Official relevant pages:',[e['pdf_page_1based']for e in evidence]);assert evidence
Path('docs/geo005/metropolitan-definition.json').write_text(json.dumps({'official_url':url,'document_sha256':expected,'document_bytes':size,'title':'Metrópolis de México 2020','publication_date':'2023-10-19','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'facts_extraction_only_not_republication_of_book':True,'page_excerpts':evidence},ensure_ascii=False,indent=2)+'\n')

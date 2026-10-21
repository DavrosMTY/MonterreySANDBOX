"""Stream official AWS regional CSV, retaining only a few factual price records."""
import csv,datetime,hashlib,io,json
from pathlib import Path
import urllib.request
URL='https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonEC2/current/us-east-1/index.csv'

def main():
 result={'url':URL,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'records':[]}
 try:
  req=urllib.request.Request(URL,headers={'User-Agent':'MonterreyOpenWorld-public-research'})
  with urllib.request.urlopen(req,timeout=60) as response:
   text=io.TextIOWrapper(response,encoding='utf-8-sig',newline='')
   for line in text:
    if line.startswith('"SKU"'):headers=next(csv.reader([line]));break
   else:raise ValueError('Missing AWS CSV header')
   rows=csv.DictReader(text,fieldnames=headers)
   for i,row in enumerate(rows):
    if row.get('TermType')!='OnDemand':continue
    instance=row.get('Instance Type')
    wanted=instance in ('g4dn.2xlarge','g4dn.4xlarge','g5.2xlarge') and row.get('Operating System')=='Windows' and row.get('Tenancy')=='Shared' and row.get('Pre Installed S/W')=='NA' and row.get('CapacityStatus')=='Used'
    storage=row.get('Volume API Name')=='gp3' and row.get('Unit')=='GB-Mo' and row.get('Location')=='US East (N. Virginia)'
    if wanted or storage:
     result['records'].append({k:v for k,v in row.items() if v})
    found={r.get('Instance Type') for r in result['records']}
    if {'g4dn.2xlarge','g4dn.4xlarge','g5.2xlarge'}<=found and any(r.get('Volume API Name')=='gp3' for r in result['records']):break
    if i>900000:raise ValueError('Research row budget exceeded')
   result['rows_scanned']=i+1;result['http_status']=response.status
 except Exception as exc:result['error']=str(exc)
 Path(__file__).with_name('aws-catalog.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()

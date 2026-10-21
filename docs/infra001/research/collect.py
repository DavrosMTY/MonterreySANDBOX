"""Read-only public tariff collection on a standard public GitHub runner.

No account authentication, cloud provisioning, package installation or credentials.
Remote response text is data only; it is never executed or used as instructions.
"""
import concurrent.futures
import datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request

URLS={
 'airgpu_home':'https://airgpu.com/',
 'airgpu_help':'https://help.airgpu.com/',
 'azure_disks_eastus':'https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Storage%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20productName%20eq%20%27Standard%20SSD%20Managed%20Disks%27',
 'azure_premium_eastus':'https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Storage%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20productName%20eq%20%27Premium%20SSD%20Managed%20Disks%27',
 'azure_ip':'https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Virtual%20Network%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20productName%20eq%20%27IP%20Addresses%27',
 'azure_shutdown':'https://learn.microsoft.com/en-us/azure/virtual-machines/states-billing',
 'vagon_help':'https://docs.vagon.io/computer',
 'vagon_os':'https://vagon.io/computer',
 'paperspace_windows':'https://docs.digitalocean.com/products/paperspace/machines/details/pricing/',
 'epic_eula':'https://www.unrealengine.com/en-US/eula/unreal',
 'epic_faq':'https://www.unrealengine.com/en-US/faq',
 'aws_dcv_price':'https://docs.aws.amazon.com/dcv/latest/adminguide/setting-up-license.html',
 'aws_scheduler':'https://aws.amazon.com/eventbridge/pricing/'
}


class Text(HTMLParser):
 def __init__(self):super().__init__();self.fragments=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style'):self.skip+=1
  if tag in ('p','div','tr','li','h1','h2','h3','h4','td','th'):self.fragments.append('\n')
 def handle_endtag(self,tag):
  if tag in ('script','style'):self.skip=max(0,self.skip-1)
  if tag in ('p','div','tr','li','h1','h2','h3','h4','td','th'):self.fragments.append('\n')
 def handle_data(self,data):
  if not self.skip:self.fragments.append(data)


def fetch(item):
 key,url=item
 record={'id':key,'requested_url':url,'retrieved_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (MonterreyOpenWorld INFRA001 public pricing research)'})
  with urllib.request.urlopen(req,timeout=35) as response:
   body=response.read(12_000_001);record.update(http_status=response.status,final_url=response.url)
  if len(body)>12_000_000:raise ValueError('Response exceeds research size cap')
  record.update(response_bytes=len(body),response_sha256=hashlib.sha256(body).hexdigest())
  value=body.decode(errors='replace')
  if value.lstrip().startswith(('{','[')):
   data=json.loads(value)
   if key=='aws_windows_rates':
    matches=[]
    def visit(value,path=''):
     if isinstance(value,dict):
      if any(str(value.get(k,'')) in ('g4dn.2xlarge','g4dn.4xlarge','g5.2xlarge','g5.4xlarge') for k in ('Instance Type','instanceType','instanceTypeName')):matches.append(value);return
      for k,v in value.items():visit(v,path+'/'+k)
     elif isinstance(value,list):
      for v in value:visit(v,path)
    visit(data);record['matching_rates']=matches;record['top_keys']=list(data)[:15]
    if not matches:record['json_excerpt']=value[:14000]
   else:record['data']=data
  else:
   parser=Text();parser.feed(value);lines=[re.sub(r'\s+',' ',s).strip() for s in ''.join(parser.fragments).splitlines()];lines=[s for s in lines if s]
   keywords=r'\$|USD|/hr|/hour|per hour|monthly|storage|Windows|VRAM|A10|T4|RTX|suspend|stop|license|session 0|interactive|ephemeral|public repositor|self-hosted|autologon|first 100|Community'
   selected=set()
   for i,line in enumerate(lines):
    if re.search(keywords,line,re.I):selected.update(range(max(0,i-2),min(len(lines),i+4)))
   record['text_excerpt']=' '.join((' '.join(lines[i] for i in sorted(selected))).split()[:80])
   numeric=re.compile(r'\$|GB|TB|VRAM|vCPU|cores|A10|T4|RTX|P5000|P6000|g4dn|g5\.|NV12',re.I)
   record['fact_rows']=[{'line':i,'fact_tokens':re.findall(r'\$?\d+(?:[.,]\d+)?(?:/hour|/hr|/month)?|GB|TB|VRAM|vCPU|cores|A10G?|T4|RTX\d*|P5000|P6000|g4dn\.[A-Za-z0-9]+|NV12ads_A10_v5',line,re.I)} for i,line in enumerate(lines) if numeric.search(line)][:250]

 except Exception as exc:record['error']=str(exc)
 return record


def main():
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(fetch,URLS.items()))
 out=Path(__file__).with_name('supplement.json')
 out.write_text(json.dumps({'collected_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Unauthenticated official public URLs, read-only, no provisioning','records':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({r['id']:{'status':r.get('http_status'),'error':r.get('error'),'bytes':r.get('response_bytes')} for r in records},indent=2))


if __name__=='__main__':main()

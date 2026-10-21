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
 'aws_windows_rates':'https://b0.p.awsstatic.com/pricing/2.0/meteredUnitMaps/ec2/USD/current/ec2-windows-ondemand-without-sql/us-east-1/index.json',
 'aws_ec2':'https://aws.amazon.com/ec2/pricing/on-demand/',
 'aws_g4_specs':'https://aws.amazon.com/ec2/instance-types/g4/',
 'aws_ebs':'https://aws.amazon.com/ebs/pricing/',
 'aws_ipv4':'https://aws.amazon.com/vpc/pricing/',
 'aws_dcv':'https://aws.amazon.com/hpc/dcv/',
 'aws_stop':'https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html',
 'azure_eastus':'https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Virtual%20Machines%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20armSkuName%20eq%20%27Standard_NV12ads_A10_v5%27',
 'azure_texas':'https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Virtual%20Machines%27%20and%20armRegionName%20eq%20%27southcentralus%27%20and%20armSkuName%20eq%20%27Standard_NV12ads_A10_v5%27',
 'azure_disks':'https://prices.azure.com/api/retail/prices?$filter=serviceName%20eq%20%27Storage%27%20and%20armRegionName%20eq%20%27southcentralus%27%20and%20productName%20eq%20%27Standard%20SSD%20Managed%20Disks%27',
 'azure_gpu_specs':'https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/gpu-accelerated/nvadsa10v5-series',
 'azure_gpu_driver':'https://learn.microsoft.com/en-us/azure/virtual-machines/windows/n-series-driver-setup',
 'azure_egress':'https://azure.microsoft.com/en-us/pricing/details/bandwidth/',
 'airgpu':'https://airgpu.com/pricing/',
 'airgpu_faq':'https://airgpu.com/faq/',
 'airgpu_api':'https://airgpu.com/blog/',
 'paperspace':'https://www.paperspace.com/pricing',
 'vagon':'https://vagon.io/pricing',
 'vagon_api':'https://docs.vagon.io/streams',
 'shadow':'https://shadow.tech/en-US/shadowpc/offers',
 'vultr':'https://www.vultr.com/pricing/#cloud-gpu',
 'runpod':'https://www.runpod.io/pricing',
 'lambda':'https://lambda.ai/service/gpu-cloud',
 'github_runner_security':'https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions',
 'github_ephemeral':'https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/autoscaling-with-self-hosted-runners',
 'github_oidc_aws':'https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws',
 'github_runner_cost':'https://docs.github.com/en/billing/concepts/product-billing/github-actions',
 'epic_license':'https://www.unrealengine.com/en-US/license',
 'epic_github':'https://dev.epicgames.com/documentation/en-us/unreal-engine/downloading-source-code-in-unreal-engine?application_version=5.6',
 'vs_license':'https://visualstudio.microsoft.com/vs/community/',
 'windows_sessions':'https://learn.microsoft.com/en-us/windows/win32/services/interactive-services',
 'aws_grid':'https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/install-nvidia-driver.html',
 'aws_egress':'https://aws.amazon.com/ec2/pricing/on-demand/#Data_Transfer'
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
   record['text_excerpt']='\n'.join(lines[i] for i in sorted(selected))[:52000]
   raw_prices=[value[max(0,m.start()-90):m.end()+160] for m in list(re.finditer(r'\$\s*\d+(?:\.\d+)?|"price"\s*:\s*"?\d',value))[:70]]
   record['raw_price_fragments']=raw_prices
 except Exception as exc:record['error']=str(exc)
 return record


def main():
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:records=list(pool.map(fetch,URLS.items()))
 out=Path(__file__).with_name('snapshot.json')
 out.write_text(json.dumps({'collected_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Unauthenticated official public URLs, read-only, no provisioning','records':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({r['id']:{'status':r.get('http_status'),'error':r.get('error'),'bytes':r.get('response_bytes')} for r in records},indent=2))


if __name__=='__main__':main()

// Geographic inspection and comparison sidecar. No remote map/elevation API.
import * as THREE from 'three';

export function sampleGrid(grid,x,z){
 const n=grid.n,c=(x+1000)/2000*(n-1),r=(z+1000)/2000*(n-1);
 if(!Number.isFinite(c+r)||c<0||r<0||c>n-1||r>n-1)return null;
 const col=Math.min(Math.floor(c),n-2),row=Math.min(Math.floor(r),n-2),u=c-col,v=r-row;
 const h=grid.heights_m,a=h[row*n+col],b=h[row*n+col+1],d=h[(row+1)*n+col],e=h[(row+1)*n+col+1];
 return grid.interpolation==='native_triangles'?(u+v<=1?a+(b-a)*u+(d-a)*v:e+(d-e)*(1-u)+(b-e)*(1-v)):
  a*(1-u)*(1-v)+b*u*(1-v)+d*(1-u)*v+e*u*v;
}
export function slopeGrid(grid,x,z){
 const s=2000/(grid.n-1),left=Math.max(-1000,x-s),right=Math.min(1000,x+s),north=Math.max(-1000,z-s),south=Math.min(1000,z+s);
 return 100*Math.hypot((sampleGrid(grid,right,z)-sampleGrid(grid,left,z))/(right-left),(sampleGrid(grid,x,south)-sampleGrid(grid,x,north))/(south-north));
}
export function utm14ToLonLat(east,north){
 // Standard inverse Transverse Mercator series (WGS84, UTM 14N). Tested against PROJ.
 const a=6378137,e2=.0066943799901413165,k=.9996,ep=e2/(1-e2),e1=(1-Math.sqrt(1-e2))/(1+Math.sqrt(1-e2));
 const mu=(north/k)/(a*(1-e2/4-3*e2**2/64-5*e2**3/256));
 const f=mu+(3*e1/2-27*e1**3/32)*Math.sin(2*mu)+(21*e1**2/16-55*e1**4/32)*Math.sin(4*mu)+151*e1**3/96*Math.sin(6*mu)+1097*e1**4/512*Math.sin(8*mu);
 const t=Math.tan(f)**2,c=ep*Math.cos(f)**2,n=a/Math.sqrt(1-e2*Math.sin(f)**2),r=a*(1-e2)/(1-e2*Math.sin(f)**2)**1.5,d=(east-500000)/(n*k);
 const lat=f-n*Math.tan(f)/r*(d*d/2-(5+3*t+10*c-4*c*c-9*ep)*d**4/24+(61+90*t+298*c+45*t*t-252*ep-3*c*c)*d**6/720);
 const lon=-99*Math.PI/180+(d-(1+2*t+c)*d**3/6+(5-2*c+28*t-3*c*c+8*ep+24*t*t)*d**5/120)/Math.cos(f);
 return [lon*180/Math.PI,lat*180/Math.PI];
}
export async function readTopography(record){
 const r=await fetch(record.url);if(!r.ok)throw new Error(`Auditoría topográfica HTTP ${r.status}`);
 const b=await r.arrayBuffer(),hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
 if(hash!==record.sha256)throw new Error('Integridad incorrecta de auditoría topográfica');
 const data=await new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).json();return new Topography(data);
}
export class Topography{
 constructor(data){this.data=data;this.lastProbe=null;this.textures=new Map();}
 sample(x,z,model){
  const grid=this.data.models[model].grid,ground=sampleGrid(grid,x,z);if(ground===null)return null;
  const [lon,lat]=utm14ToLonLat(this.data.center[0]+x,this.data.center[1]-z);
  const heights=Object.fromEntries(Object.entries(this.data.models).map(([key,m])=>[key,sampleGrid(m.grid,x,z)]));
  return {model,x,z,lon,lat,ground_m:ground,slope_percent:slopeGrid(grid,x,z),heights_m:heights,datum:'EGM2008',
    source:this.data.models[model].source,native_resolution_m:this.data.models[model].native_resolution_m,absolute_vertical_accuracy_m:null,
    source_year:this.data.models[model].source_year,source_warning:this.data.uncertainty};
 }
 texture(model){
  if(this.textures.has(model))return this.textures.get(model);
  const heat=this.data.models[model].heat,n=heat.n,pixels=new Uint8Array(n*n*4);
  for(let i=0;i<heat.values.length;i++){
   const v=heat.values[i];pixels.set(v>=3?[242,48,31,235]:v>=2?[255,175,28,220]:[0,0,0,0],i*4);
  }
  const t=new THREE.DataTexture(pixels,n,n,THREE.RGBAFormat);t.minFilter=t.magFilter=THREE.NearestFilter;t.needsUpdate=true;this.textures.set(model,t);return t;
 }
 inspect(point,model,system){
  const p=this.sample(point.x,point.z,model);if(!p)return null;
  this.lastProbe={...p,rendered_height_m:point.y,system};return this.lastProbe;
 }
}

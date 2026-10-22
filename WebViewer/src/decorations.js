// Original low-poly CC0 art. Source coordinates and inference flags are in the sidecar.
import * as THREE from 'three';
import {mergeGeometries} from './vendor/three/examples/jsm/utils/BufferGeometryUtils.js';

function part(geometry,color,position=[0,0,0],rotation=null){
 const g=geometry.index?geometry.toNonIndexed():geometry;g.deleteAttribute('uv');
 if(rotation)g.rotateZ(rotation);g.translate(...position);
 const c=new THREE.Color(color),a=new Float32Array(g.attributes.position.count*3);
 for(let i=0;i<a.length;i+=3){a[i]=c.r;a[i+1]=c.g;a[i+2]=c.b;}
 g.setAttribute('color',new THREE.BufferAttribute(a,3));return g;
}
const box=(size,pos,color)=>part(new THREE.BoxGeometry(...size),color,pos);
function merged(parts){const g=mergeGeometries(parts);for(const p of parts)p.dispose();g.userData.shared=true;return g;}
const seed = text=>{let h=2166136261;for(const c of text)h=Math.imul(h^c.charCodeAt(0),16777619);return (h>>>0)/4294967296;};

export class Decorations {
 constructor(){
  this.material=new THREE.MeshStandardMaterial({vertexColors:true,roughness:.88,metalness:.08});this.material.userData.shared=true;
  this.glow=new THREE.MeshStandardMaterial({vertexColors:true,roughness:.3,emissive:'#ffe3a1',emissiveIntensity:0});this.glow.userData.shared=true;
  this.white=new THREE.MeshStandardMaterial({color:'#e4e2c8',roughness:.9,polygonOffset:true,polygonOffsetFactor:-2});this.white.userData.shared=true;
  this.yellow=new THREE.MeshStandardMaterial({color:'#d4ad45',roughness:.9,polygonOffset:true,polygonOffsetFactor:-2});this.yellow.userData.shared=true;
  this.templates={
   trunk:merged([part(new THREE.CylinderGeometry(.12,.20,1,5),'#62503a')]),
   crownFar:merged([part(new THREE.IcosahedronGeometry(1,0),'#637b4c')]),
   crownNear:merged([part(new THREE.IcosahedronGeometry(1,1),'#637b4c')]),
   lamp:merged([part(new THREE.CylinderGeometry(.055,.10,7.6,6),'#596267',[0,3.8,0]),box([1.1,.12,.1],[.5,7.5,0],'#697374'),box([.65,.16,.35],[.85,7.4,0],'#b4b8ab')]),
   bulb:merged([box([.55,.035,.27],[.85,7.30,0],'#fff0af')]),
   bench:merged([box([1.65,.12,.48],[0,.48,0],'#a17f52'),box([1.65,.45,.09],[0,.82,-.22],'#b18d5c'),box([.10,.45,.4],[-.6,.22,0],'#4b5551'),box([.10,.45,.4],[.6,.22,0],'#4b5551')]),
   signal:merged([part(new THREE.CylinderGeometry(.06,.09,3.8,6),'#626b65',[0,1.9,0]),box([.35,1.05,.28],[0,3.25,0],'#242a25'),part(new THREE.SphereGeometry(.10,6,4),'#b94135',[0,3.55,.17]),part(new THREE.SphereGeometry(.10,6,4),'#c6a13b',[0,3.25,.17]),part(new THREE.SphereGeometry(.10,6,4),'#4c8563',[0,2.95,.17])]),
   stop:merged([part(new THREE.CylinderGeometry(.035,.05,2.5,5),'#7a817b',[0,1.25,0])]),
   bin:merged([part(new THREE.CylinderGeometry(.28,.23,.8,8),'#516558',[0,.4,0])]),
   bike_rack:merged([box([1.9,.09,.07],[0,.6,0],'#a5aba4'),box([.07,.6,.09],[-.85,.3,0],'#a5aba4'),box([.07,.6,.09],[.85,.3,0],'#a5aba4')]),
   paint:new THREE.PlaneGeometry(1,1).rotateX(-Math.PI/2),
  };this.templates.paint.userData.shared=true;
  const canvas=document.createElement('canvas');canvas.width=128;canvas.height=128;
  const ctx=canvas.getContext('2d');ctx.fillStyle='#bb342b';ctx.fillRect(0,0,128,128);ctx.strokeStyle='#f4eedc';ctx.lineWidth=7;ctx.strokeRect(7,7,114,114);ctx.fillStyle='white';ctx.font='bold 32px sans-serif';ctx.textAlign='center';ctx.fillText('ALTO',64,75);
  this.signTexture=new THREE.CanvasTexture(canvas);this.signTexture.colorSpace=THREE.SRGBColorSpace;
  this.signMaterial=new THREE.MeshStandardMaterial({map:this.signTexture,roughness:.8,side:THREE.DoubleSide});this.signMaterial.userData.shared=true;
  this.templates.sign=new THREE.CircleGeometry(.40,8);this.templates.sign.userData.shared=true;
  this.sectors=new Map();this.vegetation=true;this.details=true;this.paint=true;this.enabled=true;
 }
 create(records,center){
  const root=new THREE.Group();root.name='WORLD002_visual_overlay';root.userData.visualDecoration=true;
  const buckets=new Map();
  const add=(type,r,position,scale=[1,1,1],rotation=null,category='details',near=false)=>{
    const key=type+':'+category+':'+near+':'+(type==='paint'?(r.kind==='lane_yellow'?'yellow':'white'):'');
    if(!buckets.has(key))buckets.set(key,{type,category,near,entries:[]});
    buckets.get(key).entries.push({r,position,scale,rotation});
  };
  for(const r of records){
   const p=r.position,s=seed(r.source_id),height=4.2+s*1.5;
   if(r.kind==='tree'||r.kind==='palm'){
    add('trunk',r,[p[0],p[1]+height*.5,p[2]],[1,height,1],null,'vegetation');
    add('crownFar',r,[p[0],p[1]+height+1.2,p[2]],[2+s,2.4,2+s],null,'vegetation',false);
    for(let k=0;k<3;k++)add('crownNear',r,[p[0]+Math.sin(k*2.1)*1.1,p[1]+height+1.4+k*.22,p[2]+Math.cos(k*2.1)*1.1],[1.7+s,1.9,1.7+s],null,'vegetation',true);
   }else if(r.kind.startsWith('lane_')||r.kind==='crossing'){
    // Match the source road's longitudinal slope; overlays never change the road mesh.
    const q=new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.atan(-r.slope||0),r.yaw||0,0,'YXZ'));
    add('paint',r,p,[r.width,.018,r.length],q,'paint');
   }else{
    const type=this.templates[r.kind]?r.kind:'stop';add(type,r,p);
    if(r.kind==='lamp')add('bulb',r,p);
    if(r.kind==='stop')add('sign',r,[p[0],p[1]+2.3,p[2]], [1,1,1]);
   }
  }
  for(const b of buckets.values()){
    const material=b.type==='paint'?(b.entries[0].r.kind==='lane_yellow'?this.yellow:this.white):b.type==='bulb'?this.glow:b.type==='sign'?this.signMaterial:this.material;
    const mesh=new THREE.InstancedMesh(this.templates[b.type],material,b.entries.length);
    mesh.name='WORLD002_'+b.type;mesh.userData.category=b.category;mesh.userData.near=b.near;mesh.layers.set(1);
    const object=new THREE.Object3D();
    b.entries.forEach(({r,position,scale,rotation},i)=>{
      object.position.fromArray(position);object.scale.fromArray(scale);object.quaternion.copy(rotation||new THREE.Quaternion());object.updateMatrix();mesh.setMatrixAt(i,object.matrix);
      if(b.category==='vegetation'&&b.type!=='trunk')mesh.setColorAt(i,new THREE.Color().setHSL(.24+seed(r.source_id)*.06,.22,.64+seed(r.source_id)*.18));
    });mesh.instanceMatrix.needsUpdate=true;mesh.castShadow=b.category!=='paint';mesh.receiveShadow=true;mesh.computeBoundingSphere();root.add(mesh);
  }
  root.visible=this.enabled;this.sectors.set(root,{center});return root;
 }
 update(camera,profile){
  for(const [root,{center}]of this.sectors){
   const distance=Math.hypot(camera.position.x-center[0],camera.position.z-center[2]);
   const near=profile!=='low'&&distance<(profile==='high'?400:200);
   root.visible=this.enabled;
   for(const child of root.children){
    child.visible=this[child.userData.category];
    if(child.name.includes('crownNear'))child.visible&&=near;
    if(child.name.includes('crownFar'))child.visible&&=!near;
   }
  }
 }
 release(root){this.sectors.delete(root);}
 setNight(value){this.glow.emissiveIntensity=value*2.8;}
 snapshot(){return {overlay_sectors:this.sectors.size,visible_instances:[...this.sectors.keys()].reduce((sum,r)=>sum+(r.visible?r.children.filter(n=>n.visible).reduce((a,n)=>a+n.count,0):0),0),vegetation:this.vegetation,details:this.details,markings:this.paint,tree_lod:'20 triangles far, 3x80 triangles near; existing GIS unchanged'};}
}

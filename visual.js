import * as THREE from 'three';
import {CityMaterials} from './materials.js';
import {Decorations} from './decorations.js';
import {MountainBackground} from './background.js';

export const LIGHTS={
 day:{sky:'#afd0df',sun:'#fff0d5',sunIntensity:2.5,ambient:1.4,position:[-900,2000,800],night:0,exposure:1.05},
 sunset:{sky:'#bc9189',sun:'#ff9e56',sunIntensity:2.1,ambient:.75,position:[-1600,850,900],night:.12,exposure:1.05},
 night:{sky:'#101b31',sun:'#a4badd',sunIntensity:.25,ambient:.28,position:[-800,2000,1000],night:1,exposure:1.15},
};
export class VisualLayer {
 constructor({scene,renderer,sun,ambient,world}) {
  Object.assign(this,{scene,renderer,sun,ambient,world});this.city=new CityMaterials();this.enabled=['WORLD-002','GEO-004'].includes(world.milestone);
  this.sectors=new Set();this.period='day';this.shadows='auto';this.profile='low';this.fogEnabled=true;this.props=new Decorations();this.overlay=null;this.background=null;this.backgroundEnabled=true;this.attachments=new Map();
 }
 async load(){
  const read=async(record)=>{
   const r=await fetch(new URL(record.url,location.href));if(!r.ok)throw new Error(`Visual layer HTTP ${r.status}`);
   const b=await r.arrayBuffer();const hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');
   if(hash!==record.sha256)throw new Error('Visual layer integrity mismatch');
   return record.url.endsWith('.gz')?new Response(new Blob([b]).stream().pipeThrough(new DecompressionStream('gzip'))).json():JSON.parse(new TextDecoder().decode(b));
  };
  if(this.world.visual_catalog)this.city.setCatalog(await read(this.world.visual_catalog));
  if(this.world.visual_overlay)this.overlay=await read(this.world.visual_overlay);
  if(this.world.background){this.background=new MountainBackground(await read(this.world.background),this.city.get('Mountains'));this.background.setLOD(this.profile);this.setLight(this.period);}
 }
 prepare(root,sector){
  root.traverse(node=>{
   if(!node.isMesh)return;
   node.userData.grayboxMaterial=node.material;
   if(!['WORLD-002','GEO-004'].includes(this.world.milestone))return;
   node.userData.cityMaterial=this.city.get(node.name);
   node.material=this.enabled?node.userData.cityMaterial:node.userData.grayboxMaterial;
  });this.sectors.add(root);
  if(this.overlay&&sector){const group=this.props.create(this.overlay.sectors[sector.cell_id||sector.id]||[],sector.center);root.add(group);this.attachments.set(root,group);}

 }
 release(root){
  this.sectors.delete(root);const decor=this.attachments.get(root);if(decor){this.props.release(decor);this.attachments.delete(root);}
  root.traverse(node=>{if(node.userData.grayboxMaterial){
    const materials=Array.isArray(node.userData.grayboxMaterial)?node.userData.grayboxMaterial:[node.userData.grayboxMaterial];
    for(const m of materials)m.dispose();
  }});
 }
 setMode(mode){
  this.enabled=mode==='city';this.props.enabled=this.enabled;if(this.background)this.background.enabled=this.enabled&&this.backgroundEnabled;
  for(const root of this.sectors)root.traverse(node=>{if(node.userData.cityMaterial)node.material=this.enabled?node.userData.cityMaterial:node.userData.grayboxMaterial;});
 }
 setLight(period){
  this.period=period;const p=LIGHTS[period];this.city.uniforms.uMowNight.value=p.night;this.props.setNight(p.night);
  this.scene.background=new THREE.Color(p.sky);this.sun.color.set(p.sun);this.sun.intensity=p.sunIntensity;
  this.sun.position.fromArray(p.position);this.ambient.intensity=p.ambient;this.renderer.toneMappingExposure=p.exposure;
  this.setFog(this.fogEnabled);
 }
 setFog(value){this.fogEnabled=value;const radius={low:310,balanced:620,high:1500}[this.profile];this.scene.fog=value?new THREE.Fog(this.scene.background,radius*.8,radius*2.4):null;this.background?.setLight(LIGHTS[this.period],this.scene.background,value);}
 setProfile(name){this.profile=name;this.setShadows(this.shadows);this.background?.setLOD(name);this.setFog(this.fogEnabled);}
 setShadows(value){this.shadows=value;const active=value==='on'||value==='auto'&&this.profile==='high';
  this.renderer.shadowMap.enabled=active;this.sun.castShadow=active;this.sun.shadow.camera.layers.enable(1);
  this.scene.traverse(n=>{if(n.material)for(const m of Array.isArray(n.material)?n.material:[n.material])m.needsUpdate=true;});
 }
 setFlag(name,value){if(name==='background'){this.backgroundEnabled=value;if(this.background)this.background.enabled=value&&this.enabled;}else this.props[name]=value;}
 update(camera){this.props.enabled=this.enabled;this.props.update(camera,this.profile);if(this.background)this.background.enabled=this.enabled&&this.backgroundEnabled;}
 render(renderer,camera){
  renderer.autoClear=false;renderer.info.autoReset=false;renderer.info.reset();renderer.setClearColor(this.scene.background);renderer.clear();
  this.background?.render(renderer,camera);renderer.clearDepth();const sky=this.scene.background;this.scene.background=null;renderer.render(this.scene,camera);this.scene.background=sky;
 }
 snapshot(){return {props:this.props.snapshot(),background:this.background?.snapshot(),mode:this.enabled?'city':'graybox',period:this.period,shadows:this.shadows,compiled_materials:[...this.city.compiled],resident_visual_sectors:this.sectors.size};}
}

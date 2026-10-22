// Georeferenced Copernicus background, outside the playable pilot. Separate depth pass.
import * as THREE from 'three';
import {geometryBytes} from './core.js';
export class MountainBackground {
 constructor(data,material){
  this.data=data;this.scene=new THREE.Scene();this.camera=new THREE.PerspectiveCamera();this.camera.near=20;this.camera.far=45000;
  this.light=new THREE.HemisphereLight('#e4efff','#645b48',1.3);this.sun=new THREE.DirectionalLight('#fff0db',2);this.sun.position.set(-1000,2000,800);
  this.scene.add(this.light,this.sun);this.material=material;this.mesh=null;this.enabled=true;this.current=-1;
 }
 setLOD(profile){
  const index={low:0,balanced:1,high:2}[profile];if(index===this.current)return;this.current=index;
  const lod=this.data.lods[index],n=lod.n,positions=new Float32Array(n*n*3),indices=[];
  for(let row=0;row<n;row++)for(let col=0;col<n;col++){
   const i=(row*n+col)*3;positions[i]=-18000+col*lod.spacing_m;positions[i+1]=lod.heights_m[row*n+col];positions[i+2]=-18000+row*lod.spacing_m;
  }
  for(let r=0;r<n-1;r++)for(let c=0;c<n-1;c++){
   const x=-18000+(c+.5)*lod.spacing_m,z=-18000+(r+.5)*lod.spacing_m;
   if(Math.abs(x)+lod.spacing_m*.5<1000&&Math.abs(z)+lod.spacing_m*.5<1000)continue;
   const a=r*n+c,b=a+1,d=a+n,e=d+1;indices.push(a,d,b,b,d,e);
  }
  const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setIndex(indices);geometry.computeVertexNormals();
  if(this.mesh){this.scene.remove(this.mesh);this.mesh.geometry.dispose();}
  this.mesh=new THREE.Mesh(geometry,this.material);this.mesh.name='Copernicus_non_playable_background';this.mesh.userData.source_sha256=this.data.source_sha256;
  this.scene.add(this.mesh);
 }
 setLight(settings,sky,fogEnabled){
  this.scene.fog=fogEnabled?new THREE.Fog(sky,3500,28000):null;
  this.light.intensity=settings.ambient;this.sun.color.set(settings.sun);this.sun.intensity=settings.sunIntensity;this.sun.position.fromArray(settings.position);
 }
 render(renderer,camera){
  if(!this.enabled||!this.mesh)return;
  this.camera.position.copy(camera.position);this.camera.quaternion.copy(camera.quaternion);this.camera.fov=camera.fov;this.camera.aspect=camera.aspect;this.camera.updateProjectionMatrix();
  renderer.render(this.scene,this.camera);
 }
 bytes(){return this.mesh?geometryBytes(this.scene):0;}
 snapshot(){return {visible:this.enabled,lod_spacing_m:this.data.lods[this.current]?.spacing_m,triangles:this.mesh?this.mesh.geometry.index.count/3:0,not_playable:true,source_sha256:this.data.source_sha256};}
}

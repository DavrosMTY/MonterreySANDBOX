// Original WORLD-002 procedural surface recipes: no image downloads or material maps.
import * as THREE from 'three';

export function styleClass(category) {
  return ({residential:0,commercial:1,corporate:2,industrial:3,civic:4,unknown:5})[category] ?? 5;
}
const shared = `
varying vec3 vMowPosition;
varying vec4 vMowStyle;
uniform float uMowNight;
uniform float uMowHeat;
uniform sampler2D uMowHeatMap;
uniform float uMowFloor;
uniform float uMowBay;
uniform vec3 uMowPalette[8];
float mowHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float mowNoise(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);return mix(mix(mowHash(i),mowHash(i+vec2(1,0)),f.x),mix(mowHash(i+vec2(0,1)),mowHash(i+vec2(1,1)),f.x),f.y);}
float mowBox(vec2 p,vec2 lo,vec2 hi){vec2 aa=max(fwidth(p),vec2(.002));vec2 a=smoothstep(lo-aa,lo+aa,p);vec2 b=1.0-smoothstep(hi-aa,hi+aa,p);return a.x*a.y*b.x*b.y;}
vec3 mowPalette(float s){return uMowPalette[int(floor(fract(s)*8.0))];}
`;
const facade = `
float mowClass=vMowStyle.x;
float mowSeed=vMowStyle.y;
float mowHeight=max(2.0,vMowStyle.w);
float mowY=vMowPosition.y-vMowStyle.z;
// World surface orientation is derived from position derivatives, independent of view rotation.
vec3 mowWN=normalize(cross(dFdx(vMowPosition),dFdy(vMowPosition)));
float mowRoof=step(.65,abs(mowWN.y));
float mowU=abs(mowWN.x)>abs(mowWN.z)?vMowPosition.z:vMowPosition.x;
float mowFloor=uMowFloor;
vec2 mowUV=vec2(mowU/uMowBay+mowSeed*13.0,mowY/mowFloor);
vec2 mowCell=fract(mowUV);
float mowWindow=mowBox(mowCell,vec2(.16,.26),vec2(.80,.79));
mowWindow*=step(1.0,mowY)*step(mowY,mowHeight-.6)*(1.0-mowRoof);
vec3 mowWall=mowPalette(mowSeed);
float mowBrick=step(.72,fract(mowSeed*7.13));
vec2 mowBrickUV=vec2(mowU*2.8+mod(floor(mowY*5.5),2.0)*.5,mowY*5.5);
vec2 mowBrickCell=fract(mowBrickUV);
float mowMortar=1.0-mowBox(mowBrickCell,vec2(.045,.08),vec2(.955,.91));
vec3 mowBrickColor=mix(vec3(.39,.19,.10),vec3(.56,.29,.16),mowHash(floor(mowBrickUV)));
mowWall=mix(mowWall,mix(mowBrickColor,vec3(.48,.43,.35),mowMortar),mowBrick*.7);
float mowGrain=mowHash(floor(vMowPosition.xz*14.0)+floor(mowY*11.0));
mowWall*=.92+.12*mowGrain;
if(mowClass> .5 && mowClass<1.5){mowWall=mix(vec3(.72,.65,.50),mowPalette(mowSeed),.25);mowWindow=max(mowWindow,mowBox(mowCell,vec2(.06,.08),vec2(.92,.90))*step(mowY,3.0)*(1.0-mowRoof));}
if(mowClass>1.5 && mowClass<2.5){mowWall=vec3(.28,.34,.37);mowWindow=mowBox(mowCell,vec2(.045,.055),vec2(.955,.945))*(1.0-mowRoof)*step(.8,mowY);}
if(mowClass>2.5 && mowClass<3.5){mowWall=mix(vec3(.40,.43,.41),vec3(.64,.62,.53),.5+.5*sin(mowU*22.0));mowWindow*=step(mowHeight*.65,mowY);}
if(mowClass>3.5 && mowClass<4.5){mowWall=vec3(.65,.58,.43);mowWindow=mowBox(mowCell,vec2(.25,.16),vec2(.66,.76))*step(1.0,mowY)*(1.0-mowRoof);}
float mowDoor=mowBox(vec2(fract(mowU/13.0+mowSeed),mowY),vec2(.38,.02),vec2(.50,2.35))*(1.0-mowRoof);
if(mowClass>2.5 && mowClass<3.5)mowDoor=mowBox(vec2(fract(mowU/16.0+mowSeed),mowY),vec2(.22,.02),vec2(.62,4.0))*(1.0-mowRoof);
mowWindow*=1.0-mowDoor;
vec3 mowGlass=mix(vec3(.035,.10,.14),vec3(.15,.29,.34),smoothstep(.2,.9,mowCell.y));
mowGlass+=vec3(.08,.10,.10)*pow(mowNoise(vec2(mowU*.2,mowY*.3)),3.0);
vec3 mowColor=mix(mowWall,mowGlass,mowWindow);
mowColor=mix(mowColor,vec3(.07,.09,.08),mowDoor);
vec3 mowRoofColor=mix(vec3(.29,.30,.28),vec3(.49,.30,.20),step(.65,mowSeed));
if(mowClass>2.5&&mowClass<3.5)mowRoofColor=vec3(.45,.48,.47)*( .85+.15*sin(vMowPosition.x*13.0));
mowColor=mix(mowColor,mowRoofColor,mowRoof);
mowColor*=mix(.72,1.0,smoothstep(0.0,.55,mowY));
diffuseColor.rgb=mowColor;
float mowLit=mowWindow*step(.65,mowHash(floor(mowUV)+mowSeed))*uMowNight;
`;
const surface = system => {
  if (system === 'Mountains') return `
float n=mowNoise(vMowPosition.xz*.006);float rock=smoothstep(1000.,2200.,vMowPosition.y);diffuseColor.rgb=mix(vec3(.18,.25,.18),vec3(.39,.38,.33),rock)*(.85+.25*n);float mowWindow=0.;float mowLit=0.;`;
  if (system === 'Tunnels') return `diffuseColor.rgb=vec3(.28,.29,.27)*(.9+.15*mowHash(floor(vMowPosition.xy*8.)));float mowWindow=0.;float mowLit=0.;`;
  if (system === 'Landscape') return `
float mowT=mowNoise(vMowPosition.xz*.018);float mowMicro=mowHash(floor(vMowPosition.xz*9.0));
diffuseColor.rgb=mix(vec3(.25,.29,.17),vec3(.46,.37,.25),mowT)*(.90+.15*mowMicro);
float mowWindow=0.0;float mowLit=0.0;`;
  if (system === 'Sidewalks') return `
vec2 mowP=fract(vMowPosition.xz/1.15);float mowSeam=1.0-mowBox(mowP,vec2(.022),vec2(.978));
float mowGrain=mowHash(floor(vMowPosition.xz*15.0));
diffuseColor.rgb=mix(vec3(.52,.48,.39)*(.94+.12*mowGrain),vec3(.24,.24,.21),mowSeam*.55);
float mowWindow=0.0;float mowLit=0.0;`;
  return `
float mowGrain=mowHash(floor(vMowPosition.xz*20.0));
float mowAggregate=mowNoise(vMowPosition.xz*3.0);
vec3 mowAsphalt=vec3(.065,.072,.074)*(.8+.4*mowGrain)+vec3(.025)*mowAggregate;
float mowS=vMowStyle.x;
if(mowS> .5 && mowS<1.5)mowAsphalt=vec3(.31,.32,.30)*(.9+.2*mowGrain);
if(mowS>1.5){vec2 c=fract(vMowPosition.xz*vec2(3.,5.));float seam=1.-mowBox(c,vec2(.035,.06),vec2(.965,.94));mowAsphalt=mix(vec3(.24,.23,.21),vec3(.10),seam);}
diffuseColor.rgb=mowAsphalt;
float mowWindow=0.0;float mowLit=0.0;`;
};

export class CityMaterials {
  constructor() {
    this.uniforms = {uMowNight:{value:0},uMowHeat:{value:0},uMowHeatMap:{value:new THREE.DataTexture(new Uint8Array(4),1,1)},uMowFloor:{value:3.2},uMowBay:{value:3.1},uMowPalette:{value:['#e6d4b5','#d9a57b','#dca7a1','#a7b6a2','#a7bdc4','#e4ddca','#b98b65','#dad7cb'].map(x=>new THREE.Color(x))}};
    this.uniforms.uMowHeatMap.value.needsUpdate=true;
    this.materials = new Map(); this.compiled = new Set();
  }
  setCatalog(catalog){
    this.uniforms.uMowFloor.value=catalog.floor_height_default_m;this.uniforms.uMowBay.value=catalog.bay_width_default_m;
    this.uniforms.uMowPalette.value=catalog.palette.map(x=>new THREE.Color(x));
  }
  get(system) {
    if(this.materials.has(system))return this.materials.get(system);
    const material=new THREE.MeshStandardMaterial({color:'white',roughness:.9,metalness:.02,flatShading:true});
    material.name=`WORLD002_${system}`; material.userData.shared=true; material.defaultAttributeValues={_mow_style:[0,0,0,0]};
    material.onBeforeCompile=shader=>{
      Object.assign(shader.uniforms,this.uniforms);
      shader.vertexShader=shader.vertexShader.replace('#include <common>',`#include <common>\nattribute vec4 _mow_style;varying vec3 vMowPosition;varying vec4 vMowStyle;`)
        .replace('#include <begin_vertex>',`#include <begin_vertex>\nvMowPosition=(modelMatrix*vec4(position,1.0)).xyz;vMowStyle=_mow_style;`);
      shader.fragmentShader=shader.fragmentShader.replace('#include <common>',`#include <common>\n${shared}`)
        .replace('#include <color_fragment>',`#include <color_fragment>\n${system==='Buildings'?facade:surface(system)}
${['Buildings','Mountains'].includes(system)?'':`if(uMowHeat>0.5 && abs(vMowPosition.x)<=1000. && abs(vMowPosition.z)<=1000.){vec4 heat=texture2D(uMowHeatMap,(vMowPosition.xz+1000.)/2000.);diffuseColor.rgb=mix(diffuseColor.rgb,heat.rgb,heat.a);}`}`)
        .replace('#include <roughnessmap_fragment>',`#include <roughnessmap_fragment>\nroughnessFactor=mix(.90,.22,mowWindow);`)
        .replace('#include <emissivemap_fragment>',`#include <emissivemap_fragment>\ntotalEmissiveRadiance+=vec3(1.0,.60,.23)*mowLit*1.8;`);
      this.compiled.add(system);
    };
    material.customProgramCacheKey=()=>`WORLD002-${system}-1`;
    this.materials.set(system,material); return material;
  }
  dispose(){for(const m of this.materials.values())m.dispose();this.materials.clear();}
}

// Optional geographic navigation. GIS snapshots remain independent of rendering.
import {utm14ToLonLat} from './topography.js';

export async function selectMetroRegion(root){
 if(!root.metro_catalog)return {world:root,metro:null,region:null};
 const response=await fetch(root.metro_catalog);if(!response.ok)throw new Error('No se encontró el catálogo metropolitano');
 const metro=await response.json();const id=new URL(location.href).searchParams.get('region')||metro.default_region;
 const region=metro.regions.find(r=>r.id===id);if(!region)throw new Error('Región no registrada');
 if(!/^regions\/[a-z0-9-]+\/world\.json$/.test(region.world_url))throw new Error('Ruta de región no permitida');
 const r=await fetch(region.world_url);if(!r.ok)throw new Error('No se encontró el sector seleccionado');
 return {world:await r.json(),metro,region};
}

export function metroControls({metro,region,world,scene,camera,stream}){
 if(!metro)return {update(){},snapshot:()=>null,apply(){}};
 document.querySelector('.edition i').textContent='METRO–001';document.querySelector('.corner .pill').textContent='GEO–005 / METRO–001';
 document.querySelector('h1').innerHTML='Monterrey.<br><em>Por regiones.</em>';
 document.querySelector('.intro').textContent=region.label+' · MDT 5 m, levantamiento 2007. Alturas y fachadas sin verificación independiente.';
 document.querySelector('.facts').innerHTML=`<span><b>${region.buildings.toLocaleString('es-MX')}</b> edificios</span><span><b>1:1</b> escala UTM</span>`;
 const section=document.createElement('section');section.id='metro-tools';
 const link=document.createElement('a');link.href='./metro.html';link.textContent='↗ Cobertura metropolitana y municipios';section.append(link);
 const label=document.createElement('label');label.textContent='Región procesada ';const select=document.createElement('select');select.id='metro-region';
 for(const item of metro.regions){const o=document.createElement('option');o.value=item.id;o.textContent=item.label;o.selected=item.id===region.id;select.append(o);}label.append(select);section.append(label);
 select.onchange=()=>{const url=new URL(location.href);url.searchParams.set('region',select.value);location.assign(url);};
 const quality=document.createElement('p');quality.className='hint';quality.id='metro-confidence';quality.textContent='Confianza: huellas OSM · edificios C. Alturas, carriles ausentes y estructuras: estimaciones. A/B verificados: 0. Precisión absoluta: desconocida.';section.append(quality);
 const flags={Landscape:true,Buildings:true,Roads:true,Bridges:true,Tunnels:true,Sidewalks:true};
 for(const [title,systems]of [['Terreno',['Landscape']],['Edificios',['Buildings']],['Red vial',['Roads','Bridges','Tunnels','Sidewalks']]]){
  const row=document.createElement('label');row.className='check';const input=document.createElement('input');input.type='checkbox';input.checked=true;input.dataset.metroLayer=systems[0];row.append(input,document.createTextNode(' '+title));input.onchange=()=>{for(const s of systems)flags[s]=input.checked;apply();};section.append(row);
 }
 const coords=document.createElement('p');coords.className='hint';coords.id='metro-coordinates';section.append(coords);
 const button=document.createElement('button');button.id='cartographic';button.textContent='Fidelidad cartográfica · sin adornos';button.onclick=()=>{document.getElementById('visual-mode').value='graybox';document.getElementById('visual-mode').dispatchEvent(new Event('change'));for(const id of ['vegetation','details','paint','background']){const el=document.getElementById(id);el.checked=false;el.dispatchEvent(new Event('change'));}};section.append(button);
 document.querySelector('.views').before(section);
 function apply(){for(const {scene:root}of stream.resident.values())root.traverse(n=>{if(n.isMesh&&flags[n.userData.system??n.name]!==undefined)n.visible=flags[n.userData.system??n.name];});}
 function update(){apply();const east=world.center_easting_northing_m[0]+camera.position.x,north=world.center_easting_northing_m[1]-camera.position.z;const ll=utm14ToLonLat(east,north);coords.textContent=`Cámara: ${ll[1].toFixed(6)}, ${ll[0].toFixed(6)} · UTM ${east.toFixed(1)} E / ${north.toFixed(1)} N · ${camera.position.y.toFixed(1)} m EGM2008 (altura del modelo)`;}
 return {apply,update,snapshot:()=>({region:region.id,layers:{...flags},building_tier:'C',verified_heights:0,absolute_accuracy_m:null,center_utm_m:world.center_easting_northing_m})};
}

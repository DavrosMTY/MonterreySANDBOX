import test from 'node:test';
import assert from 'node:assert/strict';
import {sampleGrid,slopeGrid,utm14ToLonLat} from '../src/topography.js';

test('native source triangles retain a slope break and reject outside sampling',()=>{
 const g={n:2,heights_m:[500,510,520,540],interpolation:'native_triangles'};
 assert.equal(sampleGrid(g,0,0),515);assert.equal(sampleGrid(g,-500,-500),507.5);assert.equal(sampleGrid(g,500,500),527.5);
 assert.equal(sampleGrid(g,1001,0),null);assert.equal(sampleGrid(g,0,NaN),null);
});
test('reference raster remains bilinear while native triangulation stays explicit',()=>{
 assert.equal(sampleGrid({n:2,heights_m:[500,510,520,540]},0,0),517.5);
 const g={n:2,heights_m:[500,520,500,520]};assert(Math.abs(slopeGrid(g,0,0)-1)<1e-9);
});
test('inverse UTM 14N matches independent PROJ project-center control',()=>{
 const [lon,lat]=utm14ToLonLat(368523.6419988461,2839458.1365162465);
 assert(Math.abs(lon+100.310)<1e-7);assert(Math.abs(lat-25.667)<1e-7);
});

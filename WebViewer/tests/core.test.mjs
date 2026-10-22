import test from 'node:test';
import assert from 'node:assert/strict';
import {nearby, SectorStream} from '../src/core.js';
const sectors = [0, 1, 2].map(x => ({id: String(x), bytes: 10, bounds: [[x * 250, 0, 0], [x * 250 + 250, 20, 250]]}));
test('loads the nearest sectors by bounds, including crossed borders', () => {
  assert.deepEqual(nearby(sectors, {x: 249, z: 125}, 2).map(x => x.id), ['0', '1']);
  assert.deepEqual(nearby(sectors, {x: 900, z: 125}, 10), []);
});
test('evicts old scenes when travel changes the desired set', async () => {
  const released = [], attached = [];
  const s = new SectorStream({load: async x => x, attach: x => attached.push(x.id), release: x => released.push(x.id)});
  s.update(sectors); await s.idle(); s.update([sectors[2]]); await s.idle();
  assert.deepEqual([...s.resident.keys()], ['2']); assert.deepEqual(released.sort(), ['0', '1']);
  assert.equal(attached.length, 3);
});
test('a late response from an obsolete request is disposed instead of attached', async () => {
  let finish; const released = [], attached = [];
  const s = new SectorStream({concurrency: 1, load: x => new Promise(resolve => {finish = () => resolve(x);}),
    attach: x => attached.push(x.id), release: x => released.push(x.id)});
  s.update([sectors[0]]); await Promise.resolve(); s.update([]); finish(); await s.idle();
  assert.deepEqual(attached, []); assert.deepEqual(released, ['0']); assert.equal(s.resident.size, 0);
});
test('network failure stays visible and does not create a tight retry loop', async () => {
  let attempts = 0;
  const s = new SectorStream({load: async () => {attempts++; throw new Error('offline');}, attach: () => {}, release: () => {}});
  s.update([sectors[0]]); await s.idle(); s.update([sectors[0]]); await s.idle();
  assert.equal(attempts, 1); assert.equal(s.errors.get('0'), 'offline');
});

test('evicting an instanced sector releases its own GPU buffers but preserves shared art',async()=>{
  const {releaseScene,geometryBytes}=await import('../src/core.js');
  let instances=0,ownGeometry=0,ownMaterial=0;
  const shared={userData:{shared:true},dispose(){throw new Error('Shared resources must survive eviction');}};
  const own={userData:{},attributes:{position:{array:new Float32Array(9)}},dispose(){ownGeometry++;}};
  const material={userData:{},dispose(){ownMaterial++;}};
  const node={isInstancedMesh:true,dispose(){instances++;},geometry:shared,material:shared,instanceMatrix:{array:new Float32Array(16)}};
  const root={traverse(fn){fn(node);fn({geometry:own,material});fn({geometry:own,material});}};
  shared.attributes={};
  assert.equal(geometryBytes(root),100);
  releaseScene(root);assert.equal(instances,1);assert.equal(ownGeometry,1);assert.equal(ownMaterial,1);
});

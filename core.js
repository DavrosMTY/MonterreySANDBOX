// Pure scheduling/measurement helpers shared by the viewer and node tests.
export const PROFILES = Object.freeze({
  low: {radius: 310, dpr: .7, shadows: false},
  balanced: {radius: 620, dpr: 1, shadows: false},
  high: {radius: 1500, dpr: 1.5, shadows: true},
});
export function nearby(sectors, position, radius) {
  return sectors.map(sector => {
    const [lo, hi] = sector.bounds;
    const dx = Math.max(lo[0] - position.x, 0, position.x - hi[0]);
    const dz = Math.max(lo[2] - position.z, 0, position.z - hi[2]);
    return {sector, distance: Math.hypot(dx, dz)};
  }).filter(x => x.distance <= radius).sort((a, b) => a.distance - b.distance)
    .map(x => x.sector);
}
export function geometryBytes(scene) {
  const buffers = new Set();
  scene.traverse(node => {
    if (!node.geometry) return;
    for (const a of Object.values(node.geometry.attributes)) buffers.add(a.array.buffer);
    if (node.geometry.index) buffers.add(node.geometry.index.array.buffer);
  });
  return [...buffers].reduce((sum, b) => sum + b.byteLength, 0);
}
export function releaseScene(scene) {
  const geometries = new Set(), materials = new Set();
  scene.traverse(node => {
    if (node.geometry) geometries.add(node.geometry);
    for (const m of Array.isArray(node.material) ? node.material : [node.material]) if (m) materials.add(m);
  });
  for (const g of geometries) g.dispose();
  for (const m of materials) m.dispose();
}
export class SectorStream {
  constructor({load, attach, release, concurrency = 2}) {
    Object.assign(this, {load, attach, release, concurrency});
    this.resident = new Map(); this.pending = new Map(); this.wanted = new Map();
    this.errors = new Map(); this.retryAfter = new Map(); this.downloadedBytes = 0;
  }
  update(sectors) {
    this.wanted = new Map(sectors.map(x => [x.id, x]));
    for (const [id, value] of this.resident) if (!this.wanted.has(id)) {
      this.release(value); this.resident.delete(id);
    }
    // Abort fetches that no longer have a destination; stale parsed scenes are disposed too.
    for (const [id, record] of this.pending) if (!this.wanted.has(id)) record.controller.abort();
    this.pump();
  }
  pump() {
    for (const [id, sector] of this.wanted) {
      if (this.pending.size >= this.concurrency) break;
      if (this.resident.has(id) || this.pending.has(id) || (this.retryAfter.get(id) || 0) > Date.now()) continue;
      const controller = new AbortController();
      const task = Promise.resolve().then(() => this.load(sector, controller.signal)).then(value => {
        if (!this.wanted.has(id) || controller.signal.aborted) { this.release(value); return; }
        this.attach(value); this.resident.set(id, value); this.errors.delete(id);
        this.retryAfter.delete(id); this.downloadedBytes += sector.bytes;
      }).catch(error => {
        if (error.name !== 'AbortError') { this.errors.set(id, error.message); this.retryAfter.set(id, Date.now() + 15000); }
      }).finally(() => { this.pending.delete(id); this.pump(); });
      this.pending.set(id, {controller, task});
    }
  }
  async idle() {
    while (this.pending.size) await Promise.all([...this.pending.values()].map(x => x.task));
  }
}

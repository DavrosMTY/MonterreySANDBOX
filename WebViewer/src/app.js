import * as THREE from 'three';
import {VisualLayer} from './visual.js';
import {GLTFLoader} from './vendor/three/examples/jsm/loaders/GLTFLoader.js';
import {PROFILES, nearby, geometryBytes, releaseScene, SectorStream} from './core.js';

const $ = id => document.getElementById(id);
const fail = error => { $('error').hidden = false; $('error-text').textContent = error.message; };
let renderer;
try {
  renderer = new THREE.WebGLRenderer({antialias: true, powerPreference: 'high-performance'});
} catch {
  fail(new Error('Este navegador no pudo iniciar WebGL 2. Prueba una versión reciente de Chrome, Edge o Firefox con aceleración gráfica habilitada.'));
}
if (renderer) start().catch(fail);

async function start() {
  if (!('DecompressionStream' in window)) throw new Error('Este navegador necesita soporte de DecompressionStream para abrir los sectores comprimidos. Actualiza Chrome, Edge, Firefox o Safari.');
  renderer.setSize(innerWidth, innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = .95;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const canvas = renderer.domElement; canvas.tabIndex = 0;
  canvas.setAttribute('aria-label', 'Escenario Monterrey; WASD para moverte, arrastra para mirar');
  $('viewport').appendChild(canvas);
  canvas.addEventListener('webglcontextlost', e => { e.preventDefault(); fail(new Error('Se perdió el contexto gráfico. Recarga y selecciona calidad baja.')); });
  const world = await fetch('./world.json').then(r => { if (!r.ok) throw new Error('No se encontró el manifiesto del mundo.'); return r.json(); });
  if (world.synthetic || world.source_milestone !== 'GEO-003 / WORLD-001') throw new Error('El visor requiere los datos reales verificados de GEO-003.');
  const scene = new THREE.Scene();
  const sky = new THREE.Color('#cddbe2'); scene.background = sky;
  scene.fog = new THREE.Fog(sky, 650, 2400);
  const ambient=new THREE.HemisphereLight('#eff7ff', '#6d7254', 1.2);scene.add(ambient);
  const sun = new THREE.DirectionalLight('#fff1da', 2.0);
  sun.position.set(-650, 1600, 550); scene.add(sun); scene.add(sun.target);
  sun.target.position.set(0, 530, 0);
  sun.shadow.mapSize.set(1024, 1024);
  Object.assign(sun.shadow.camera, {left: -600, right: 600, top: 600, bottom: -600, near: 1, far: 2600});
  sun.shadow.normalBias = .12; sun.shadow.bias = -.00015;
  const camera = new THREE.PerspectiveCamera(55, innerWidth / innerHeight, .15, 6000);
  camera.rotation.order = 'YXZ';
  const loader = new GLTFLoader();
  const context = renderer.getContext();
  const debug = context.getExtension('WEBGL_debug_renderer_info');
  const device = debug ? context.getParameter(debug.UNMASKED_RENDERER_WEBGL) : context.getParameter(context.RENDERER);
  let profileName = matchMedia('(max-width: 700px)').matches || /swiftshader|llvmpipe|software/i.test(device) ? 'low' : 'balanced';
  let panoramaMode=false;
  let mode = 'aerial', focus = new THREE.Vector3(0, 535, 0), lastSectorUpdate = -1;
  let speed = 35, dragging = false, pointerX = 0, pointerY = 0;
  const keys = new Set(), ray = new THREE.Raycaster(), down = new THREE.Vector3(0, -1, 0);
  const forward = new THREE.Vector3(), right = new THREE.Vector3(), move = new THREE.Vector3();
  const frames = [], frameTimes = [];
  let frameStart = performance.now(), lastStats = frameStart, fps = 0, frameMs = 0, bytes = 0;
  function materialOptions(root) {
    root.traverse(node => {
      if (!node.isMesh) return;
      node.castShadow = node.userData.system === 'Buildings' || node.name === 'Buildings';
      node.receiveShadow = true;
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      for (const material of materials) {
        material.flatShading = true; material.wireframe = $('wireframe').checked; material.needsUpdate = true;
      }
    });
  }
  const visual=new VisualLayer({scene,renderer,sun,ambient,world});
  visual.setLight('day');
  await visual.load();
  camera.layers.enable(1);
  const stream = new SectorStream({
    load: async (sector, signal) => {
      const response = await fetch(new URL(sector.url, location.href), {signal});
      if (!response.ok) throw new Error(`Sector ${sector.id}: HTTP ${response.status}`);
      const compressed = await response.arrayBuffer();
      // Digest validates the exact published input before parsing external geometry.
      const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', compressed))].map(x => x.toString(16).padStart(2, '0')).join('');
      if (digest !== sector.sha256) throw new Error(`Integridad incorrecta en sector ${sector.id}`);
      const binary = await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();
      if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
      const gltf = await loader.parseAsync(binary, './');
      return {scene: gltf.scene, sector, bytes: geometryBytes(gltf.scene)};
    },
    attach: value => { materialOptions(value.scene); visual.prepare(value.scene,value.sector);materialOptions(value.scene);visual.update(camera); scene.add(value.scene); },
    release: value => { visual.release(value.scene);scene.remove(value.scene); releaseScene(value.scene); },
  });
  function updateSectors() {
    visual.update(camera);
    stream.update(nearby(world.sectors, mode === 'aerial' ? focus : camera.position, panoramaMode?1500:PROFILES[profileName].radius));
  }
  function setProfile(name) {
    profileName = name; const p = PROFILES[name];
    $('quality').value = name;
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, p.dpr));
    visual.setProfile(name);
    scene.traverse(node => { if (node.material) {
      for (const m of Array.isArray(node.material) ? node.material : [node.material]) m.needsUpdate = true;
    }});
    updateSectors();
  }
  function setView(next) {
    panoramaMode=false;mode = next;
    if (next === 'aerial') {
      focus.set(0, 535, 0); camera.position.set(410, 1050, 580); camera.lookAt(focus);
    } else {
      // Real GEO-003 centerline: Calle Ignacio Zaragoza, way/801774599/1687.
      camera.position.set(-76.36123249, 539.05541892, -48.25964916);
      camera.lookAt(-80.70601185, 540.01604524, -23.73362797); focus.copy(camera.position);
    }
    for (const id of ['aerial', 'street']) {
      $(id).classList.toggle('active', id === next); $(id).setAttribute('aria-pressed', String(id === next));
    }
    keys.clear(); updateSectors();
  }
  $('aerial').onclick = () => setView('aerial');
  $('street').onclick = () => setView('street');
  $('quality').onchange = e => setProfile(e.target.value);
  $('speed').onchange = e => { speed = Number(e.target.value); };
  $('fog').onchange = e => visual.setFog(e.target.checked);
  $('visual-mode').onchange=e=>{visual.setMode(e.target.value);visual.update(camera);};
  $('lighting').onchange=e=>visual.setLight(e.target.value);
  $('shadows').onchange=e=>visual.setShadows(e.target.value);
  $('visual-mode').value=visual.enabled?'city':'graybox';
  for(const key of ['vegetation','details','paint','background'])$(key).onchange=e=>{visual.setFlag(key,e.target.checked);visual.update(camera);};
  $('panorama').onchange=e=>{
    const preset=visual.background?.data.camera_presets[e.target.value];if(!preset)return;
    for(const id of ['aerial','street']){$(id).classList.toggle('active',id==='aerial');$(id).setAttribute('aria-pressed',String(id==='aerial'));}
    panoramaMode=true;mode='aerial';focus.set(0,535,0);camera.position.set(e.target.value==='sierra'?-600:500,660,650);camera.lookAt(...preset.target);keys.clear();updateSectors();
  };
  $('wireframe').onchange = () => { for (const value of stream.resident.values()) materialOptions(value.scene); };
  $('explore').onclick = async () => {
    canvas.focus();
    try { await canvas.requestPointerLock(); } catch { /* Drag-look remains available. */ }
  };
  canvas.oncontextmenu = e => e.preventDefault();
  canvas.addEventListener('pointerdown', e => {
    if (e.button === 2 || e.pointerType === 'touch') {
      dragging = true; pointerX = e.clientX; pointerY = e.clientY;
      canvas.setPointerCapture(e.pointerId); canvas.focus();
    }
  });
  canvas.addEventListener('pointerup', () => { dragging = false; });
  canvas.addEventListener('pointercancel', () => { dragging = false; });
  document.addEventListener('mousemove', e => {
    if (document.pointerLockElement === canvas) rotate(e.movementX, e.movementY);
  });
  canvas.addEventListener('pointermove', e => {
    if (dragging && document.pointerLockElement !== canvas) {
      rotate(e.clientX - pointerX, e.clientY - pointerY); pointerX = e.clientX; pointerY = e.clientY;
    }
  });
  function rotate(x, y) {
    camera.rotation.y -= x * .0025;
    camera.rotation.x = THREE.MathUtils.clamp(camera.rotation.x - y * .0025, -1.45, 1.45);
  }
  document.addEventListener('keydown', e => {
    if (e.target.matches('input,select,button,summary') || e.ctrlKey || e.metaKey || e.altKey) return;
    if (['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE', 'ShiftLeft', 'ShiftRight'].includes(e.code)) { keys.add(e.code); e.preventDefault(); }
  });
  document.addEventListener('keyup', e => keys.delete(e.code));
  window.addEventListener('blur', () => { keys.clear(); dragging = false; });
  document.addEventListener('visibilitychange', () => { if (document.hidden) keys.clear(); });
  for (const button of document.querySelectorAll('[data-key]')) {
    button.addEventListener('pointerdown', e => { e.preventDefault(); keys.add(button.dataset.key); button.setPointerCapture(e.pointerId); });
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) button.addEventListener(event, () => keys.delete(button.dataset.key));
  }
  addEventListener('resize', () => {
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight);
  });
  function snapshot() {
    return {ready: stream.resident.size > 0, quality: profileName, mode, camera: camera.position.toArray(),
      rotation: camera.rotation.toArray().slice(0, 3), resident: [...stream.resident.keys()], wanted: [...stream.wanted.keys()],
      pending: stream.pending.size, errors: [...stream.errors.entries()], fps, frame_ms: frameMs,
      geometry_bytes: bytes, heap_bytes: performance.memory?.usedJSHeapSize ?? null,
      triangles: renderer.info.render.triangles, draw_calls: renderer.info.render.calls,
      geometries: renderer.info.memory.geometries, downloaded_bytes: stream.downloadedBytes,
      drawing_buffer: [canvas.width, canvas.height], renderer: device,
      source_glb_sha256: world.source_glb_sha256,visual:visual.snapshot()};
  }
  // Read-only diagnostics, used by the browser tests and downloadable evidence.
  window.__MOW__ = Object.freeze({snapshot, idle: () => stream.idle()});
  setView('aerial'); setProfile(profileName);
  function animate(now) {
    const elapsed = now - frameStart, dt = Math.min(elapsed / 1000, .05); frameStart = now;
    if (!document.hidden) {
      camera.getWorldDirection(forward); forward.y = 0; forward.normalize(); right.crossVectors(forward, camera.up).normalize();
      move.set(0, 0, 0);
      if (keys.has('KeyW')) move.add(forward); if (keys.has('KeyS')) move.sub(forward);
      if (keys.has('KeyD')) move.add(right); if (keys.has('KeyA')) move.sub(right);
      if (keys.has('KeyE')) move.y += 1; if (keys.has('KeyQ')) move.y -= 1;
      if (move.lengthSq()) {
        move.normalize().multiplyScalar(speed * dt * (keys.has('ShiftLeft') || keys.has('ShiftRight') ? 4 : 1));
        camera.position.add(move); if (mode === 'aerial') focus.add(move);
        camera.position.x = THREE.MathUtils.clamp(camera.position.x, -1120, 1120);
        camera.position.z = THREE.MathUtils.clamp(camera.position.z, -1120, 1120);
        focus.x = THREE.MathUtils.clamp(focus.x, -1000, 1000); focus.z = THREE.MathUtils.clamp(focus.z, -1000, 1000);
        camera.position.y = THREE.MathUtils.clamp(camera.position.y, 505, 2300);
      }
      // Prevent diving through an already-loaded ground surface. This is a free
      // camera aid, not swept player collision or proof of walkable roads/tunnels.
      if (mode === 'street' && now - lastStats > 200) {
        ray.set(new THREE.Vector3(camera.position.x, camera.position.y + 2, camera.position.z), down);
        const hits = ray.intersectObjects([...stream.resident.values()].flatMap(v => v.scene.children), true);
        if (hits.length && hits[0].distance < 3.7) camera.position.y = hits[0].point.y + 1.7;
      }
      if (now - lastSectorUpdate > 300) { updateSectors(); lastSectorUpdate = now; }
      visual.render(renderer,camera);
      frames.push(now); frameTimes.push(elapsed);
      while (frames.length>2 && frames[0] < now - 2000) { frames.shift(); frameTimes.shift(); }
    }
    if (now - lastStats > 500) {
      const span = frames.length > 1 ? (frames.at(-1) - frames[0]) / 1000 : 0;
      fps = span > 0 ? (frames.length - 1) / span : 0;
      frameMs = frameTimes.length ? frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length : 0;
      bytes = geometryBytes(scene)+(visual.background?.bytes()||0);
      $('fps').textContent = fps.toFixed(0); $('sectors').textContent = `${stream.resident.size}/${world.sectors.length}`;
      $('triangles').textContent = renderer.info.render.triangles.toLocaleString('es-MX');
      $('memory').textContent = (bytes / 1048576).toFixed(1);
      $('heap').textContent = performance.memory ? (performance.memory.usedJSHeapSize / 1048576).toFixed(0) : 'N/D';
      $('notice').textContent = stream.errors.size ? `Carga parcial: ${stream.errors.size} sector(es) fallaron; reintentando.` :
        stream.pending.size ? `Cargando sectores cercanos · ${stream.resident.size}/${stream.wanted.size}` :
        `${stream.resident.size} sectores listos · cámara libre, sin colisión física`;
      $('progress').style.width = `${100 * stream.resident.size / Math.max(stream.wanted.size, 1)}%`;
      $('needle').style.transform = `rotate(${camera.rotation.y}rad)`;
      lastStats = now;
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
}

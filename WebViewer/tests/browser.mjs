// Real WebGL integration, keyboard/mouse, loading/eviction, and explicitly software-rendered timing.
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {chromium} from 'playwright-core';
import {existsSync, readFileSync, writeFileSync, mkdirSync, statSync} from 'node:fs';
import http from 'node:http';
import {resolve, extname} from 'node:path';
const site = resolve(process.env.MOW_SITE || '../artifacts/free001-site');
const output = resolve(process.env.MOW_EVIDENCE || '../artifacts/free001-browser'); mkdirSync(output, {recursive:true});
const mime = {'.html':'text/html', '.js':'text/javascript', '.css':'text/css', '.json':'application/json', '.svg':'image/svg+xml'};
let server;
const external = process.env.MOW_URL;
if (!external) {
  server = http.createServer((req,res) => {
    const path = resolve(site, '.' + decodeURIComponent(new URL(req.url, 'http://localhost').pathname) + (req.url.endsWith('/') ? 'index.html' : ''));
    if (!path.startsWith(site + '/') || !existsSync(path) || !statSync(path).isFile()) {res.writeHead(404); res.end();return;}
    res.setHeader('Content-Type', mime[extname(path)] || 'application/octet-stream'); res.end(readFileSync(path));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
}
const url = external || `http://127.0.0.1:${server.address().port}/`;
const executablePath = process.env.CHROMIUM_PATH || ['/usr/bin/chromium','/usr/bin/google-chrome'].find(existsSync);
const browser = await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-dev-shm-usage']});
const errors = [], requests = [];
let activePage;
try {
  const browserContext = await browser.newContext({viewport:{width:1280,height:800}});
  let page = await browserContext.newPage(); activePage=page;
  let hostingInterstitial = false;
  function observe(page) {
  page.on('console',msg=>{if(msg.type()==='error')errors.push(msg.text());});
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {if (response.status()>=400)errors.push(`${response.status()} ${response.url()}`);});
  page.on('request', request => requests.push(request.url()));
  }
  observe(page);
  const main = await page.goto(url);
  assert(main.ok(), `Public entry HTTP ${main.status()}`);
  if ((await page.title()).startsWith('External Content Notice')) {
    hostingInterstitial = true;
    assert.equal(new URL(await page.locator('#phish-dest').inputValue()).href, new URL(url).href, 'The notice must lead to our exact immutable URL');
    await Promise.all([page.waitForNavigation(), page.getByRole('button',{name:'Open the page',exact:true}).click()]);
    // The free service's notice has advertising. Test the actual application in
    // a fresh page with the normal consent cookie, separately from that notice.
    const context = page.context();
    for (const event of ['pageerror','response','request','console']) page.removeAllListeners(event);
    await page.goto('about:blank');
    page = await context.newPage(); activePage = page; errors.length=0; requests.length=0;
    observe(page);
    const entry = await page.goto(url); assert(entry.ok(),`Application entry HTTP ${entry.status()}`);
  }
  await page.waitForFunction(() => window.__MOW__?.snapshot().ready, null, {timeout:60000});
  const samples = [];
  for (const quality of ['balanced','low']) {
    await page.locator('details').evaluate(el=>{el.open=true;});
    await page.selectOption('#quality', quality);
    await page.evaluate(()=>window.__MOW__.idle());
    await page.waitForTimeout(3500);
    const value = await page.evaluate(()=>window.__MOW__.snapshot());
    assert.equal(value.errors.length, 0); assert(value.triangles>1000); assert.equal(value.pending,0);
    samples.push(value);
    await page.screenshot({path:`${output}/aerial-${quality}.png`});
  }
  assert(samples[1].resident.length < samples[0].resident.length, 'Low quality evicts distant sectors');
  assert(samples[1].geometry_bytes < samples[0].geometry_bytes, 'Low quality reduces resident geometry');
  assert(samples[1].drawing_buffer[0] < samples[0].drawing_buffer[0], 'Low quality reduces resolution');
  await page.click('#street'); await page.evaluate(()=>window.__MOW__.idle());
  await page.waitForTimeout(1500);
  const street = await page.evaluate(()=>window.__MOW__.snapshot());
  assert.equal(street.mode,'street'); assert(street.camera[1]<600);
  await page.locator('canvas').focus(); await page.keyboard.down('KeyW'); await page.waitForTimeout(1200); await page.keyboard.up('KeyW');
  const moved = await page.evaluate(()=>window.__MOW__.snapshot());
  assert(Math.hypot(moved.camera[0]-street.camera[0],moved.camera[2]-street.camera[2])>.5,'W moves the camera');
  await page.mouse.move(920,350); await page.mouse.down({button:'right'}); await page.mouse.move(1010,370,{steps:5}); await page.mouse.up({button:'right'});
  const rotated = await page.evaluate(()=>window.__MOW__.snapshot());
  assert(Math.abs(rotated.rotation[1]-moved.rotation[1])>.01,'Mouse changes view');
  await page.screenshot({path:`${output}/street.png`});
  let world002=null;
  if(process.env.MOW_WORLD002==='1'){
    const shots={},regions={};const timings=[];
    async function sample(name){
      await page.evaluate(()=>window.__MOW__.idle());await page.waitForTimeout(3500);
      const state=await page.evaluate(()=>window.__MOW__.snapshot());
      assert.equal(state.errors.length,0);assert.equal(state.pending,0);
      assert.equal(state.visual.resident_visual_sectors,state.resident.length);
      assert.equal(state.visual.props.overlay_sectors,state.resident.length);
      timings.push({name,...state});
      const png=await page.screenshot({path:`${output}/${name}.png`});shots[name]=createHash('sha256').update(png).digest('hex');
      regions[name]=createHash('sha256').update(await page.screenshot({clip:{x:380,y:120,width:900,height:610}})).digest('hex');
      return state;
    }
    await page.click('#street');
    await page.selectOption('#visual-mode','graybox');
    const gray=await sample('street-graybox');assert.equal(gray.visual.props.visible_instances,0);assert.equal(gray.visual.background.visible,false);
    await page.selectOption('#visual-mode','city');
    const city=await sample('street-city-day');assert(city.visual.props.visible_instances>0);assert.equal(city.visual.background.visible,true);
    assert.deepEqual(city.camera,gray.camera,'Material comparison preserves the camera');assert.deepEqual(city.resident,gray.resident);
    assert.notEqual(regions['street-graybox'],regions['street-city-day'],'The rendered city region changes, excluding the control panel and FPS HUD');
    for(const period of ['sunset','night']){await page.selectOption('#lighting',period);const s=await sample(`street-city-${period}`);assert.equal(s.visual.period,period);assert.notEqual(regions[`street-city-${period}`],regions['street-city-day']);}
    await page.selectOption('#lighting','day');
    for(const id of ['vegetation','details','paint'])await page.uncheck('#'+id);
    const bare=await sample('details-disabled');assert.equal(bare.visual.props.visible_instances,0);
    for(const id of ['vegetation','details','paint'])await page.check('#'+id);
    await page.selectOption('#shadows','on');await sample('street-shadows');await page.selectOption('#shadows','off');
    await page.click('#aerial');
    const residentCounts=[];
    for(const [profile,spacing] of [['high',90],['balanced',180],['low',360],['balanced',180],['low',360]]){
      await page.selectOption('#quality',profile);const s=await sample(`aerial-${profile}-${residentCounts.length}`);
      assert.equal(s.visual.background.lod_spacing_m,spacing);residentCounts.push(s);
    }
    assert.equal(residentCounts[0].resident.length,64);
    assert.equal(residentCounts[2].geometries,residentCounts[4].geometries,'Repeated streaming cycle releases per-sector and instance buffers');
    assert.equal(residentCounts[2].geometry_bytes,residentCounts[4].geometry_bytes);
    for(const preset of ['silla','sierra','larga']){await page.selectOption('#panorama',preset);await sample(`landscape-${preset}`);}
    world002={status:'passed',timings,screenshot_sha256:shots,comparison_region_sha256:regions,checks:['Graybox/city at identical street camera and sectors','Day/sunset/night rendering','Decorations toggled off','Real shadow shader compilation','64 sectors at high quality without simplifying the pilot','Three DEM LODs','Repeated load/eviction preserves buffer counts','Three georeferenced landscape directions','No console, shader, HTTP or page errors']};
  }
  await page.setViewportSize({width:390,height:844}); await page.click('#aerial'); await page.evaluate(()=>window.__MOW__.idle());
  await page.screenshot({path:`${output}/mobile.png`});
  assert(await page.locator('.touch-controls').isVisible());
  assert.equal(errors.length,0,errors.join('\n'));
  const origin=new URL(url).origin;
  const immutablePrefix = external && /^https:\/\/rawcdn\.githack\.com\/DavrosMTY\/MonterreySANDBOX\/[a-f0-9]{40}\//.test(url)
    ? new URL(url).pathname.replace(/index\.html$/, '') : null;
  const staticRedirects = requests.filter(x=>new URL(x).origin!==origin);
  assert(staticRedirects.every(x=> {
    const target=new URL(x);
    return immutablePrefix && target.origin==='https://raw.githubusercontent.com' &&
      target.pathname.startsWith(immutablePrefix+'assets/') && /\/(?:cell_[0-7]_[0-7]\.glb|visual-overlay\.json|background\.json)\.gz$/.test(target.pathname);
  }),'Only static GLB redirects to the identical immutable GitHub source are allowed');
  const report={status:'passed',tested_url:url,renderer:'Chromium / ANGLE SwiftShader SOFTWARE; not user GPU or Unreal performance',
    world002,viewport:[1280,800],hosting_interstitial:hostingInterstitial,service_notice_can_include_advertising:hostingInterstitial,samples,street_initial:street,street_after_controls:rotated,
    browser_errors:errors,external_runtime_requests:staticRedirects.length,unapproved_runtime_requests:0,runtime_origins:[...new Set(requests.map(x=>new URL(x).origin))],checks:['Real GEO-003 GLB loaded and rendered','Two quality profiles rendered','Sector eviction and memory reduction','Keyboard translation','Mouse rotation','Street and aerial presets','Mobile controls','Only project static assets; preview GLB redirects to the identical pinned GitHub source allowed']};
  writeFileSync(`${output}/browser-report.json`,JSON.stringify(report,null,2)+'\n'); console.log(JSON.stringify(report,null,2));
} catch (error) {
  writeFileSync(`${output}/browser-failure.json`,JSON.stringify({status:'failed',tested_url:url,error:String(error),stack:error.stack,entry_title:activePage?await activePage.title().catch(()=>null):null,entry_text:activePage?(await activePage.locator('body').innerText({timeout:2000}).catch(()=>'' )).slice(0,400):null,browser_errors:errors,requests},null,2)+'\n');
  throw error;
} finally {await browser.close(); if(server)await new Promise(resolve=>server.close(resolve));}

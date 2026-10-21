// Real WebGL integration, keyboard/mouse, loading/eviction, and explicitly software-rendered timing.
import assert from 'node:assert/strict';
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
  const page = await browser.newPage({viewport:{width:1280,height:800}}); activePage=page;
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {if (response.status()>=400)errors.push(`${response.status()} ${response.url()}`);});
  page.on('request', request => requests.push(request.url()));
  const main = await page.goto(url);
  assert(main.ok(), `Public entry HTTP ${main.status()}`);
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
  await page.setViewportSize({width:390,height:844}); await page.click('#aerial'); await page.evaluate(()=>window.__MOW__.idle());
  await page.screenshot({path:`${output}/mobile.png`});
  assert(await page.locator('.touch-controls').isVisible());
  assert.equal(errors.length,0,errors.join('\n'));
  const origin=new URL(url).origin; assert(requests.every(x=>new URL(x).origin===origin),'No external runtime services');
  const report={status:'passed',tested_url:url,renderer:'Chromium / ANGLE SwiftShader SOFTWARE; not user GPU or Unreal performance',
    viewport:[1280,800],samples,street_initial:street,street_after_controls:rotated,
    browser_errors:errors,external_runtime_requests:0,checks:['Real GEO-003 GLB loaded and rendered','Two quality profiles rendered','Sector eviction and memory reduction','Keyboard translation','Mouse rotation','Street and aerial presets','Mobile controls','No external runtime dependencies']};
  writeFileSync(`${output}/browser-report.json`,JSON.stringify(report,null,2)+'\n'); console.log(JSON.stringify(report,null,2));
} catch (error) {
  writeFileSync(`${output}/browser-failure.json`,JSON.stringify({status:'failed',tested_url:url,error:String(error),stack:error.stack,entry_title:activePage?await activePage.title().catch(()=>null):null,entry_text:activePage?(await activePage.locator('body').innerText({timeout:2000}).catch(()=>'' )).slice(0,400):null,browser_errors:errors,requests},null,2)+'\n');
  throw error;
} finally {await browser.close(); if(server)await new Promise(resolve=>server.close(resolve));}

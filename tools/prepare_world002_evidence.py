"""Package authentic browser captures and receipts inside the capped static site."""
import argparse
import html
import json
from pathlib import Path
import shutil


def prepare(site,browser,geometry,visual):
    site,browser=Path(site),Path(browser)
    report=json.loads((browser/'browser-report.json').read_text())
    if report['status']!='passed' or report.get('world002',{}).get('status')!='passed':
        raise ValueError('Publish only successful actual WORLD-002 browser evidence')
    out=site/'evidence';out.mkdir(exist_ok=True)
    for p in browser.glob('*.png'):shutil.copy2(p,out/p.name)
    for source,name in [(browser/'browser-report.json','browser-report.json'),(Path(geometry),'geometry.json'),(Path(visual),'visual.json')]:shutil.copy2(source,out/name)
    cards=[]
    for name,title in [('street-graybox','Original Graybox'),('street-city-day','Ciudad · día'),('street-city-sunset','Atardecer'),('street-city-night','Noche'),('street-shadows','Sombras'),('aerial-balanced','Vista aérea'),('landscape-silla','Área Cerro de la Silla'),('landscape-sierra','Sierra Madre'),('landscape-larga','Loma Larga'),('mobile','Chromium responsive')]:
        cards.append(f'<figure><a href="{name}.png"><img loading="lazy" src="{name}.png" alt="{html.escape(title)}"></a><figcaption>{html.escape(title)}</figcaption></figure>')
    body='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Capturas reales · WORLD-002</title><style>body{font:16px/1.7 system-ui;background:#14201d;color:#d9e5d8;margin:24px}a{color:#b9f17b}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:18px}figure{margin:0}img{width:100%;height:auto;border-radius:10px}small{color:#abc0ad}</style><a href="../">← Explorar el visor</a><h1>WORLD-002 · capturas auténticas</h1><p>Chromium / ANGLE SwiftShader por software, 1280 × 800. Son capturas del navegador, sin imágenes generadas por IA. No son Unreal ni mediciones de una GPU de consumo. Fachadas, pintura y plantación adicional son propuestas visuales.</p><p><a href="browser-report.json">Pruebas y FPS</a> · <a href="geometry.json">Conservación geométrica</a> · <a href="visual.json">Validación de fuentes</a></p><div class="grid">'''+''.join(cards)+'</div></html>'
    (out/'index.html').write_text(body)
    total=sum(p.stat().st_size for p in site.rglob('*')if p.is_file())
    if total>50*1024**2:raise ValueError('Evidence exceeds total 50 MiB deployment cap')
    print(json.dumps({'site_including_real_evidence_bytes':total,'screenshots':len(cards)}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('site','browser','geometry','visual'):p.add_argument('--'+name,required=True)
    a=p.parse_args();prepare(a.site,a.browser,a.geometry,a.visual)

"""Publish selected untouched Chromium captures and full numerical QA under 50 MiB."""
import argparse
import html
import json
from pathlib import Path
import shutil


def prepare(site,browser):
    site,browser=Path(site),Path(browser)
    report=json.loads((browser/'browser-report.json').read_text())
    if report['status']!='passed'or report.get('geo004',{}).get('status')!='passed':raise ValueError('Require actual successful GEO-004 browser run')
    out=site/'evidence';out.mkdir(exist_ok=False)
    names=[f'{model}-case{i}'for i in range(3)for model in ('geo003','geo004')]+['geo003-heatmap','geo004-heatmap','geographic-query','geo004-street-night']
    cards=[]
    for name in names:
        source=browser/(name+'.png');shutil.copy2(source,out/source.name)
        cards.append(f'<figure><a href="{name}.png"><img loading="lazy" src="{name}.png" alt="{html.escape(name)}"></a><figcaption>{html.escape(name)}</figcaption></figure>')
    shutil.copy2(browser/'browser-report.json',out/'browser-report.json')
    (out/'index.html').write_text('''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>GEO-004 · evidencia real</title><style>body{font:16px/1.6 system-ui;background:#14201d;color:#e1eadb;margin:24px}a{color:#c8f78b}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:20px}figure{margin:0}img{width:100%}</style><a href="../">← Abrir visor</a><h1>GEO-003 / GEO-004 · capturas auténticas</h1><p>Capturas sin retoque de Chromium, WebGL mediante ANGLE SwiftShader por software, 1280 × 800. Cada pareja usa exactamente la misma cámara y mallas distintas verificadas por SHA256. No son imágenes generadas por IA ni capturas de Unreal.</p><p>Fuente nueva: INEGI MDT LiDAR 5 m, datos 2007, EPV no publicada. Puentes, túneles y cimentaciones aún requieren controles independientes. El mapa de calor incluye pendientes, superficies ausentes y estructuras pendientes: no significa que todas las zonas restantes sean correctas.</p><p><a href="browser-report.json">Pruebas y rendimiento observado</a> · <a href="../reports/validation.json">QA completo</a> · <a href="../reports/review-issues.geojson">Incidencias geográficas</a> · <a href="../reports/longitudinal-comparison.png">Perfiles científicos</a></p><div class="grid">'''+''.join(cards)+'</div></html>')
    total=sum(p.stat().st_size for p in site.rglob('*')if p.is_file())
    if total>50*1024**2:raise ValueError('Free deployment cap exceeded')
    print(json.dumps({'site_bytes':total,'authentic_captures':len(names),'status':'passed'}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',required=True);p.add_argument('--browser',required=True);a=p.parse_args();prepare(a.site,a.browser)

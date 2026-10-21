"""Render a geographic review map from exported data, without Unreal or basemaps."""
import argparse
import json
import os
from pathlib import Path
import textwrap

os.environ.setdefault('MPLCONFIGDIR', '/tmp/monterrey-matplotlib')
os.environ.setdefault('XDG_CACHE_HOME', '/tmp/monterrey-cache')
Path(os.environ['XDG_CACHE_HOME']).mkdir(parents=True, exist_ok=True)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from GeoPipeline.sources import COPERNICUS_DERIVED_NOTICE, COPERNICUS_LIABILITY, OSM_NOTICE


def render(terrain, urban, output):
    terrain, urban = Path(terrain), Path(urban)
    manifest = json.loads((terrain/'manifest.json').read_text())
    roads = json.loads((urban/'urban.json').read_text())
    buildings = json.loads((urban/'buildings.geojson').read_text())
    if manifest['center_easting_northing_m'] != roads['center_easting_northing_m'] or manifest['extent_m'] != roads['extent_m']:
        raise ValueError('Terrain and urban origins/extents must match')
    with rasterio.open(terrain/manifest['reference_geotiff']) as src:
        heights = src.read(1)
    fig, ax = plt.subplots(figsize=(11, 11))
    half = manifest['extent_m']/2
    edge = half + manifest['sample_spacing_m']/2
    im = ax.imshow(heights, origin='upper', extent=(-edge, edge, -edge, edge), cmap='terrain', interpolation='nearest')
    lines = [[(p[0]/100, -p[1]/100) for p in r['xy_cm']] for r in roads['roads']]
    ax.add_collection(LineCollection(lines, colors='#c83232', linewidths=.55, alpha=.85))
    for feature in buildings['features']:
        for polygon in feature['properties']['world_polygons_cm']:
            vertices, codes = [], []
            for ring in polygon:
                vertices += [(p[0]/100, -p[1]/100) for p in ring]
                codes += [MplPath.MOVETO]+[MplPath.LINETO]*(len(ring)-2)+[MplPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MplPath(vertices, codes), facecolor='#f4edd6', edgecolor='#302c24', linewidth=.25, alpha=.8))
    ax.scatter([0], [0], c='black', marker='+', s=50)
    ax.set_xlim(-half, half); ax.set_ylim(-half, half); ax.set_aspect('equal')
    synthetic = manifest['synthetic_demo_not_geographic_truth'] or roads['synthetic_fixture']
    label = 'DATOS SINTÉTICOS' if synthetic else 'Copernicus DSM real + OpenStreetMap'
    ax.set_title(f'Monterrey Open World | sector piloto {manifest["extent_m"]/1000:g} × {manifest["extent_m"]/1000:g} km\n{label} — mapa técnico; sin render Unreal', fontsize=12)
    ax.set_xlabel('Este de cuadrícula desde el centro (m)')
    ax.set_ylabel('Norte de cuadrícula desde el centro (m)')
    ax.grid(alpha=.15)
    ax.text(.97, .96, 'N de\ncuadrícula ↑', transform=ax.transAxes, ha='right', va='top', fontsize=8,
            bbox={'facecolor': 'white', 'alpha': .8, 'edgecolor': 'none'})
    fig.colorbar(im, ax=ax, shrink=.7, label='Elevación de superficie (m; datum de origen)')
    fig.subplots_adjust(bottom=.16, top=.92, left=.09, right=.97)
    footer = 'Fixture sintético de pruebas.' if synthetic else '\n'.join(textwrap.wrap(COPERNICUS_DERIVED_NOTICE+' '+COPERNICUS_LIABILITY, 150))+'\n'+OSM_NOTICE
    fig.text(.06, .025, footer, fontsize=6, va='bottom')
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180); plt.close(fig)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--terrain', required=True); p.add_argument('--urban', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); render(a.terrain, a.urban, a.output)

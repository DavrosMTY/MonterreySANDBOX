"""Run the local acceptance workflow and preserve evidence in a fresh directory."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fetch-real', action='store_true', help='Also attempt the two selected public sources, once')
    p.add_argument('--dem', help='Reuse a local licensed DEM rather than downloading it again')
    p.add_argument('--dem-record', help='Provenance JSON for the cached DEM, including vertical_datum')
    p.add_argument('--osm', help='Reuse a local Overpass JSON extract')
    a = p.parse_args()
    if a.fetch_real and (a.dem or a.osm):
        p.error('Choose fresh acquisitions or cached sources, not both')
    if a.dem and not a.dem_record:
        p.error('--dem requires --dem-record')
    artifacts = ROOT/'artifacts'; artifacts.mkdir(exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix='geo001_1-', dir=artifacts))
    results = []

    def execute(name, arguments, required=True):
        proc = subprocess.run([sys.executable, *arguments], cwd=ROOT, text=True, capture_output=True)
        (run_dir/f'{name}.log').write_text(proc.stdout+proc.stderr, encoding='utf-8')
        results.append({'name': name, 'exit_code': proc.returncode, 'required': required})
        return proc.returncode

    junit = run_dir/'tests.xml'
    execute('pytest', ['-m', 'pytest', '-q', f'--junitxml={junit}'])
    for label, tiles, extent in [('single', 1, 2000), ('tiles', 2, 4000)]:
        output = run_dir/label
        if execute(f'export-{label}', ['-m', 'GeoPipeline.geo001', '--demo', '--tiles', str(tiles), '--extent-m', str(extent), '--output', str(output)]) == 0:
            execute(f'validate-{label}', ['-m', 'GeoPipeline.validate', str(output)])
    execute('urban', ['-m', 'GeoPipeline.urban', '--osm', 'tests/fixtures/synthetic_urban.json', '--output', str(run_dir/'urban')])
    execute('unreal', ['tools/check_unreal.py', '--output', str(run_dir/'unreal.json')], required=False)
    dem = Path(a.dem).resolve() if a.dem else None
    dem_record = Path(a.dem_record).resolve() if a.dem_record else None
    osm = Path(a.osm).resolve() if a.osm else None
    if a.fetch_real:
        dem = run_dir/'real/copernicus.tif'
        osm = run_dir/'real/osm.json'
        if execute('acquire-dem', ['-m', 'GeoPipeline.acquire', 'dem', '--output', str(dem)], required=False) != 0:
            dem = None
        else:
            dem_record = Path(str(dem)+'.source.json')
        if execute('acquire-osm', ['-m', 'GeoPipeline.acquire', 'osm', '--output', str(osm)], required=False) != 0:
            osm = None
    if dem:
        datum = json.loads(dem_record.read_text(encoding='utf-8'))['vertical_datum']
        if execute('export-real', ['-m', 'GeoPipeline.geo001', '--dem', str(dem), '--source-record', str(dem_record), '--vertical-datum', datum, '--output', str(run_dir/'real/terrain')]) == 0:
            execute('validate-real', ['-m', 'GeoPipeline.validate', str(run_dir/'real/terrain')])
    if osm:
        execute('urban-real', ['-m', 'GeoPipeline.urban', '--osm', str(osm), '--output', str(run_dir/'real/urban')])
    suites = ET.parse(junit).getroot() if junit.exists() else None
    counts = {k: sum(int(s.get(k, '0')) for s in suites.iter('testsuite')) if suites is not None else 0
              for k in ('tests', 'failures', 'errors', 'skipped')}
    ok = counts['tests'] > 0 and not any(counts[k] for k in ('failures', 'errors')) and all(r['exit_code'] == 0 for r in results if r['required'])
    report = {'generated_at_utc': datetime.now(timezone.utc).isoformat(), 'run_directory': str(run_dir.relative_to(ROOT)),
              'local_pipeline_status': 'passed' if ok else 'failed', 'test_counts': counts, 'commands': results,
              'real_terrain_produced': (run_dir/'real/terrain/manifest.json').exists(),
              'real_osm_processed': (run_dir/'real/urban/urban.json').exists(),
              'unreal': json.loads((run_dir/'unreal.json').read_text()) if (run_dir/'unreal.json').exists() else {'status': 'probe_failed'},
              'ci_windows_executed': False, 'published_or_pushed': False}
    (run_dir/'acceptance.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())

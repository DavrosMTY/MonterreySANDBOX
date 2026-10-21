"""WORLD-001 Windows UE5.6 build/import/WP runner; exit 2 = unavailable engine.

Uses excavated static terrain, category-separated cell assets and native collision
configuration. Original Landscape import is intentionally rejected for WORLD-001.
"""
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    raise SystemExit(subprocess.call([sys.executable,str(ROOT/'tools/run_unreal_geo002.py'),
        '--city','Data/city/geo003_world001','--terrain-mode','static_mesh',
        '--map','/Game/Maps/WORLD001','--asset-root','/Game/WORLD001',
        '--receipt','artifacts/geo003_unreal_status.json',*sys.argv[1:]],cwd=ROOT))

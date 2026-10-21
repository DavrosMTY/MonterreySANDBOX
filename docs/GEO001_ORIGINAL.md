# Monterrey Open World — GEO-001 alpha

First reproducible deliverable: a **single 505 x 505, 16-bit Landscape heightmap** for Unreal Engine 5. Demo data is **synthetic, not real Monterrey elevations**. A licensed real GeoTIFF is needed for geographic terrain.

## Windows setup

1. Install Unreal Engine 5 through Epic Games Launcher and create a **Games > Blank** project named `MonterreyOpenWorld` (Blueprint initially; add C++ later). Enable World Partition/Open World when creating the level.
2. Install Python 3.12 x64 and Git. Optional for inspection: QGIS and Visual Studio 2022 with Game development with C++.
3. In PowerShell at this repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m pytest -q
python -m GeoPipeline.geo001 --demo --output Data/unreal/demo
```

4. Outputs: `Data/unreal/demo/terrain_505.png`, `terrain_505.r16`, `manifest.json`.

## Using a real DEM

Download a **local, properly licensed GeoTIFF elevation model** covering the requested 2-km square around the project center. Document its vertical datum explicitly (e.g. source metadata designation). Do **not** infer or convert between vertical datums automatically.

```powershell
python -m GeoPipeline.geo001 --dem Data/raw/monterrey_dem.tif --vertical-datum SOURCE_DATUM_NAME --lat 25.667 --lon -100.310 --extent-m 2000 --output Data/unreal/real
```

If the DEM does not cover every target sample, the command errors rather than hiding holes. Output projection is EPSG:32614 and center/scale information is in `manifest.json`. Data is interpolated at the output spacing; this does not introduce genuine additional ground detail. For larger areas, tiled export, shared border sampling, and metadata per tile remain future work.

## Unreal Editor manual validation

1. Create an Open World/World Partition level, save it.
2. Open Landscape mode (Shift+2), Manage > Import from File. Select `terrain_505.png` and choose a topology compatible with 505 x 505 vertices (e.g. 4x4 components, 2x2 sections/component, 63 quads/section).
3. Read `manifest.json`: use `unreal_x_scale_cm`, `unreal_y_scale_cm`, `unreal_z_scale_cm` for Landscape X, Y, Z scales. Use `unreal_landscape_actor_z_cm` as the elevation offset only in a world coordinate scheme consistent with the chosen origin. In a local zero-centered scene this is optional, but must be treated consistently with building/road coordinates.
4. Check landscape footprint (2 km each axis); test critical point elevations and orientation. GeoRaster rows are north-to-south; compare multiple known corner control points against Unreal axes. Invert Y / flip rows at import if necessary. **Do not assume orientation without validation.**
5. Apply a simple landscape material for visually inspecting slopes. No photorealism, roads, traffic or live GIS connection is claimed in this alpha.

## Limits and next milestone

This is a real runnable terrain exporter, not a complete road network importer, city reconstruction, UE plugin, or verified end-to-end engine integration. The demo is fictional relief. `GEO-002` should add tested OSM/PBF extraction, lane/bridge semantic graph, building footprints, road meshes/splines, tiled World Partition landscape, and an editor-side import utility. Preserve OSM ODbL attribution and other source license conditions.

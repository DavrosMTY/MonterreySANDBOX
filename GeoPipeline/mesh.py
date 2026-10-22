"""GEO-002 geometry in right-handed grid East/North/Up metres, source datum Z."""
from pathlib import Path
import numpy as np
import rasterio
import shapely
from shapely.geometry import Polygon
import trimesh


class Surface:
    """Bilinear vertex sampling with strict bounds; no outside extrapolation."""
    def __init__(self, reference, manifest):
        self.manifest = manifest
        with rasterio.open(reference) as src:
            if src.crs.to_epsg() != 32614:
                raise ValueError('Expected EPSG:32614 reference')
            self.data = src.read(1)
        self.half = manifest['extent_m']/2
        self.spacing = manifest['sample_spacing_m']

    def __call__(self, xy):
        points = np.asarray(xy, dtype=float).reshape(-1, 2)
        col = (points[:, 0]+self.half)/self.spacing
        row = (self.half-points[:, 1])/self.spacing
        last = self.data.shape[0]-1
        if not np.isfinite(points).all() or np.any(col < -1e-6) or np.any(row < -1e-6) or np.any(col > last+1e-6) or np.any(row > last+1e-6):
            raise ValueError('Geometry outside reference vertex footprint')
        col, row = np.clip(col, 0, last), np.clip(row, 0, last)
        c, r = np.minimum(col.astype(int), last-1), np.minimum(row.astype(int), last-1)
        tx, ty = col-c, row-r
        result = ((1-tx)*(1-ty)*self.data[r, c] + tx*(1-ty)*self.data[r, c+1]
                  + (1-tx)*ty*self.data[r+1, c] + tx*ty*self.data[r+1, c+1])
        if not np.isfinite(result).all():
            raise ValueError('Invalid DEM sample')
        return result


def polygons(geometry):
    if geometry.is_empty:
        return []
    if geometry.geom_type == 'Polygon':
        return [geometry]
    if hasattr(geometry, 'geoms'):
        return [p for g in geometry.geoms for p in polygons(g)]
    return []


def densify_polygon(poly, spacing):
    def ring(points):
        result = []
        points = np.asarray(points)
        for a, b in zip(points[:-1], points[1:]):
            n = max(1, int(np.ceil(np.linalg.norm(b-a)/spacing)))
            result.extend(a+(b-a)*t/n for t in range(n))
        return result
    return Polygon(ring(poly.exterior.coords), [ring(r.coords) for r in poly.interiors])


def extrude(poly, lower, upper, wall_color, roof_color, module_height=None, interior_points=None, cap_triangles=None):
    """Closed constrained triangulation, including holes, welded at caps and walls.

    lower/upper are either scalar elevations or vectorized xy sample functions.
    Optional wall rows form reusable spandrel/window/spandrel facade modules.
    """
    if not poly.is_valid or poly.is_empty or poly.area < 1e-6:
        raise ValueError('Invalid extrusion footprint')
    # Geographic reprojection plus linear subdivision can produce almost-collinear
    # cap slivers below float32 interchange precision. Snap only derived geometry
    # to 0.1 mm, retaining source footprints unchanged and recording this policy.
    poly = shapely.set_precision(poly, .0001)
    if poly.geom_type != 'Polygon' or not poly.is_valid or poly.is_empty:
        raise ValueError('Footprint topology collapsed under 0.1 mm numerical grid')
    poly = shapely.orient_polygons(poly, exterior_cw=False)
    caps = (np.array([np.asarray(t.exterior.coords)[:3,:2] for t in shapely.constrained_delaunay_triangles(poly).geoms])
            if cap_triangles is None else np.asarray(cap_triangles,dtype=float))
    # Insert critical grade-crossing points into BOTH cap triangulations. A height
    # constraint not represented by a vertex can disappear during tessellation.
    from shapely.geometry import Point
    existing={tuple(np.round(p,8)) for tri in caps for p in tri}
    for point in ([] if interior_points is None else interior_points):
        point=np.round(np.asarray(point)/.0001)*.0001
        key=tuple(np.round(point,8))
        if key in existing or not poly.contains(Point(point)):continue
        # Batch barycentric containment avoids one Python/GEOS call per triangle.
        a,b=caps[:,1]-caps[:,0],caps[:,2]-caps[:,0]
        q=point-caps[:,0];det=a[:,0]*b[:,1]-a[:,1]*b[:,0]
        u=(q[:,0]*b[:,1]-q[:,1]*b[:,0])/det
        w=(a[:,0]*q[:,1]-a[:,1]*q[:,0])/det
        inside=(u>=-1e-10)&(w>=-1e-10)&(u+w<=1+1e-10)
        refined=[]
        for tri in caps[inside]:
            for i in range(3):
                candidate=np.asarray([tri[i],tri[(i+1)%3],point])
                area=abs(np.cross(np.append(candidate[1]-candidate[0],0),np.append(candidate[2]-candidate[0],0))[2])/2
                if area>1e-10:refined.append(candidate)
        if refined:
            caps=np.concatenate([caps[~inside],np.asarray(refined)])
            existing.add(key)
    sample_xy = np.unique(np.vstack(caps), axis=0)
    low_values = np.asarray(lower(sample_xy) if callable(lower) else np.full(len(sample_xy), lower))
    high_values = np.asarray(upper(sample_xy) if callable(upper) else np.full(len(sample_xy), upper))
    if not np.isfinite(low_values).all() or not np.isfinite(high_values).all() or np.any(high_values <= low_values):
        raise ValueError('Non-finite or non-positive extrusion elevations')
    z_lookup = {tuple(np.round(p, 8)): (lo, hi) for p, lo, hi in zip(sample_xy, low_values, high_values)}
    vertices, faces, colors, index = [], [], [], {}

    def v(x, y, z):
        key = (round(float(x), 8), round(float(y), 8), round(float(z), 8))
        if key not in index:
            index[key] = len(vertices); vertices.append(key)
        return index[key]

    def z_at(z, xy):
        col = 0 if z is lower else 1
        return np.asarray([z_lookup[tuple(np.round(p, 8))][col] for p in xy])

    def face(ids, color):
        faces.append(ids); colors.append(color)

    for triangle in caps:
        xy = triangle
        if np.cross(np.append(xy[1]-xy[0], 0), np.append(xy[2]-xy[0], 0))[2] < 0:
            xy = xy[::-1]
        bottom, top = z_at(lower, xy), z_at(upper, xy)
        if np.any(top <= bottom):
            raise ValueError('Non-positive extrusion thickness')
        face([v(*p, z) for p, z in zip(xy, top)], roof_color)
        face([v(*p, z) for p, z in zip(xy[::-1], bottom[::-1])], wall_color)
    for ring in [poly.exterior, *poly.interiors]:
        coords = np.asarray(ring.coords)[:, :2]
        low, high = z_at(lower, coords), z_at(upper, coords)
        if module_height is not None:
            if not np.allclose(low, low[0]) or not np.allclose(high, high[0]):
                raise ValueError('Facade module rows require horizontal caps')
            # Elevations around 500 m can turn exactly one 3.2 m storey into
            # 3.200000000000045 m. Do not create a zero-height extra storey.
            floor_count = max(1, int(np.ceil((high[0]-low[0]-1e-8)/module_height)))
            levels = [low[0]]
            for floor in range(floor_count):
                a, b = low[0]+floor*module_height, min(low[0]+(floor+1)*module_height, high[0])
                levels.extend([a+(b-a)*.22, a+(b-a)*.78, b])
        else:
            levels = None
        for i, (a, b) in enumerate(zip(coords[:-1], coords[1:])):
            rows = zip(levels[:-1], levels[1:]) if levels is not None else [(None, None)]
            for row, (z0, z1) in enumerate(rows):
                al, bl = (low[i], low[i+1]) if levels is None else (z0, z0)
                ah, bh = (high[i], high[i+1]) if levels is None else (z1, z1)
                ids = [v(*a, al), v(*b, bl), v(*b, bh), v(*a, ah)]
                color = [58, 93, 106, 255] if levels is not None and row % 3 == 1 and i % 3 != 0 else wall_color
                face([ids[0], ids[1], ids[2]], color); face([ids[0], ids[2], ids[3]], color)
    result = trimesh.Trimesh(vertices=np.asarray(vertices), faces=np.asarray(faces), process=False,
                             face_colors=np.asarray(colors, dtype=np.uint8))
    if not np.isfinite(result.vertices).all() or np.min(result.area_faces) <= 1e-12:
        raise ValueError('Degenerate or invalid mesh triangle')
    if not result.is_watertight or not result.is_winding_consistent or result.volume <= 0:
        raise ValueError(f'Extrusion is not a closed positive oriented solid: watertight={result.is_watertight}, winding={result.is_winding_consistent}, volume={result.volume}')
    return result


def terrain_meshes(surface, cells=8):
    """Chunk exactly the original vertex grid without simplifying the height field."""
    intervals = surface.data.shape[0]-1
    if intervals % cells:
        raise ValueError('Terrain intervals must divide chunk count')
    stride = intervals//cells
    for cy in range(cells):
        for cx in range(cells):
            row, col = np.mgrid[cy*stride:(cy+1)*stride+1, cx*stride:(cx+1)*stride+1]
            xyz = np.column_stack([(-surface.half+col*surface.spacing).ravel(),
                                   (surface.half-row*surface.spacing).ravel(), surface.data[row, col].ravel()])
            indices = np.arange((stride+1)**2).reshape(stride+1, stride+1)
            a, b, c, d = indices[:-1, :-1].ravel(), indices[:-1, 1:].ravel(), indices[1:, :-1].ravel(), indices[1:, 1:].ravel()
            faces = np.vstack([np.column_stack([a, c, b]), np.column_stack([b, c, d])])
            mesh = trimesh.Trimesh(xyz, faces, process=False)
            mesh.visual.face_colors = [132, 151, 113, 255]
            yield f'terrain_{cx}_{cy}', mesh


def enu_to_gltf():
    return np.array([[1., 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]])


def enu_to_unreal_cm(points):
    return np.asarray(points, dtype=float)*[100, -100, 100]

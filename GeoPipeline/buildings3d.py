"""OSM footprints to modular blockout solids with per-feature height provenance."""
import numpy as np
from shapely.geometry import Polygon

from .mesh import densify_polygon, extrude
from .urban import number

DEFAULTS = {
    'floor_height_m': 3.2, 'facade_bay_width_m': 4., 'foundation_embed_m': .25,
    'default_heights_m': {'residential': 6.4, 'commercial': 12.8, 'industrial': 8., 'civic': 12.8, 'unknown': 9.6, 'canopy': 4.5},
    'colors': {'residential': [200, 179, 148, 255], 'commercial': [180, 195, 200, 255],
               'industrial': [170, 174, 166, 255], 'civic': [211, 201, 177, 255],
               'unknown': [197, 184, 161, 255], 'canopy': [184, 179, 169, 255]},
}


def classify(tags):
    kind = tags.get('building')
    if kind == 'roof':
        return 'canopy'
    if kind in ('house', 'apartments', 'residential', 'detached', 'terrace', 'semidetached_house', 'dormitory'):
        return 'residential'
    if kind in ('industrial', 'warehouse', 'factory', 'manufacture'):
        return 'industrial'
    if kind in ('commercial', 'retail', 'hotel', 'office', 'supermarket') or 'shop' in tags:
        return 'commercial'
    if kind in ('church', 'chapel', 'cathedral', 'school', 'university', 'government', 'hospital', 'civic', 'public', 'college'):
        return 'civic'
    return 'unknown'


def heights(tags, config):
    category = classify(tags)
    explicit, floors = number(tags.get('height')), number(tags.get('building:levels'))
    if explicit is not None:
        top, provenance = explicit, 'osm_height_tag'
    elif floors is not None:
        top, provenance = floors*config['floor_height_m'], 'osm_levels_times_procedural_floor_height'
    else:
        top, provenance = config['default_heights_m'][category], 'procedural_class_default'
    minimum = number(tags.get('min_height'))
    if minimum is not None:
        bottom, minimum_source = minimum, 'osm_min_height_tag'
    else:
        min_levels = number(tags.get('building:min_level'))
        bottom, minimum_source = (min_levels*config['floor_height_m'], 'osm_min_level_times_procedural_floor_height') if min_levels else (0., 'ground_assumed')
    if category == 'canopy':
        bottom = max(bottom, top-.35); minimum_source = 'procedural_canopy_thickness'
    if not 0 <= bottom < top <= 500:
        raise ValueError('Invalid or unsupported building height range')
    return {'category': category, 'top_relative_ground_m': top, 'bottom_relative_ground_m': bottom,
            'height_source': provenance, 'height_estimated': provenance != 'osm_height_tag',
            'minimum_height_source': minimum_source, 'osm_levels': floors}


def footprint_parts(feature):
    parts = []
    for rings in feature['properties']['world_polygons_cm']:
        transformed = [np.asarray(ring, dtype=float)*[.01, -.01] for ring in rings]
        p = Polygon(transformed[0], transformed[1:])
        if not p.is_valid or p.area <= 0:
            raise ValueError(f'Invalid building footprint {feature["id"]}')
        parts.append(p)
    return parts


def generate(feature, surface, config, graybox=False):
    info = heights(feature['properties']['tags'], config)
    for part, original in enumerate(footprint_parts(feature)):
        poly = original if graybox else densify_polygon(original, config['facade_bay_width_m'])
        # Preserve dense foundation sampling even when facade panels are omitted.
        sample_poly = densify_polygon(original, config['facade_bay_width_m']) if graybox else poly
        samples = np.vstack([np.asarray(r.coords)[:-1] for r in [sample_poly.exterior, *sample_poly.interiors]])
        sample_heights=surface(samples)
        base = float(np.quantile(sample_heights, .10))
        bottom = base+info['bottom_relative_ground_m']-(config['foundation_embed_m'] if info['bottom_relative_ground_m'] == 0 else 0)
        if info['bottom_relative_ground_m']==0:
            bottom=min(bottom,float(sample_heights.min())-config['foundation_embed_m'])
        top = base+info['top_relative_ground_m']
        module_height = config['floor_height_m'] if info['category'] != 'canopy' and not graybox else None
        mesh = extrude(poly, bottom, top, config['colors'][info['category']], [132, 130, 119, 255], module_height)
        name = feature['id'].replace('/', '_')+f'_part{part}'
        record = dict(info, name=name, osm_id=feature['id'], part=part,
                      base_elevation_m=base, base_source='procedural_10th_percentile_DSM_perimeter_not_DTM',
                      bottom_m=bottom, top_m=top, footprint_area_m2=original.area,
                      footprint_holes=len(original.interiors), source_tags=feature['properties']['tags'],
                      roof_model='flat_blockout', facade_model='graybox_footprint_solid' if graybox else 'repeating_spandrel_window_panels',
                      facade_bay_width_m=config['facade_bay_width_m'],
                      facade_floor_height_m=config['floor_height_m'], placement_randomized=False)
        record['numerical_snap_grid_m'] = .0001
        record['foundation_skirt_extended_m'] = max(0.,base+info['bottom_relative_ground_m']-bottom)
        yield name, mesh, record, original

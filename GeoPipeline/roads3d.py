"""OSM road surfaces, pedestrian strips and grade-aware elevation estimates.

Widths and bridge/tunnel profiles are blockout estimates, never lane geometry.
"""
from collections import defaultdict
import heapq
import math
import re

import numpy as np
import shapely
from shapely.geometry import LineString, Point, box

from .mesh import densify_polygon, extrude, polygons
from .urban import number

DEFAULTS = {
    'lane_width_m': 3.2, 'shoulder_total_m': .4, 'sidewalk_width_m': 1.8,
    'road_lift_m': .12, 'slab_thickness_m': .25, 'bridge_slab_thickness_m': .6,
    'bridge_clearance_estimate_m': 5.5, 'tunnel_depth_estimate_m': 6.,
    'transition_length_m': 45., 'tunnel_interior_height_m': 4.5,
    'mesh_edge_spacing_m': 6., 'building_clearance_m': .15,
    'default_widths_m': {'motorway': 10., 'trunk': 10., 'primary': 9.6, 'secondary': 9.6,
                         'tertiary': 6.4, 'residential': 6.4, 'service': 4., 'living_street': 5.,
                         'footway': 1.8, 'pedestrian': 4., 'steps': 2., 'cycleway': 2.2, 'default': 5.},
}
WALK = {'footway', 'pedestrian', 'steps', 'path', 'cycleway', 'bridleway'}


def grade(tags):
    raw = tags.get('layer', '0')
    layer = int(raw) if re.fullmatch(r'-?\d+', raw) and -5 <= int(raw) <= 5 else 0
    if tags.get('bridge', 'no') not in ('no', 'false', '0'):
        kind = 'bridge'
    elif tags.get('tunnel', 'no') not in ('no', 'false', '0', 'building_passage'):
        kind = 'tunnel'
    elif layer > 0:
        kind = 'elevated_inferred'
    elif layer < 0:
        kind = 'depressed_inferred'
    else:
        kind = 'surface'
    return kind, layer


def width(tags, config):
    if number(tags.get('width')) is not None:
        return number(tags['width']), 'osm_width_tag'
    lanes = number(tags.get('lanes'))
    if lanes is not None and lanes.is_integer() and 1 <= lanes <= 12 and tags.get('highway') not in WALK:
        return lanes*config['lane_width_m']+config['shoulder_total_m'], 'osm_lanes_times_procedural_lane_width'
    key = tags.get('highway', '').removesuffix('_link')
    return config['default_widths_m'].get(key, config['default_widths_m']['default']), 'procedural_highway_class_default'


class Network:
    def __init__(self, urban, surface, config):
        self.surface, self.config = surface, config
        self.roads, self.incident = [], defaultdict(list)
        graph = urban['graph_nodes']
        edge_lookup = defaultdict(list)
        for edge in urban['directed_edges']:
            edge_lookup[edge['road_id']].append(edge)
        self.nodes = {k: [v['xy_cm'][0]/100, -v['xy_cm'][1]/100] for k, v in graph.items()}
        for road in urban['roads']:
            xy = np.asarray(road['xy_cm'])*[.01, -.01]
            line = LineString(xy)
            kind, layer = grade(road['tags'])
            candidates = {n for e in edge_lookup[road['id']] for n in (e['from'], e['to'])}
            ends = []
            for i, p in enumerate((xy[0], xy[-1])):
                key = next((n for n in sorted(candidates) if np.linalg.norm(np.asarray(self.nodes[n])-p) < 1e-5), None)
                if key is None:
                    key = f'unresolved:{road["id"]}:{i}'; self.nodes[key] = p.tolist()
                ends.append(key)
            w, width_source = width(road['tags'], config)
            if not math.isfinite(w) or not 0 < w <= 60:
                raise ValueError('Unsupported road width')
            role = 'walkway' if road['tags'].get('highway') in WALK else 'carriageway'
            sidewalk = road['tags'].get('sidewalk')
            if sidewalk in ('no', 'none', 'separate') or role == 'walkway' or kind != 'surface':
                sw, sw_source = 0, 'none_or_separately_mapped'
            elif sidewalk in ('both', 'left', 'right', 'yes'):
                sw, sw_source = config['sidewalk_width_m'], 'osm_tag_with_procedural_width'
            elif road['tags'].get('highway') in ('residential', 'tertiary', 'secondary', 'primary', 'living_street'):
                sw, sw_source = config['sidewalk_width_m'], 'procedural_urban_class_default'
            else:
                sw, sw_source = 0, 'not_generated'
            record = {'id': road['id'], 'osm_way_id': road['osm_way_id'], 'tags': road['tags'],
                      'line': line, 'end_nodes': ends, 'kind': kind, 'layer': layer,
                      'role': role, 'width_m': w, 'width_source': width_source,
                      'sidewalk_m': sw, 'sidewalk_source': sw_source,
                      'sidewalk_sides': sidewalk if sidewalk in ('left', 'right') else 'both',
                      'lane_count_tag': road['tags'].get('lanes'), 'lane_geometry_generated': False,
                      'elevation_source': 'DSM_proxy_plus_procedural_grade_profile',
                      'elevation_estimated': True,
                      'vehicle_candidate': role == 'carriageway' and road['tags'].get('access') not in ('no', 'private')
                                           and road['tags'].get('motor_vehicle') not in ('no', 'private')}
            self.roads.append(record)
            for node in set(ends):
                self.incident[node].append(len(self.roads)-1)
        self.distances, self.targets = {}, {}
        self.constraints = defaultdict(dict)
        for kind in {r['kind'] for r in self.roads} - {'surface'}:
            adj, targets = defaultdict(list), {}
            for road in [r for r in self.roads if r['kind'] == kind]:
                a, b = road['end_nodes']; length = road['line'].length
                adj[a].append((b, length)); adj[b].append((a, length))
                value = abs(road['layer']) or 1
                for n in (a, b): targets[n] = max(targets.get(n, 1), value)
            portals = []
            for node in adj:
                touching_surface = any(self.roads[i]['kind'] != kind for i in self.incident[node])
                boundary = max(abs(v) for v in self.nodes[node]) >= surface.half-.01
                if touching_surface or (len(adj[node]) == 1 and not boundary):
                    portals.append(node)
            distance = {n: math.inf for n in adj}; queue = []
            for n in portals:
                distance[n] = 0.; heapq.heappush(queue, (0., n))
            while queue:
                d, n = heapq.heappop(queue)
                if d != distance[n]: continue
                for neighbor, cost in adj[n]:
                    if d+cost < distance[neighbor]:
                        distance[neighbor] = d+cost; heapq.heappush(queue, (d+cost, neighbor))
            self.distances[kind], self.targets[kind] = distance, targets
        self.clearance_audit = self.enforce_clearances()

    def enforce_clearances(self):
        """Separate source-disconnected grade crossings by procedural vertical constraints.

        Planimetry and graph edges stay unchanged. This is blockout geometry, not
        evidence of surveyed elevations, safe gradients or engineering clearances.
        """
        lines = [r['line'] for r in self.roads]; tree = shapely.STRtree(lines)
        crossings = []
        def rank(r):
            level = (abs(r['layer']) or 1)
            sign = 1 if r['kind'] in ('bridge','elevated_inferred') else -1 if r['kind'] in ('tunnel','depressed_inferred') else 0
            return (sign*level,r['layer'],r['id'])
        for i,road in enumerate(self.roads):
            if road['kind']=='surface': continue
            for j in tree.query(road['line'],predicate='intersects'):
                other=self.roads[j]
                if i==j or (other['kind']!='surface' and j<i):continue
                if (road['kind'],road['layer'])==(other['kind'],other['layer']):continue
                if set(road['end_nodes']) & set(other['end_nodes']):continue
                p=road['line'].intersection(other['line'])
                pts=[p] if p.geom_type=='Point' else list(p.geoms) if p.geom_type=='MultiPoint' else []
                for point in pts:
                    lower,upper=sorted((road,other),key=rank)
                    crossings.append((lower,upper,point))
        applied,unresolved=0,[]
        required=self.config['bridge_clearance_estimate_m']+self.config['bridge_slab_thickness_m']
        for iteration in range(8):
            changes=0
            for lower,upper,p in sorted(crossings,key=lambda c:rank(c[1])):
                xy=np.array([[p.x,p.y]])
                low_z,high_z=self.z(xy,[lower])[0],self.z(xy,[upper])[0]
                if high_z-low_z >= required-.001:continue
                selected=upper if upper['kind'] in ('bridge','elevated_inferred') else lower
                sign=1 if selected is upper else -1
                desired=(low_z+required if sign>0 else high_z-required)-self.surface(xy)[0]-self.config['road_lift_m']
                position=selected['line'].project(p); length=selected['line'].length
                if position<.001 or length-position<.001:
                    unresolved.append({'road':selected['id'],'reason':'crossing_at_source_endpoint','xy_enu_m':[p.x,p.y]})
                    continue
                margin=max(8.,(lower if sign>0 else upper)['width_m']/2+6.)
                for s in (max(.001,position-margin),position,min(length-.001,position+margin)):
                    previous=self.constraints[selected['id']].get(s,0.)
                    self.constraints[selected['id']][s]=max(previous,desired) if sign>0 else min(previous,desired)
                applied+=1;changes+=1
            if not changes:break
        self.crossing_points=crossings
        return {'crossings':len(crossings),'constraint_updates':applied,'required_top_separation_estimate_m':required,
                'unresolved_endpoint_cases':unresolved,'surveyed_elevations_used':False,
                'engineering_gradients_validated':False,'source_xy_or_graph_edges_changed':False}

    def z(self, xy, roads):
        xy = np.asarray(xy).reshape(-1, 2)
        values = self.surface(xy)+self.config['road_lift_m']
        if roads[0]['kind'] == 'surface':
            return values
        lines = np.asarray([r['line'] for r in roads], dtype=object)
        # Numerical nearest only selects an elevation proxy. It never creates graph edges.
        nearest = shapely.STRtree(lines).nearest(shapely.points(xy))
        distances = shapely.line_locate_point(lines[nearest], shapely.points(xy))
        for index in np.unique(nearest):
            selected = nearest == index; r = roads[index]; a, b = r['end_nodes']
            d = distances[selected]; length = r['line'].length
            portal = np.minimum(self.distances[r['kind']][a]+d, self.distances[r['kind']][b]+length-d)
            t = np.clip(portal/self.config['transition_length_m'], 0, 1)
            ramp = t*t*(3-2*t)
            target = self.targets[r['kind']][a]*(1-d/length)+self.targets[r['kind']][b]*(d/length)
            delta = self.config['bridge_clearance_estimate_m'] if r['kind'] in ('bridge', 'elevated_inferred') else -self.config['tunnel_depth_estimate_m']
            values[selected] += ramp*delta*target
            controls=self.constraints.get(r['id'])
            if controls:
                def endpoint_offset(node):
                    t=min(self.distances[r['kind']][node]/self.config['transition_length_m'],1.)
                    return (t*t*(3-2*t))*delta*self.targets[r['kind']][node]
                samples={0.:endpoint_offset(a),length:endpoint_offset(b),**controls}
                positions=sorted(samples)
                proxy=np.interp(d,positions,[samples[s] for s in positions])
                baseline=values[selected]-self.surface(xy[selected])-self.config['road_lift_m']
                corrected=np.maximum(baseline,proxy) if delta>0 else np.minimum(baseline,proxy)
                values[selected]+=corrected-baseline
        return values

    def semantic_graph(self, original):
        road_lookup = {r['id']: r for r in self.roads}
        records = []
        for r in self.roads:
            record = {k: v for k, v in r.items() if k != 'line'}
            record['source_centerline_enu_m'] = [[*p, float(z)] for p, z in zip(r['line'].coords, self.z(r['line'].coords, [r]))]
            samples=sorted(set(np.linspace(0,r['line'].length,max(2,int(np.ceil(r['line'].length/5))+1)).tolist()+list(self.constraints.get(r['id'],{}))))
            xy=np.array([[r['line'].interpolate(s).x,r['line'].interpolate(s).y] for s in samples])
            z=self.z(xy,[r]); record['centerline_enu_m']=[[float(p[0]),float(p[1]),float(h)] for p,h in zip(xy,z)]
            record['max_sampled_grade_percent']=float(np.max(np.abs(np.diff(z))/np.diff(samples))*100)
            record['procedural_clearance_constraints']=[{'distance_along_m':s,'offset_from_DSM_m':v} for s,v in sorted(self.constraints.get(r['id'],{}).items())]
            records.append(record)
        return {'schema_version': 1, 'coordinates': 'East North Up metres, source vertical datum',
                'roads': records, 'nodes': {n: {'xy_enu_m': xy, 'source_node_id': n,
                                             'incident_grade_kinds': sorted({self.roads[i]['kind'] for i in self.incident[n]})}
                                        for n, xy in self.nodes.items()},
                'directed_edges': [dict(e, grade=road_lookup[e['road_id']]['kind'], layer=road_lookup[e['road_id']]['layer'],
                                        vehicle_candidate=road_lookup[e['road_id']]['vehicle_candidate']) for e in original['directed_edges']],
                'lane_graph_generated': False, 'new_geometric_crossing_connections': 0,
                'turn_restrictions_processed': False, 'road_geometry_may_be_trimmed_to_avoid_buildings': True,
                'clearance_constraint_audit':self.clearance_audit}


def generate(network, building_obstacles, cells, *, extruder=extrude, densifier=densify_polygon):
    """Union only same-grade surfaces; clip buildings instead of moving them.

    A buffer union fills actual same-level junction footprints. Source graph nodes
    alone define logical connectivity. No union or graph snapping between grades.
    """
    c, half = network.config, network.surface.half
    bounds = box(-half, -half, half, half)
    raw_obstacle = shapely.union_all(building_obstacles) if building_obstacles else PolygonEmpty()
    obstacle = raw_obstacle.buffer(c['building_clearance_m'])
    groups, records = defaultdict(list), []
    for r in network.roads:
        poly = r['line'].buffer(r['width_m']/2, cap_style='round', join_style='round', quad_segs=2).intersection(bounds)
        trimmed = 0.
        if r['kind'] == 'surface':
            before = poly.area; poly = poly.difference(obstacle); trimmed = max(0., before-poly.area)
        group=(r['kind'],r['layer'],r['role'],r['component']) if getattr(network,'separate_structure_components',False) and r['kind']!='surface' else (r['kind'],r['layer'],r['role'])
        groups[group].append((poly,r))
        records.append({'road_id': r['id'], 'building_overlap_removed_m2': trimmed})
    ground_vehicle = shapely.union_all([p for key, pairs in groups.items() if key[0] == 'surface' and key[2] == 'carriageway' for p, _ in pairs])
    sidewalks = []
    for r in network.roads:
        if not r['sidewalk_m']: continue
        if r['sidewalk_sides'] in ('left', 'right'):
            sign = 1 if r['sidewalk_sides'] == 'left' else -1
            outer = r['line'].offset_curve(sign*(r['width_m']/2+r['sidewalk_m']/2)).buffer(r['sidewalk_m']/2, cap_style='flat', quad_segs=2)
        else:
            outer = r['line'].buffer(r['width_m']/2+r['sidewalk_m'], cap_style='round', quad_segs=2)
        sidewalks.append(outer.intersection(bounds))
    sidewalk = shapely.union_all(sidewalks).difference(ground_vehicle).difference(obstacle)
    if not sidewalk.is_empty:
        source = [r for r in network.roads if r['kind'] == 'surface' and r['sidewalk_m']]
        groups['surface', 0, 'sidewalk'] = [(sidewalk, source[0])]
    step = 2*half/cells
    for group,pairs in sorted(groups.items()):
        kind,layer,role=group[:3]
        suffix='_c'+str(group[3])if len(group)>3 else ''
        geometry = shapely.union_all([p for p, _ in pairs])
        if kind == 'surface' and role == 'walkway':
            geometry = geometry.difference(ground_vehicle)
        geometry = shapely.set_precision(geometry, .001)
        roads = [r for _, r in pairs]
        if role == 'sidewalk':
            roads = [r for r in network.roads if r['kind'] == 'surface']
        extra = .08 if role in ('sidewalk', 'walkway') else 0.
        ids={r['id'] for r in roads}; critical={}
        for lower,upper,p in network.crossing_points:
            for r in (lower,upper):
                if r['id'] not in ids:continue
                key=(p.x,p.y); value=float(network.z([[p.x,p.y]],[r])[0])+extra
                if key not in critical:critical[key]=value
                elif kind in ('bridge','elevated_inferred'):critical[key]=max(critical[key],value)
                elif kind in ('tunnel','depressed_inferred'):critical[key]=min(critical[key],value)
        if hasattr(network, 'profiles'):
            for r in roads:
                points=network.profiles[r['id']]['xy']
                if getattr(network,'continuous_cap_field',False):
                    values=network.z(points,roads)+extra
                    for point,value in zip(points,values):critical[tuple(np.round(point,4))]=float(value)
                else:
                    for point in points:
                        key=tuple(np.round(point,4));critical[key]=float(network.z([point],[r])[0])+extra
        def sampler(xy,selected=roads,lift=extra):
            xy=np.asarray(xy); values=network.z(xy,selected)+lift
            if hasattr(network, 'profiles'):
                for i, point in enumerate(xy):
                    key=tuple(np.round(point,4))
                    if key in critical: values[i]=critical[key]
                return values
            for point,height in critical.items():
                match=np.max(np.abs(xy-np.asarray(point)),axis=1)<.0002
                values[match]=height
            return values
        depth = c['bridge_slab_thickness_m'] if kind in ('bridge', 'elevated_inferred') else c['slab_thickness_m']
        color = [63, 66, 70, 255] if role == 'carriageway' else [179, 174, 160, 255]
        if kind in ('bridge', 'elevated_inferred'): color = [83, 91, 104, 255]
        if kind in ('tunnel', 'depressed_inferred'): color = [86, 77, 68, 255]
        for cy in range(cells):
            for cx in range(cells):
                cell = box(-half+cx*step, -half+cy*step, -half+(cx+1)*step, -half+(cy+1)*step)
                clipped = geometry.intersection(cell)
                for part, p in enumerate(polygons(clipped)):
                    if p.area < .05: continue
                    p = densifier(p, c['mesh_edge_spacing_m'])
                    name = (f'{kind}_{layer}_{role}_{cx}_{cy}_{part}'+suffix).replace('-', 'minus')
                    local_critical = {k:v for k,v in critical.items() if p.bounds[0] <= k[0] <= p.bounds[2] and p.bounds[1] <= k[1] <= p.bounds[3]}
                    def bottom(xy):
                        values=sampler(xy)-depth
                        if hasattr(network,'terrain_surface') and kind in ('surface','depressed_inferred'):
                            values=np.minimum(values,network.terrain_surface(xy)-.25)
                        return values
                    try:
                        mesh = extruder(p, bottom, sampler, color, color, interior_points=local_critical)
                    except ValueError as exc:
                        # Never turn a geometry failure into a successful silent omission.
                        raise ValueError(f'Road solid {name}: {exc}') from exc
                    meta = {'name': name, 'kind': kind, 'layer': layer, 'role': role, 'cell': [cx, cy],
                            'elevation_estimated': True, 'profile_source': 'DSM_plus_procedural_profile',
                            'source_road_ids': [r['id'] for poly, r in pairs if poly.intersects(cell)],
                            'slab_thickness_m': depth, 'terrain_cut_for_tunnel': hasattr(network, 'profiles') and kind == 'tunnel',
                            'ground_building_projected_overlap_m2': p.intersection(raw_obstacle).area if kind == 'surface' else None}
                    yield name, mesh, meta
                    if kind == 'tunnel' and role == 'carriageway':
                        # Roof lining is a closed slab. Portals and terrain excavation are unresolved.
                        roof_z = lambda xy: sampler(xy)+c['tunnel_interior_height_m']
                        roof = extruder(p, roof_z, lambda xy: roof_z(xy)+.3, [115, 111, 101, 255], [115, 111, 101, 255], interior_points=local_critical)
                        yield name+'_lining_roof', roof, dict(meta, name=name+'_lining_roof', role='tunnel_lining_roof')
    network.geometry_audit = records


def PolygonEmpty():
    from shapely.geometry import Polygon
    return Polygon()

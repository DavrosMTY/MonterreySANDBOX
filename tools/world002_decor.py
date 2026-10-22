"""Conservative visual overlay. Original road geometry/graph is read-only."""
from collections import Counter,defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from pyproj import Transformer
import shapely
from shapely.geometry import LineString,Point,box

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from GeoPipeline.qa_world import HeightIndex


def lane_policy(tags):
    lanes=tags.get('lanes','')
    if not re.fullmatch(r'[1-6]',str(lanes)):return None
    n=int(lanes);oneway=str(tags.get('oneway','')).lower()
    if n<2:return None
    if oneway in ('yes','1','true','-1'):return {'count':n,'dividers':n-1,'color':'white','oneway':oneway}
    if n==2 and oneway in ('no','0','false'):return {'count':2,'dividers':1,'color':'yellow','oneway':oneway}
    return None  # Unknown direction or asymmetric allocation: never invent a divider.


def enu_triangles(mesh):
    points=mesh.vertices[:,[0,2,1]]*np.array([1,-1,1])
    return points[mesh.faces]


def overlays(sectors, roads, center):
    source_path=ROOT/'WebViewer/visual/osm-street-inventory.json'
    source=json.loads(source_path.read_text());receipt=json.loads(source_path.with_suffix('.source.json').read_text())
    if hashlib.sha256(source_path.read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('Street inventory provenance changed')
    ground=[];carriage=[];sidewalk=[];building_boxes=[]
    for cell,groups in sectors.items():
        for system,parts in groups.items():
            for name,mesh,r in parts:
                if system=='Buildings':
                    b=r['bounds_enu_m'];building_boxes.append(box(b[0][0]-2.2,b[0][1]-2.2,b[1][0]+2.2,b[1][1]+2.2));continue
                if r.get('kind','surface')!='surface' or r.get('layer',0)!=0:continue
                tri=enu_triangles(mesh)
                if r['role'] in ('terrain','sidewalk','carriageway','walkway'):ground.append(tri)
                if r['role']=='carriageway':carriage.append(tri)
                if r['role']=='sidewalk':
                    normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);valid=np.flatnonzero(normal[:,2]>1.0)
                    if len(valid):
                        choice=valid[np.argmax(normal[valid,2])];sidewalk.append((name,tri[choice].mean(axis=0)))
    height=HeightIndex(np.concatenate(ground));road_height=HeightIndex(np.concatenate(carriage))
    blocked=shapely.STRtree(building_boxes)
    available=[r for r in roads.values() if r['kind']=='surface' and r['role']=='carriageway' and r.get('layer',0)==0]
    lines=[LineString(np.asarray(r['centerline_enu_m'])[:,:2])for r in available];near=shapely.STRtree(lines)
    cells=defaultdict(list);stats=Counter();skips=Counter()
    def add(kind,x,y,z,source_id,placement='osm_node',**extra):
        if not np.isfinite([x,y,z]).all() or not(-1000<=x<=1000 and -1000<=y<=1000):return
        cell=f'{min(7,int((x+1000)//250))}_{min(7,int((y+1000)//250))}'
        cells[cell].append({'kind':kind,'position':[round(x,5),round(z,5),round(-y,5)],
                            'source_id':source_id,'placement':placement,'dimensions_estimated':True,
                            'height_source':'existing_exported_surface_estimate','decorative':placement!='osm_node',**extra})
        stats[kind]+=1
    def mark(kind,xy,direction,length,width,source_id,**meta):
        normal=np.array([-direction[1],direction[0]])
        corners=np.array([xy+direction*a*length/2+normal*b*width/2 for a,b in ((-1,-1),(-1,1),(1,-1),(1,1))])
        z=road_height.heights(corners)
        if not np.isfinite(z).all() or np.ptp(z)>max(length,width)*.18:
            skips['paint_missing_or_steep_surface']+=1;return
        samples=road_height.heights([xy-direction*length/2,xy+direction*length/2])
        if not np.isfinite(samples).all():return
        add(kind,*xy,float(z.mean())+.026,source_id,'inferred_marking_on_tagged_road',
            yaw=math.atan2(-direction[0],-direction[1]),length=length,width=width,
            slope=float((samples[1]-samples[0])/length),**meta)
    # Keep only explicit lane-count + direction combinations; no new graph/circulation.
    for r,line in zip(available,lines):
        policy=lane_policy(r['tags'])
        if policy is None:continue
        width=r['width_m']
        for s in np.arange(7.,line.length-5.,10.):
            p=np.array(line.interpolate(s).coords[0]);a=np.array(line.interpolate(max(0,s-.5)).coords[0]);b=np.array(line.interpolate(min(line.length,s+.5)).coords[0]);d=b-a;d/=np.linalg.norm(d)
            for lane in range(1,policy['count']):
                offset=(lane/policy['count']-.5)*width
                mark('lane_'+policy['color'],p+np.array([-d[1],d[0]])*offset,d,3.,.12,r['id'],
                     source_lanes=policy['count'],source_oneway=policy['oneway'],width_estimated=r['width_source']!='osm_width_tag')
    tr=Transformer.from_crs('EPSG:4326','EPSG:32614',always_xy=True)
    real_tree_positions=[]
    for node in source['elements']:
        east,north=tr.transform(node['lon'],node['lat']);xy=np.array([east-center[0],north-center[1]])
        z=height.heights([xy])[0]
        if not np.isfinite(z):skips['osm_node_missing_ground']+=1;continue
        tags=node['tags'];sid=f"node/{node['id']}";h=tags.get('highway');amenity=tags.get('amenity')
        if tags.get('natural')=='tree':
            palm='phoenix' in str(tags).lower() or 'palm' in str(tags).lower();real_tree_positions.append(xy)
            add('palm' if palm else 'tree',*xy,z,sid,source_tags=tags)
        elif h=='crossing':
            idx=int(near.nearest(Point(xy)));line=lines[idx];r=available[idx];s=line.project(Point(xy))
            if line.distance(Point(xy))>12:skips['crossing_not_near_motor_road']+=1;continue
            a=np.array(line.interpolate(max(0,s-.5)).coords[0]);b=np.array(line.interpolate(min(line.length,s+.5)).coords[0]);d=b-a;d/=np.linalg.norm(d);side=np.array([-d[1],d[0]])
            for offset in np.arange(-1.8,1.81,.9):mark('crossing',xy+d*offset,side,min(r['width_m']*.8,12),.43,sid,source_tags=tags)
        else:
            kind={'traffic_signals':'signal','street_lamp':'lamp','stop':'stop','give_way':'give_way'}.get(h)
            kind=kind or {'bench':'bench','waste_basket':'bin','bicycle_parking':'bike_rack'}.get(amenity)
            if kind:add(kind,*xy,z,sid,source_tags=tags,orientation_estimated=True)
    # Sparse decorative street planting and lamps only on an existing sidewalk cap.
    occupied=set();counts=Counter()
    for name,point in sorted(sidewalk):
        x,y,z=point;key=(int(x//45),int(y//45))
        if key in occupied or len(blocked.query(Point(x,y),predicate='intersects')):continue
        if any(np.linalg.norm(point[:2]-p)<12 for p in real_tree_positions):continue
        occupied.add(key);seed=int(hashlib.sha256(name.encode()).hexdigest()[:8],16)
        kind=('tree','lamp','tree','bench')[seed%4]
        if counts[kind]>= {'tree':128,'lamp':80,'bench':32}[kind]:continue
        counts[kind]+=1;add(kind,x,y,z,'world002/decor/'+name,'procedural_on_existing_sidewalk',source_mesh=name)
    return {'schema_version':1,'source_inventory_sha256':receipt['sha256'],
            'source_timestamp':source.get('osm3s',{}).get('timestamp_osm_base'),
            'geography_or_lane_graph_modified':False,'all_dimensions_and_facade_layouts_are_visual_estimates':True,
            'lane_policy':'Explicit 1..6 lanes and explicit oneway required; two-way center divider only when lanes=2. Paint layout is a proposal, not surveyed markings.',
            'stats':dict(stats),'skipped':dict(skips),'decorative_counts':dict(counts),'sectors':dict(cells)}

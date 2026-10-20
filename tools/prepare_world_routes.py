"""Select an offline QA-gated directed route and probes for future UE traces."""
import argparse
import heapq
import json
from pathlib import Path


def select_route(semantics,audit,max_length=1500.):
    roads={r['id']:r for r in semantics['roads']}
    allowed={r['id'] for r in audit['roads'] if r['vehicle_candidate'] and r['status']=='offline_geometry_candidate'}
    adj={};undirected={}
    for e in semantics['directed_edges']:
        if e['road_id'] not in allowed:continue
        adj.setdefault(e['from'],[]).append(e)
        for a,b in ((e['from'],e['to']),(e['to'],e['from'])):undirected.setdefault(a,set()).add(b)
    remaining=set(undirected);components=[]
    while remaining:
        stack=[next(iter(remaining))];component=set()
        while stack:
            node=stack.pop()
            if node in component:continue
            component.add(node);stack.extend(undirected[node]-component)
        remaining-=component;components.append(component)
    if not components:return {'status':'no_eligible_directed_route','edges':[]}
    component=max(components,key=len)
    start=min(component,key=lambda n:sum(v*v for v in semantics['nodes'][n]['xy_enu_m']))
    dist={start:0.};parent={};queue=[(0.,start)]
    while queue:
        distance,node=heapq.heappop(queue)
        if distance!=dist[node]:continue
        for edge in adj.get(node,[]):
            target=edge['to'];value=distance+edge['length_m']
            if value<=max_length and value<dist.get(target,float('inf')):
                dist[target]=value;parent[target]=(node,edge);heapq.heappush(queue,(value,target))
    end=max(dist,key=dist.get);path=[];node=end
    while node!=start:
        node,edge=parent[node];path.append(edge)
    path.reverse()
    return {'status':'offline_directed_candidate_not_driving_certificate','start':start,'end':end,
            'length_m':dist[end],'largest_eligible_weak_component_nodes':len(component),'eligible_road_count':len(allowed),
            'edges':path,'engine_driven':False,'physical_width_and_capsule_sweeps_validated':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--city',required=True);p.add_argument('--qa',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();city=Path(a.city);out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
    s=json.loads((city/'road_semantics.json').read_text());q=json.loads(Path(a.qa).read_text());m=json.loads((city/'manifest.json').read_text())
    if q['model_sha256']!=m['glb_sha256']:raise ValueError('Route QA belongs to another model')
    route=select_route(s,q);roads={r['id']:r for r in s['roads']};probes=[]
    for e in route['edges']:
        points=roads[e['road_id']]['centerline_enu_m']
        for point in points[::max(1,len(points)//4)]:
            x,y,z=point;probes.append({'road_id':e['road_id'],'position_unreal_cm':[x*100,-y*100,z*100]})
    route['model_sha256']=m['glb_sha256']
    (out/'offline_route.json').write_text(json.dumps(route,indent=2)+'\n')
    (out/'traversal_probes.json').write_text(json.dumps({'model_sha256':m['glb_sha256'],'probes':probes,
        'expected_surface_tolerance_cm':8.,'native_trace_executed':False,'capsule_sweep_executed':False},indent=2)+'\n')
    print(json.dumps({k:v for k,v in route.items() if k!='edges'},indent=2))


if __name__=='__main__':main()

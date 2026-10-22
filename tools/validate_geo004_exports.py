"""Read all delivered OBJ exports and verify centimetres, pivots, IDs and topology counts."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def validate(city,receipt):
    city=Path(city).resolve();m=json.loads((city/'manifest.json').read_text());records={r['name']:r for r in m['mesh_parts']}
    maximum=0.;total_triangles=0;objects=[]
    for cell in m['ue_system_cells']:
        path=(city/cell['file']).resolve();assert path.is_relative_to(city)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==cell['sha256']
        assert path.with_suffix('.mtl').is_file()
        low=np.full(3,np.inf);high=np.full(3,-np.inf);names=[];vertices=0;triangles=0;header=False
        with path.open()as source:
            for line in source:
                if line.startswith('#')and 'centimetres'in line:header=True
                elif line.startswith('v '):
                    p=np.fromstring(line[2:],sep=' ');assert p.shape==(3,)and np.isfinite(p).all();low=np.minimum(low,p);high=np.maximum(high,p);vertices+=1
                elif line.startswith('f '):
                    face=[int(i)for i in line.split()[1:]];assert len(face)==3 and min(face)>0 and max(face)<=vertices;triangles+=1
                elif line.startswith('o '):names.append(line[2:].strip())
        assert header and names==cell['source_mesh_names']
        bounds=np.array([records[n]['bounds_enu_m']for n in names]);lo=bounds[:,0].min(axis=0);hi=bounds[:,1].max(axis=0)
        expected=np.array([[lo[0],-hi[1],lo[2]],[hi[0],-lo[1],hi[2]]])*100-np.array(cell['position_unreal_cm'])
        error=float(np.max(abs(np.array([low,high])-expected)));assert error<.001,(path,error)
        assert triangles==sum(records[n]['triangle_count']for n in names)
        assert vertices==sum(records[n]['vertex_count']for n in names)
        maximum=max(maximum,error);total_triangles+=triangles;objects.extend(names)
    assert len(objects)==len(set(objects))and set(objects)==set(records)
    result={'status':'passed','source_glb_sha256':m['glb_sha256'],'obj_system_cells_checked':len(m['ue_system_cells']),'mesh_names_preserved':len(objects),'triangles_checked':total_triangles,'maximum_bounds_error_cm':maximum,'obj_units':'centimetres','axes':'X east / Y south / Z up','pivot_units':'centimetres','glb_and_gis_units':'metres','unreal_import_executed':False,'absolute_survey_accuracy_certified':False}
    Path(receipt).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--city',required=True);p.add_argument('--receipt',required=True);a=p.parse_args();validate(a.city,a.receipt)

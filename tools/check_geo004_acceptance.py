"""Geometric regression gate; pending source/engineering reviews remain explicit."""
import argparse
import json
from pathlib import Path


def check(audit,validation):
    a=json.loads(Path(audit).read_text());v=json.loads(Path(validation).read_text())
    assert a['milestone']=='GEO-004'and v['source_year']==2007
    assert a['model_sha256']==v['source_model_sha256']
    assert a['counts']['cap_triangles_support_error_over_25cm']==0
    assert a['counts']['parts_with_at_grade_skirt_over_1m']==0
    for field in ('at_grade_roads_with_support_error_over_25cm','non_elevated_buildings_floating_over_50cm','buildings_terrain_above_roof_over_25cm','bridge_parts_terrain_above_deck_over_25cm','estimated_support_gaps_over_25cm'):
        assert v[field]==0,(field,v[field])
    for field in ('crossings_potential_structure_overlap','crossings_missing_surface','roads_missing_centerline_surface'):
        assert v[field+'_after']<=v[field+'_before'],field
    assert v['source_graph_edges_preserved']==4194 and v['road_ids_and_tags_preserved']==2665 and v['buildings_preserved']==1136
    assert v['numerical_geometry_after']['post_float32_degenerate_triangles']==0
    assert v['terrain_sector_boundary_support_error_max_m']<.001
    assert v['absolute_accuracy_certified']is False and v['original_source_epv_m']is None
    print(json.dumps({'status':'passed_geometric_regression_gate','absolute_accuracy_certified':False,'engineering_validation_pending':True}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',required=True);p.add_argument('--validation',required=True);a=p.parse_args();check(a.audit,a.validation)

"""GEO-004 regressions: native terrain planes, NoData, coherent caps and portals."""
import json
from pathlib import Path

import numpy as np
import pytest
from shapely.geometry import LineString,Point,Polygon

from GeoPipeline.geo004 import PlanarDTM,grid_boundary,grid_extrude,native_caps,portal_mask,TerrainNetwork
from GeoPipeline.geo004_sources import xyz_grid,require_valid_stencil
from GeoPipeline.qa_world import HeightIndex


def field(values):
    s=object.__new__(PlanarDTM);s.data=np.asarray(values,dtype=float);s.half=5.;s.spacing=10.;return s


def test_native_surface_preserves_steep_measured_grid_values_and_diagonal():
    s=field([[500,510],[520,540]])
    assert np.array_equal(s([[-5,5],[5,5],[-5,-5],[5,-5]]),[500,510,520,540])
    assert s([[0,0]])[0]==515  # shared SW-NE edge, not a smoothed 517.5 m.
    assert s([[-2.5,2.5]])[0]==507.5
    assert s([[2.5,-2.5]])[0]==527.5
    with pytest.raises(ValueError,match='Outside'):s([[5.1,0]])


def test_nodata_is_visible_and_duplicate_source_samples_are_rejected():
    a,transform=xyz_grid(np.array([[0,0,500],[5,0,501],[0,5,502]]))
    assert np.isnan(a[0,1])
    with pytest.raises(ValueError,match='Duplicate'):xyz_grid(np.array([[0,0,500],[5,0,501],[0,5,502],[0,0,500]]))
    s=field([[500,np.nan],[520,540]])
    with pytest.raises(ValueError,match='NoData'):s([[0,0]])


def test_grid_clipped_road_caps_match_native_terrain_without_spanning_cell_breaks():
    s=object.__new__(PlanarDTM);s.half=10;s.spacing=5;s.data=np.array([[500,501,504,507,508],[500,502,510,506,508],[500,501,503,506,508],[500,499,502,507,508],[500,501,505,507,508]],dtype=float)
    p=grid_boundary(Polygon([(-9.1,-8.7),(9.2,-8.7),(9.2,8.9),(-9.1,8.9)],holes=[[(-3,-3),(-3,3),(3,3),(3,-3)]]))
    m=grid_extrude(p,lambda xy:s(xy)-.13,lambda xy:s(xy)+.12,[60,60,60,255],[60,60,60,255])
    assert m.is_watertight and m.volume>0
    index=HeightIndex(m.triangles)
    xy=np.array([[-8,-8],[-8,2],[-2,-8],[8,8],[8,-2],[-5.5,5.5],[5.5,-5.5]])
    assert np.max(abs(index.heights(xy)-s(xy)-.12))<.0002
    assert np.isnan(index.heights([[0,0]])[0]),'A real footprint hole remains a hole'


def test_native_cap_narrow_diagonal_polygon_remains_closed():
    p=grid_boundary(Polygon([(-250,-122.115),(0,-150.551),(0,-154.125),(-250,-123.512)]))
    m=grid_extrude(p,lambda xy:530+xy[:,0]*.01,lambda xy:530.25+xy[:,0]*.01,[70,70,70,255],[70,70,70,255])
    assert m.is_watertight and abs(m.volume-p.area*.25)<.01


def test_portals_are_local_openings_not_whole_tunnel_corridor_excavations():
    class N:
        roads=[{'id':'tunnel','kind':'tunnel','line':LineString([(-100,0),(100,0)]),'width_m':4,'end_nodes':['a','b']}]
        distances={'tunnel':{'a':0.,'b':0.}}
        class S:
            half=120
            def __call__(self,xy):return np.full(len(xy),500.)
        surface=S()
        def z(self,xy,roads):
            t=np.clip((100-np.abs(np.asarray(xy)[:,0]))/45,0,1);return 500-6*t*t*(3-2*t)
    mask,details=portal_mask(N())
    assert mask.covers(Point(-98,0)) and not mask.covers(Point(0,0))
    assert 0<mask.area<200*4.7 and details


def test_structural_field_is_independent_of_cross_section_terrain_and_continuous():
    n=object.__new__(TerrainNetwork)
    n.surface=lambda xy:np.full(len(xy),500.);n.config={'road_lift_m':.12}
    roads=[{'id':'a','kind':'bridge','line':LineString([(-10,0),(10,0)])},{'id':'b','kind':'bridge','line':LineString([(-10,4),(10,4)])}]
    n.structure_profiles={r['id']:{'s':np.array([0,20]),'z':np.array([530,530])if r['id']=='a'else np.array([535,535])}for r in roads}
    z=n.z([[0,1.99],[0,2.01]],roads)
    assert abs(z[1]-z[0])<.05,'Nearest-road selection would create an artificial 5 m jump'
    assert n.z([[0,8]],roads[:1])[0]==530,'Deck cross section is a profile, not terrain following'


def test_source_descriptor_distinguishes_grid_spacing_from_accuracy_and_epoch():
    r=json.loads((Path(__file__).resolve().parents[1]/'manifests/geo004-sources.json').read_text())
    assert r['inegi_dtm']['horizontal_grid_m']==5
    assert r['inegi_dtm']['vertical_accuracy_epv_m']is None and r['inegi_dtm']['source_date_year']==2007
    assert r['inegi_dtm']['source_vertical_datum']=='NAVD88'and r['target_vertical_datum']=='EGM2008'
    assert len(r['grids'])==2 and all(g['sha256']and g['license']for g in r['grids'])


def test_nodata_neighbour_cannot_be_hidden_by_bilinear_normalization():
    from rasterio.transform import from_origin
    data=np.ones((4,4));data[1,1]=np.nan
    with pytest.raises(ValueError,match='NoData'):require_valid_stencil(data,from_origin(0,20,5,5),np.array([5.]),np.array([15.]))
    require_valid_stencil(np.ones((4,4)),from_origin(0,20,5,5),np.array([5.]),np.array([15.]))


def test_tunnel_envelope_keeps_deeper_clearance_anchor_instead_of_averaging_it_away():
    n=object.__new__(TerrainNetwork)
    n.surface=lambda xy:np.full(len(xy),520.);n.config={'road_lift_m':.12}
    roads=[{'id':'deep','kind':'tunnel','line':LineString([(-10,0),(10,0)])},
           {'id':'shallow','kind':'tunnel','line':LineString([(-10,2),(10,2)])}]
    n.structure_profiles={r['id']:{'s':np.array([0,20]),'z':np.array([500,500])if r['id']=='deep'else np.array([508,508])}for r in roads}
    assert n.z([[0,0]],roads)[0]==500,'A 500 m clearance anchor must not be averaged upward toward 508 m'
    assert abs(np.diff(n.z([[0,.99],[0,1.01]],roads)))[0]<.01

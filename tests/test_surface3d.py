import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from GeoPipeline.mesh import Surface, terrain_meshes


def test_surface_sampling_axes_bounds_and_terrain_preserves_vertices(tmp_path):
    rows, cols = np.mgrid[0:9, 0:9]
    heights = (500+2*cols+3*rows).astype('float32')
    path = tmp_path/'plane.tif'
    with rasterio.open(path,'w',driver='GTiff',width=9,height=9,count=1,dtype='float32',crs='EPSG:32614',transform=from_origin(0,90,10,10)) as dst:
        dst.write(heights,1)
    surface = Surface(path,{'extent_m':80,'sample_spacing_m':10})
    np.testing.assert_allclose(surface([[-40,40],[0,0],[10,0],[0,-10],[40,-40]]),[500,520,522,523,540])
    with pytest.raises(ValueError,match='outside'):surface([[40.1,0]])
    meshes = dict(terrain_meshes(surface,2))
    assert sum(len(m.faces) for m in meshes.values()) == 128
    assert all(np.all(m.face_normals[:,2]>0) for m in meshes.values())
    a,b = meshes['terrain_0_0'],meshes['terrain_1_0']
    edge_a = a.vertices[np.isclose(a.vertices[:,0],0)]
    edge_b = b.vertices[np.isclose(b.vertices[:,0],0)]
    np.testing.assert_array_equal(edge_a[np.argsort(edge_a[:,1])],edge_b[np.argsort(edge_b[:,1])])
    for m in meshes.values():np.testing.assert_allclose(m.vertices[:,2],surface(m.vertices[:,:2]))

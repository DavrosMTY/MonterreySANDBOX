import numpy as np
from GeoPipeline.geo001 import SIZE, center_utm, grid, quantize_for_unreal, synthetic_heights

def test_grid():
    left, top, spacing = grid(25.667,-100.310,2000)
    e,n = center_utm(25.667,-100.310)
    assert abs(left + 1000 - e) < 0.001
    assert abs(top - 1000 - n) < 0.001
    assert abs(spacing - 2000/504) < 1e-8

def test_quantization():
    a=synthetic_heights()
    b,h0,z,err = quantize_for_unreal(a)
    assert b.shape==(SIZE,SIZE)
    assert b.dtype==np.dtype('<u2')
    assert z>0 and err<0.01

def test_nan_rejected():
    a=np.zeros((SIZE,SIZE),dtype=np.float32)
    a[0,0]=np.nan
    try:quantize_for_unreal(a)
    except ValueError:pass
    else:assert False

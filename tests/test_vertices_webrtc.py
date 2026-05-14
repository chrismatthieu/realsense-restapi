"""Regression: full-depth vertex arrays must not use O(N) Python tolist in hot paths."""
import numpy as np
import pytest

from app.services.webrtc_manager import safe_len, vertices_to_json_list


def test_safe_len_large_numpy_no_hang():
    v = np.random.randn(480 * 640, 3).astype(np.float32)
    assert safe_len(v) == 480 * 640


def test_vertices_to_json_list_downsamples_large_cloud():
    v = np.random.randn(200_000, 3).astype(np.float32)
    out = vertices_to_json_list(v, max_vertices=3000)
    assert len(out) == 3000
    assert all(len(row) == 3 for row in out)
    assert all(isinstance(x, float) for row in out for x in row)


def test_vertices_to_json_list_small_list():
    out = vertices_to_json_list([[1, 2, 3], [4, 5, 6]], max_vertices=3000)
    assert out == [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]

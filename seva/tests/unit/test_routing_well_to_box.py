from seva.viewmodels.plate_vm import PlateVM
import pytest


@pytest.mark.parametrize(
    "wid,box",
    [
        ("A1", "A"),
        ("A10", "A"),
        ("B11", "B"),
        ("C21", "C"),
        ("D40", "D"),
    ],
)
def test_prefix_maps_box(wid, box):
    assert PlateVM.well_to_box(wid) == box


@pytest.mark.parametrize("wid", ["", "X1", "11", "a0"])
def test_invalid_prefix_raises(wid):
    with pytest.raises(ValueError):
        PlateVM.well_to_box(wid)

from types import SimpleNamespace
from package.utils.data_validator import PropertyDataValidator, ERR_MISSING_FLOOR


def test_mansion_specs_accepts_kenbiya_floor_field():
    item = SimpleNamespace(senyuMenseki=36.05, floor=4, floorStr="4階")
    reasons = []
    PropertyDataValidator._check_mansion_specs(item, reasons)
    assert ERR_MISSING_FLOOR not in reasons

import pytest
from package.models.smtrc import SmtrcInvestment
from package.utils.property_type_detector import PropertyTypeDetector
from package.utils.data_validator import PropertyDataValidator
from package.parser.baseParser import IncompatiblePropertyTypeException

def test_smtrc_investment_kaisu_field():
    item = SmtrcInvestment()
    assert hasattr(item, 'kaisu')
    item.kaisu = 5
    assert item.kaisu == 5

def test_property_type_detector_tsubo_area_extraction():
    val = '52.01㎡(15.73坪)'
    assert PropertyTypeDetector._is_positive_area_value(val) is True

def test_property_type_detector_land_url_priority():
    url = 'https://example.com/tochi/detail/12345'
    specs = {'土地面積': '100㎡'}
    detected = PropertyTypeDetector.detect(
        url=url,
        title='【建築条件付売地】新築戸建プランあり',
        specs=specs
    )
    assert detected == 'tochi'

def test_property_type_detector_specs_land_and_bldg_into_kodate():
    specs = {'土地面積': '100㎡', '建物面積': '80㎡'}
    detected = PropertyTypeDetector._detect_from_specs_rule(specs)
    assert detected == 'kodate'

def test_data_validator_underground_floor_allowed():
    assert PropertyDataValidator._has_located_floor('地下1階') is True

def test_data_validator_traffic_km_notation():
    class DummyItem:
        traffic = '最寄駅まで約4.8km'
    assert PropertyDataValidator._has_traffic_minutes(DummyItem()) is True

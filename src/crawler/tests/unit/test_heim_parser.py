from package.parser.heimParser import HeimMansionParser, HeimKodateParser, HeimTochiParser
from package.models.heim import HeimMansion, HeimKodate, HeimTochi


def test_heim_parser_creation():
    assert isinstance(HeimMansionParser().createEntity(), HeimMansion)
    assert isinstance(HeimKodateParser().createEntity(), HeimKodate)
    assert isinstance(HeimTochiParser().createEntity(), HeimTochi)

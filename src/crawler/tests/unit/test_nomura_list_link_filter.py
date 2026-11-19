from package.parser.nomuraParser import NomuraMansionParser


def test_nomura_normalize_property_list_href_excludes_area_urls():
    assert NomuraMansionParser._normalize_property_list_href("/pro/kubun/area/111/") == ""
    assert NomuraMansionParser._normalize_property_list_href("https://www.nomu.com/pro/kubun/area/271/") == ""
    assert NomuraMansionParser._normalize_property_list_href("/pro/bukken_local_id/12345/") == "https://www.nomu.com/pro/bukken_local_id/12345/"

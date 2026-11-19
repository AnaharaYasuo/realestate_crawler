from package.models.tokyu import TokyuKodate


def test_tokyu_kodate_setsumen_is_nullable():
    field = TokyuKodate._meta.get_field("setsumen")
    assert field.null is True
    assert field.blank is True

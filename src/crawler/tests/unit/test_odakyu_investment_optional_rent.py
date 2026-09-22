# -*- coding: utf-8 -*-
"""OdakyuInvestment: rent fields may be blank when listing lacks yield (Issue #317)."""
from package.models.odakyu import OdakyuInvestment


def test_odakyu_investment_rent_fields_are_blank_true():
    annual = OdakyuInvestment._meta.get_field("annualRent")
    monthly = OdakyuInvestment._meta.get_field("monthlyRent")
    assert annual.null is True and annual.blank is True
    assert monthly.null is True and monthly.blank is True


def test_odakyu_investment_rent_field_clean_allows_none():
    """IntegerField(null=True, blank=True) は None を clean 可能。"""
    annual = OdakyuInvestment._meta.get_field("annualRent")
    monthly = OdakyuInvestment._meta.get_field("monthlyRent")
    assert annual.clean(None, None) is None
    assert monthly.clean(None, None) is None

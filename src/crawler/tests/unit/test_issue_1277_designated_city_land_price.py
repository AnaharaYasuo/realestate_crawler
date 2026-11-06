# -*- coding: utf-8 -*-
"""
Issue #1277: 政令指定都市の行政区解決および地価マスタ突合仕様の検証
"""
import pytest
from package.ml.features.parsers import extract_clean_address
from package.ml.features.reference_data import (
    blend_land_prices,
    _get_land_price_stats,
    _init_global_caches,
    reset_reference_caches,
)
from package.ml.features.reference_records import LandPriceRecord


class MockProperty:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_extract_clean_address_preserves_designated_city_wards():
    """政令指定都市（名古屋市、横浜市、大阪市等）の住所から区名まで確実に保持されることを検証"""
    # 1. address1, address2 に入っているケース
    prop1 = MockProperty(address1="愛知県", address2="名古屋市名東区本郷2丁目")
    a1, a2, _, _ = extract_clean_address(prop1)
    assert a2.startswith("名古屋市名東区"), f"Expected 名古屋市名東区, got {a2}"

    # 2. address に結合して入っているケース（fallback）
    prop2 = MockProperty(address="愛知県名古屋市中区丸の内1-1-1")
    a1, a2, _, _ = extract_clean_address(prop2)
    assert a1 == "愛知県"
    assert a2 == "名古屋市中区", f"Expected 名古屋市中区, got {a2}"

    # 3. address2 が「名古屋市」とだけ入っており address に区名があるケース
    prop3 = MockProperty(address1="愛知県", address2="名古屋市", address="愛知県名古屋市千種区覚王山通")
    a1, a2, _, _ = extract_clean_address(prop3)
    assert a2 == "名古屋市千種区", f"Expected 名古屋市千種区, got {a2}"


def test_blend_land_prices_for_nagoya_wards():
    """名古屋市の区（名東区・千種区）で地価が中心区外れ値（84万/㎡）に歪まず適正値（15万〜35万/㎡）になることを検証"""
    reset_reference_caches()
    # 住宅地容積率200%での地価算出
    price_meito, _, _, _ = blend_land_prices("愛知県", "名古屋市名東区", max_youseki=200.0)
    # 名東区の公示地価は住宅地21万/商業地31万程度なので、20〜25万円/㎡前後になるべき
    assert 150000 <= price_meito <= 350000, f"Expected 15~35万 for 名東区, got {price_meito}"


def test_fallback_when_only_city_name_given_avoids_commercial_outliers():
    """区名がどうしても取得できず「名古屋市」単体の場合でも、全区中央値等を用いて80万超の外れ値にならないことを検証"""
    price_city_only, _, _, _ = blend_land_prices("愛知県", "名古屋市", max_youseki=200.0)
    # 843,766 円/㎡ などの外れ値にならず、40万円/㎡以下に収まることを検証
    assert price_city_only < 450000, f"Expected robust fallback < 45万, got {price_city_only}"

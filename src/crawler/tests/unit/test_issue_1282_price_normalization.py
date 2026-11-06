from package.ml.training.data_loader import normalize_training_price_man


def test_normalize_training_price_man():
    # 円単位 (100万円以上) -> 万円単位
    assert normalize_training_price_man(86800000, "8,680万円") == 8680.0
    assert normalize_training_price_man(115000000, "11,500万円") == 11500.0
    assert normalize_training_price_man(6800000, "680万円") == 680.0

    # 万円単位 (すでに万円単位で格納) -> そのまま保持
    assert normalize_training_price_man(5480, "5,480") == 5480.0
    assert normalize_training_price_man(3098, "3,098万円") == 3098.0
    assert normalize_training_price_man(60800, "60,800万円") == 60800.0
    assert normalize_training_price_man(130000, "130,000万円") == 130000.0

    # priceStr がない場合のフォールバック判定
    assert normalize_training_price_man(5480, None) == 5480.0
    assert normalize_training_price_man(86800000, None) == 8680.0

    # 無効値
    assert normalize_training_price_man(0, None) == 0.0
    assert normalize_training_price_man(None, None) == 0.0

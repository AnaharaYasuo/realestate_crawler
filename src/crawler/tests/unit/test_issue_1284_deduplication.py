import pandas as pd
from package.ml.training.cleaning import clean_training_data


def test_clean_training_data_deduplication():
    df = pd.DataFrame([
        {"price": 3000, "area": 60.0, "prefecture": "東京都", "city": "世田谷区", "chikunen": 10.0},
        {"price": 3000, "area": 60.0, "prefecture": "東京都", "city": "世田谷区", "chikunen": 10.0},  # 重複 (同一条件)
        {"price": 4000, "area": 70.0, "prefecture": "東京都", "city": "新宿区", "chikunen": 5.0},
    ])

    cleaned = clean_training_data(df, "mansion")
    assert len(cleaned) == 2
    assert (cleaned["price"] == 3000).sum() == 1
    assert (cleaned["price"] == 4000).sum() == 1


def test_clean_training_data_deduplication_without_pref():
    # prefecture/city 列がない場合でも price/area/chikunen だけで安全に動作
    df = pd.DataFrame([
        {"price": 3000, "area": 60.0, "chikunen": 10.0},
        {"price": 3000, "area": 60.0, "chikunen": 10.0},  # 重複
        {"price": 4000, "area": 70.0, "chikunen": 5.0},
    ])

    cleaned = clean_training_data(df, "kodate")
    assert len(cleaned) == 2

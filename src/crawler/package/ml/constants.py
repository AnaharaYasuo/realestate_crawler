"""ML パイプライン共通定数定義 (Issue #710, #714)"""

PROPERTY_TYPES: tuple[str, ...] = ("mansion", "kodate", "apartment", "tochi")
STAGES: tuple[str, ...] = ("first", "second")
ALGOS: tuple[str, ...] = ("lgb", "xgb", "cat", "rf")

COMPANIES = [
    "mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1",
    "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome",
    "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie",
    "heim", "sumirin", "keio", "kenbiya", "ietan", "haseko", "adcast", "toho",
    "reguide",
]

DEFAULT_ENSEMBLE_WEIGHTS: dict[str, dict[str, float]] = {
    "mansion": {"lgb": 0.35, "xgb": 0.35, "cat": 0.15, "rf": 0.15},
    "kodate": {"lgb": 0.35, "xgb": 0.45, "cat": 0.1, "rf": 0.1},
    "apartment": {"lgb": 0.35, "xgb": 0.45, "cat": 0.1, "rf": 0.1},
    "tochi": {"lgb": 0.3, "xgb": 0.25, "cat": 0.25, "rf": 0.2},
}

# PropertyEvaluation 等の DB 一括書き込み (bulk_create / bulk_update) の batch_size (原則 100)。
# ProxySQL 経由の接続断 (2013) / 接続タイムアウト (9001) を避けるため、書き込み系はこの定数を参照すること。
EVAL_DB_WRITE_BATCH_SIZE: int = 100

# 評価対象物件を DB から走査・取得し、ML 推論に渡す 1 チャンクの件数 (読み込み側)。
# 書き込み側 (EVAL_DB_WRITE_BATCH_SIZE) とは独立に調整する。
EVAL_DB_READ_CHUNK_SIZE: int = 1000

"""ML パイプライン共通定数定義 (Issue #710, #714)"""

PROPERTY_TYPES: tuple[str, ...] = ("mansion", "kodate", "apartment", "tochi")
STAGES: tuple[str, ...] = ("first", "second")
ALGOS: tuple[str, ...] = ("lgb", "xgb", "cat", "rf")

COMPANIES = [
    "mitsui", "sumifu", "tokyu", "nomura", "misawa", "smtrc", "sumai1",
    "mizuho", "odakyu", "afr", "sekisui", "daiwa", "totate", "athome",
    "homes", "seibu", "keikyu", "sotetsu", "keisei", "daikyo", "rearie",
    "heim", "sumirin", "keio",
]

DEFAULT_ENSEMBLE_WEIGHTS: dict[str, dict[str, float]] = {
    "mansion": {"lgb": 0.35, "xgb": 0.35, "cat": 0.15, "rf": 0.15},
    "kodate": {"lgb": 0.35, "xgb": 0.45, "cat": 0.1, "rf": 0.1},
    "apartment": {"lgb": 0.35, "xgb": 0.45, "cat": 0.1, "rf": 0.1},
    "tochi": {"lgb": 0.3, "xgb": 0.25, "cat": 0.25, "rf": 0.2},
}

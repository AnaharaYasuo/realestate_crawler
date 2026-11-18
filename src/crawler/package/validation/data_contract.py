"""Data quality contract and drift detection for crawled property batches."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class DataContractConfig:
    required_fields: tuple[str, ...] = ("price", "area_sqm", "station_name")
    min_fill_rate: float = 0.7
    max_outlier_ratio: float = 0.1
    max_unknown_station_ratio: float = 0.3


@dataclass(frozen=True)
class DataContractResult:
    passed: bool
    violations: list[str] = field(default_factory=list)


def validate_property_batch(records: list[dict], config: DataContractConfig) -> DataContractResult:
    """Validate fill-rate, outlier ratio, and unknown-station drift for a batch."""
    if not records:
        return DataContractResult(passed=False, violations=["empty_batch"])

    violations: list[str] = []
    n = len(records)

    for fname in config.required_fields:
        filled = sum(1 for r in records if r.get(fname) not in (None, ""))
        rate = filled / n
        if rate < config.min_fill_rate:
            violations.append(f"low_fill_rate:{fname}={rate:.2f}<{config.min_fill_rate}")

    outliers = sum(
        1
        for r in records
        if (r.get("price") is not None and r["price"] <= 0)
        or (r.get("area_sqm") is not None and r["area_sqm"] <= 0)
    )
    if (outliers / n) > config.max_outlier_ratio:
        violations.append(f"high_outlier_ratio:{outliers / n:.2f}>{config.max_outlier_ratio}")

    unknown_stations = sum(1 for r in records if not r.get("station_name"))
    if (unknown_stations / n) > config.max_unknown_station_ratio:
        violations.append(
            f"high_unknown_station_ratio:{unknown_stations / n:.2f}>{config.max_unknown_station_ratio}"
        )

    return DataContractResult(passed=len(violations) == 0, violations=violations)

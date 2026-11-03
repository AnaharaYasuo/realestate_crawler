"""
ML 参照マスタ軽量レコード定義 (Issue #717, Epic #710)
スロット化されたイミュータブルなデータクラスにより、Django ORM インスタンスの
内部状態や不要フィールドをメモリから完全に排除し常駐メモリを最小化する。
"""

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MunicipalRecord:
    prefecture: str
    city: str
    population_growth_rate: float
    average_income: int
    total_population: int | None
    income_growth_rate: float | None
    population_density: float | None


@dataclass(slots=True, frozen=True)
class LandPriceRecord:
    prefecture: str
    city: str
    average_land_price: int
    estimated_rosenka_price: int | None
    estimated_fixed_asset_price: int | None
    land_price_growth_rate: float | None
    land_use: str


@dataclass(slots=True, frozen=True)
class StationRecord:
    station_name: str
    passenger_volume: int


@dataclass(slots=True, frozen=True)
class HazardMapRecord:
    prefecture: str
    city: str
    flood_risk_level: int
    landslide_risk_level: int


@dataclass(slots=True, frozen=True)
class UrbanPlanningZoneRecord:
    zone_name: str
    max_kenpei: int
    max_youseki: int


@dataclass(slots=True, frozen=True)
class MacroEconomicRecord:
    year_month: str
    repi_mansion: float | None
    repi_kodate: float | None
    repi_tochi: float | None
    jgb_10y_yield: float | None
    nikkei_225: float | None
    tse_reit_index: float | None
    construction_cost_index: float | None


@dataclass(slots=True, frozen=True)
class MunicipalFutureRecord:
    prefecture: str
    city: str
    target_year: int
    projected_population: int
    pop_change_rate_from_2020: float
    working_age_ratio: float
    elderly_ratio: float
    projected_households: int | None
    single_household_ratio: float | None


@dataclass(slots=True, frozen=True)
class MunicipalYearlyRecord:
    prefecture: str
    city: str
    year: int
    total_population: int | None
    population_growth_rate: float
    average_income: int
    income_growth_rate: float | None
    income_3y_cagr: float | None
    population_density: float | None


@dataclass(slots=True, frozen=True)
class StationYearlyRecord:
    station_name: str
    railway_line: str
    year: int
    passenger_volume: int
    volume_yoy_growth: float | None
    volume_3y_cagr: float | None


@dataclass(slots=True, frozen=True)
class UrbanInductionZoneRecord:
    prefecture: str
    city: str
    town_name: str
    is_urban_induction_zone: bool
    is_residential_induction_zone: bool
    plan_status: str

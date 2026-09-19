# -*- coding: utf-8 -*-
"""
1物件1リクエスト完結型 AI属性抽出器 (SingleUnifiedPropertyExtractor)
クローリング時・バッチ評価時において、1物件につき厳格に最大1回のLLMリクエストで全観点を一括抽出する。
"""
import os
import re
import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

try:
    import google.generativeai as genai
except ImportError:
    genai = None


@dataclass
class PropertyOverview:
    price_man_yen: Optional[int] = None
    property_type: str = "mansion"
    transaction_type: Optional[str] = None
    occupancy_status: Optional[str] = None


@dataclass
class BuildingMasterAttributes:
    developer_brand: Optional[str] = None
    developer_tier: str = "unknown"
    contractor_name: Optional[str] = None
    contractor_tier: str = "unknown"
    structure_type: Optional[str] = None
    earthquake_resistance: Optional[str] = None
    total_units: Optional[int] = None
    elevator_available: Optional[bool] = None
    hallway_type: Optional[str] = None
    garbage_disposal_24h: Optional[bool] = None
    management_type: Optional[str] = None
    manager_working_style: Optional[str] = None
    shared_facilities: List[str] = field(default_factory=list)


@dataclass
class UnitSpecAttributes:
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    is_top_floor: Optional[bool] = None
    is_basement: Optional[bool] = None
    is_corner_unit: Optional[bool] = None
    main_orientation: Optional[str] = None
    has_disposer: Optional[bool] = None
    has_dishwasher: Optional[bool] = None
    has_floor_heating: Optional[bool] = None
    has_bath_dryer: Optional[bool] = None
    has_water_purifier: Optional[bool] = None
    renovation_status: str = "未実施"
    renovation_year_month: Optional[str] = None
    renovation_details: List[str] = field(default_factory=list)
    piping_replaced: Optional[bool] = None
    private_garden_area_m2: Optional[float] = None
    roof_balcony_area_m2: Optional[float] = None
    special_notes_psychological_defect: bool = False


@dataclass
class LandKodateAttributes:
    effective_land_area_m2: Optional[float] = None
    road_frontage_width_m: Optional[float] = None
    road_frontage_orientation: Optional[str] = None
    road_type: Optional[str] = None
    road_contact_type: Optional[str] = None
    setback_required_area_m2: Optional[float] = None
    private_road_burden_area_m2: Optional[float] = None
    effective_floor_area_ratio_percent: Optional[float] = None
    building_condition: Optional[str] = None
    land_delivery_condition: Optional[str] = None
    house_builder_type: Optional[str] = None


@dataclass
class RightsEconomicAttributes:
    land_rights_type: str = "所有権"
    ground_rent_monthly_yen: Optional[int] = None
    lease_expiry_year_month: Optional[str] = None
    management_fee_monthly_yen: Optional[int] = None
    repair_reserve_fund_monthly_yen: Optional[int] = None
    other_monthly_expenses_yen: Optional[int] = None
    other_expenses_breakdown: Optional[str] = None


@dataclass
class VisualAttributes:
    layout_outframe_score: Optional[float] = 3.5
    layout_efficiency_score: Optional[float] = 3.5
    has_service_room: Optional[bool] = False
    exterior_luxury_score: Optional[float] = 3.5
    exterior_deterioration_risk: Optional[bool] = False
    interior_grade_score: Optional[float] = 3.5
    is_fully_renovated_appearance: Optional[bool] = False
    view_blockage_severity: str = "none"
    view_scenic_premium: bool = False
    retaining_wall_risk: bool = False
    overall_visual_adjustment_percent: float = 0.0


@dataclass
class UnifiedPropertyAttributes:
    property_overview: PropertyOverview = field(default_factory=PropertyOverview)
    building_master: BuildingMasterAttributes = field(default_factory=BuildingMasterAttributes)
    unit_specs: UnitSpecAttributes = field(default_factory=UnitSpecAttributes)
    land_kodate_specs: LandKodateAttributes = field(default_factory=LandKodateAttributes)
    rights_economic_conditions: RightsEconomicAttributes = field(default_factory=RightsEconomicAttributes)
    visual_features: VisualAttributes = field(default_factory=VisualAttributes)



PROMPT_TEMPLATE = """あなたは不動産鑑定評価および機械学習価格推定の専門データエンジニアです。
入力された1件の物件データから、価格推定に必要な全属性・スペック・リスク要因を漏れなく抽出し、
指定のJSON形式のみを出力してください。架空の情報は作らず、記載がない項目は null または false としてください。

【物件生テキスト】
タイトル: {title}
サイト/種別: {site} / {property_type}
価格表記: {price_str}
スペック辞書: {specs_json}
特徴タグ: {features_json}
アピール文章: {appeals_json}
抽出スニペット: {snippets_json}

【出力JSONフォーマット】
{{
  "property_overview": {{
    "price_man_yen": int or null,
    "property_type": "mansion" | "kodate" | "tochi" | "investment",
    "transaction_type": string or null,
    "occupancy_status": string or null
  }},
  "building_master": {{
    "developer_brand": string or null,
    "developer_tier": "major_reputable" | "standard" | "unknown",
    "contractor_name": string or null,
    "contractor_tier": "super_general" | "major" | "local" | "unknown",
    "structure_type": string or null,
    "earthquake_resistance": "免震" | "制震" | "耐震" | null,
    "total_units": int or null,
    "elevator_available": bool or null,
    "hallway_type": "内廊下" | "外廊下" | null,
    "garbage_disposal_24h": bool or null,
    "management_type": "全部委託" | "一部委託" | "自主管理" | null,
    "manager_working_style": "常駐" | "日勤" | "巡回" | "管理員なし" | null,
    "shared_facilities": [string]
  }},
  "unit_specs": {{
    "floor_number": int or null,
    "total_floors": int or null,
    "is_top_floor": bool or null,
    "is_basement": bool or null,
    "is_corner_unit": bool or null,
    "main_orientation": string or null,
    "has_disposer": bool or null,
    "has_dishwasher": bool or null,
    "has_floor_heating": bool or null,
    "has_bath_dryer": bool or null,
    "has_water_purifier": bool or null,
    "renovation_status": "未実施" | "一部リフォーム" | "フルリノベーション" | "予定",
    "renovation_year_month": string or null,
    "renovation_details": [string],
    "piping_replaced": bool or null,
    "private_garden_area_m2": float or null,
    "roof_balcony_area_m2": float or null,
    "special_notes_psychological_defect": bool
  }},
  "land_kodate_specs": {{
    "effective_land_area_m2": float or null,
    "road_frontage_width_m": float or null,
    "road_frontage_orientation": string or null,
    "road_type": "公道" | "私道" | null,
    "road_contact_type": "一方" | "角地" | "両面道路" | "路地状(旗竿地)" | null,
    "setback_required_area_m2": float or null,
    "private_road_burden_area_m2": float or null,
    "effective_floor_area_ratio_percent": float or null,
    "building_condition": "無" | "有" | null,
    "land_delivery_condition": "更地渡し" | "古家あり現況渡し" | "権利床渡し" | null,
    "house_builder_type": "注文住宅" | "ハウスメーカー" | "建売" | null
  }},
  "rights_economic_conditions": {{
    "land_rights_type": "所有権" | "旧法借地権" | "普通借地権" | "定期借地権",
    "ground_rent_monthly_yen": int or null,
    "lease_expiry_year_month": string or null,
    "management_fee_monthly_yen": int or null,
    "repair_reserve_fund_monthly_yen": int or null,
    "other_monthly_expenses_yen": int or null,
    "other_expenses_breakdown": string or null
  }},
  "visual_features": {{
    "layout_outframe_score": float or 3.5,
    "layout_efficiency_score": float or 3.5,
    "has_service_room": bool,
    "exterior_luxury_score": float or 3.5,
    "exterior_deterioration_risk": bool,
    "interior_grade_score": float or 3.5,
    "is_fully_renovated_appearance": bool,
    "view_blockage_severity": "none" | "slight" | "severe",
    "view_scenic_premium": bool,
    "retaining_wall_risk": bool,
    "overall_visual_adjustment_percent": float
  }}
}}
"""


class SingleUnifiedPropertyExtractor:
    """1物件1リクエスト完結型属性抽出器（テキスト・画像マルチモーダル一括対応）"""

    def __init__(self, model_name: str = "gemini-1.5-flash"):
        self.model_name = model_name

    def _get_generative_model(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or not genai:
            return None
        genai.configure(api_key=api_key)
        return genai.GenerativeModel(self.model_name)

    def extract(self, prop_data: Dict[str, Any]) -> UnifiedPropertyAttributes:
        """
        1件の物件データから全観点を1回のリクエストで一括抽出。
        画像リストが同梱されている場合も、画像群とプロンプトをまとめて1回で呼出。
        """
        # ルールベースの初期フォールバックを生成
        fallback_res = self._rule_based_fallback(prop_data)

        model = self._get_generative_model()
        if not model:
            # APIキー未設定時はルールベースで返す
            return fallback_res

        # 1物件1リクエスト用プロンプトの構築
        prompt = PROMPT_TEMPLATE.format(
            title=prop_data.get("title", ""),
            site=prop_data.get("site", ""),
            property_type=prop_data.get("property_type", "mansion"),
            price_str=prop_data.get("price_str", ""),
            specs_json=json.dumps(prop_data.get("specs", {}), ensure_ascii=False),
            features_json=json.dumps(prop_data.get("features", []), ensure_ascii=False),
            appeals_json=json.dumps(prop_data.get("appeals", []), ensure_ascii=False),
            snippets_json=json.dumps(prop_data.get("snippets", []), ensure_ascii=False),
        )

        try:
            # 【厳格遵守】画像がある場合も一括同梱し、1物件につき厳格に1回のみ呼出
            images = prop_data.get("images") or []
            if images:
                content_payload = list(images) + [prompt]
            else:
                content_payload = prompt

            response = model.generate_content(content_payload)
            raw_text = response.text.strip() if hasattr(response, "text") else ""
            
            # Markdown コードブロックの除去
            cleaned_json = re.sub(r"^```json\s*", "", raw_text)
            cleaned_json = re.sub(r"\s*```$", "", cleaned_json)

            data = json.loads(cleaned_json)
            return self._dict_to_attributes(data, fallback_res)
        except Exception as e:
            logging.warning(f"SingleUnifiedPropertyExtractor: LLM call or parse failed: {e}. Using fallback.")
            return fallback_res


    def _rule_based_fallback(self, prop_data: Dict[str, Any]) -> UnifiedPropertyAttributes:
        """API未設定・失敗時のルールベース高速抽出"""
        all_text = " ".join([
            prop_data.get("title", ""),
            str(prop_data.get("specs", {})),
            " ".join(prop_data.get("features", [])),
            " ".join(prop_data.get("appeals", [])),
            " ".join(prop_data.get("snippets", []))
        ])

        # 価格の簡易抽出
        price_man = None
        price_str = prop_data.get("price_str", "") or prop_data.get("specs", {}).get("価格", "")
        price_match = re.search(r'([0-9,]+(?:\.[0-9]+)?)\s*万円', price_str.replace(",", ""))
        if price_match:
            try:
                price_man = int(float(price_match.group(1)))
            except ValueError:
                pass

        ev = True if re.search(r'エレベーター|EV', all_text) else None
        corner = True if re.search(r'角部屋|角住戸|２面採光|3面採光', all_text) else None
        disposer = True if re.search(r'ディスポーザー', all_text) else None
        dish = True if re.search(r'食洗|食器洗', all_text) else None
        floor_heat = True if re.search(r'床暖房', all_text) else None
        hallway = "内廊下" if "内廊下" in all_text else ("外廊下" if "外廊下" in all_text else None)
        defect = True if "告知事項" in all_text or "心理的瑕疵" in all_text else False

        # 借地権判定
        rights = "所有権"
        if "借地権" in all_text:
            rights = "定期借地権" if "定期" in all_text else "旧法借地権"

        return UnifiedPropertyAttributes(
            property_overview=PropertyOverview(
                price_man_yen=price_man,
                property_type=prop_data.get("property_type", "mansion")
            ),
            building_master=BuildingMasterAttributes(
                elevator_available=ev,
                hallway_type=hallway
            ),
            unit_specs=UnitSpecAttributes(
                is_corner_unit=corner,
                has_disposer=disposer,
                has_dishwasher=dish,
                has_floor_heating=floor_heat,
                special_notes_psychological_defect=defect
            ),
            land_kodate_specs=LandKodateAttributes(),
            rights_economic_conditions=RightsEconomicAttributes(
                land_rights_type=rights
            )
        )

    def _dict_to_attributes(self, data: dict, fallback: UnifiedPropertyAttributes) -> UnifiedPropertyAttributes:
        """JSON辞書をデータクラスにマッピング"""
        overview_dict = data.get("property_overview", {})
        bld_dict = data.get("building_master", {})
        unit_dict = data.get("unit_specs", {})
        land_dict = data.get("land_kodate_specs", {})
        rights_dict = data.get("rights_economic_conditions", {})

        overview = PropertyOverview(
            price_man_yen=overview_dict.get("price_man_yen") or fallback.property_overview.price_man_yen,
            property_type=overview_dict.get("property_type") or fallback.property_overview.property_type,
            transaction_type=overview_dict.get("transaction_type"),
            occupancy_status=overview_dict.get("occupancy_status")
        )

        building = BuildingMasterAttributes(
            developer_brand=bld_dict.get("developer_brand"),
            developer_tier=bld_dict.get("developer_tier", "unknown"),
            contractor_name=bld_dict.get("contractor_name"),
            contractor_tier=bld_dict.get("contractor_tier", "unknown"),
            structure_type=bld_dict.get("structure_type"),
            earthquake_resistance=bld_dict.get("earthquake_resistance"),
            total_units=bld_dict.get("total_units"),
            elevator_available=bld_dict.get("elevator_available", fallback.building_master.elevator_available),
            hallway_type=bld_dict.get("hallway_type", fallback.building_master.hallway_type),
            garbage_disposal_24h=bld_dict.get("garbage_disposal_24h"),
            management_type=bld_dict.get("management_type"),
            manager_working_style=bld_dict.get("manager_working_style"),
            shared_facilities=bld_dict.get("shared_facilities", [])
        )

        unit = UnitSpecAttributes(
            floor_number=unit_dict.get("floor_number"),
            total_floors=unit_dict.get("total_floors"),
            is_top_floor=unit_dict.get("is_top_floor"),
            is_basement=unit_dict.get("is_basement"),
            is_corner_unit=unit_dict.get("is_corner_unit", fallback.unit_specs.is_corner_unit),
            main_orientation=unit_dict.get("main_orientation"),
            has_disposer=unit_dict.get("has_disposer", fallback.unit_specs.has_disposer),
            has_dishwasher=unit_dict.get("has_dishwasher", fallback.unit_specs.has_dishwasher),
            has_floor_heating=unit_dict.get("has_floor_heating", fallback.unit_specs.has_floor_heating),
            has_bath_dryer=unit_dict.get("has_bath_dryer"),
            has_water_purifier=unit_dict.get("has_water_purifier"),
            renovation_status=unit_dict.get("renovation_status", "未実施"),
            renovation_year_month=unit_dict.get("renovation_year_month"),
            renovation_details=unit_dict.get("renovation_details", []),
            piping_replaced=unit_dict.get("piping_replaced"),
            private_garden_area_m2=unit_dict.get("private_garden_area_m2"),
            roof_balcony_area_m2=unit_dict.get("roof_balcony_area_m2"),
            special_notes_psychological_defect=unit_dict.get("special_notes_psychological_defect", fallback.unit_specs.special_notes_psychological_defect)
        )

        land = LandKodateAttributes(
            effective_land_area_m2=land_dict.get("effective_land_area_m2"),
            road_frontage_width_m=land_dict.get("road_frontage_width_m"),
            road_frontage_orientation=land_dict.get("road_frontage_orientation"),
            road_type=land_dict.get("road_type"),
            road_contact_type=land_dict.get("road_contact_type"),
            setback_required_area_m2=land_dict.get("setback_required_area_m2"),
            private_road_burden_area_m2=land_dict.get("private_road_burden_area_m2"),
            effective_floor_area_ratio_percent=land_dict.get("effective_floor_area_ratio_percent"),
            building_condition=land_dict.get("building_condition"),
            land_delivery_condition=land_dict.get("land_delivery_condition"),
            house_builder_type=land_dict.get("house_builder_type")
        )

        rights = RightsEconomicAttributes(
            land_rights_type=rights_dict.get("land_rights_type", fallback.rights_economic_conditions.land_rights_type),
            ground_rent_monthly_yen=rights_dict.get("ground_rent_monthly_yen"),
            lease_expiry_year_month=rights_dict.get("lease_expiry_year_month"),
            management_fee_monthly_yen=rights_dict.get("management_fee_monthly_yen"),
            repair_reserve_fund_monthly_yen=rights_dict.get("repair_reserve_fund_monthly_yen"),
            other_monthly_expenses_yen=rights_dict.get("other_monthly_expenses_yen"),
            other_expenses_breakdown=rights_dict.get("other_expenses_breakdown")
        )

        visual_dict = data.get("visual_features", {})
        visual = VisualAttributes(
            layout_outframe_score=visual_dict.get("layout_outframe_score", 3.5),
            layout_efficiency_score=visual_dict.get("layout_efficiency_score", 3.5),
            has_service_room=visual_dict.get("has_service_room", False),
            exterior_luxury_score=visual_dict.get("exterior_luxury_score", 3.5),
            exterior_deterioration_risk=visual_dict.get("exterior_deterioration_risk", False),
            interior_grade_score=visual_dict.get("interior_grade_score", 3.5),
            is_fully_renovated_appearance=visual_dict.get("is_fully_renovated_appearance", False),
            view_blockage_severity=visual_dict.get("view_blockage_severity", "none"),
            view_scenic_premium=visual_dict.get("view_scenic_premium", False),
            retaining_wall_risk=visual_dict.get("retaining_wall_risk", False),
            overall_visual_adjustment_percent=visual_dict.get("overall_visual_adjustment_percent", 0.0)
        )

        return UnifiedPropertyAttributes(
            property_overview=overview,
            building_master=building,
            unit_specs=unit,
            land_kodate_specs=land,
            rights_economic_conditions=rights,
            visual_features=visual
        )


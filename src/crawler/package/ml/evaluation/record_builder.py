"""
評価レコード生成およびプロ目線テキストリスク抽出モジュール (Issue #716)
"""

from decimal import Decimal
from typing import Any

from package.ml.constants import COMPANIES
from package.ml.investment_evaluator import evaluate_investment_property
from package.models.evaluation import PropertyEvaluation
from package.utils.converter import parse_chidai
from package.utils.deduplication import find_duplicate_property
from package.utils.text_risk_analyzer import analyze_text_risks


def resolve_company_and_type(model_name: str) -> tuple[str, str]:
    """モデル名から会社名と物件種別を判定する"""
    company = "unknown"
    for c in COMPANIES:
        if model_name.lower().startswith(c):
            company = c
            break
    property_type = model_name.lower().replace(company, "")
    return company, property_type


def extract_land_rent_and_liability(item: Any) -> tuple[int | None, Decimal | None]:
    """物件から地代および借地権負担（債務控除額）を算出する"""
    chidai_val = getattr(item, "chidai", None)
    if chidai_val is None and getattr(item, "chidaiStr", None):
        chidai_val = parse_chidai(item.chidaiStr)
    monthly_rent = int(chidai_val) if chidai_val and int(chidai_val) > 0 else None
    liability = Decimal(int((monthly_rent * 12.0) / 10000.0 / 0.05)) if monthly_rent else None
    return monthly_rent, liability


def populate_text_risks(evaluation_record: Any, item: Any) -> None:
    """物件テキストからプロ目線リスクフラグを抽出し評価レコードに反映する"""
    full_text = " ".join(filter(None, [
        getattr(item, "propertyName", ""),
        getattr(item, "address", ""),
        getattr(item, "traffic", ""),
        getattr(item, "biko", ""),
        getattr(item, "tochikenri", ""),
        getattr(item, "genkyo", ""),
        getattr(item, "torihiki", ""),
        getattr(item, "setsubi", ""),
    ]))
    chikunengetsu = getattr(item, "chikunengetsu", None)
    if chikunengetsu:
        chikunengetsu_str = chikunengetsu.strftime("%Y年%m月") if hasattr(chikunengetsu, "strftime") else str(chikunengetsu)
    else:
        chikunengetsu_str = getattr(item, "chikunengetsuStr", None)
    kaisu_str = getattr(item, "kaisu", None) or getattr(item, "shozaikai", None)
    total_floors = getattr(item, "chijoKaisu", None) or getattr(item, "totalFloors", None)
    parsed_total_floors = None
    if total_floors is not None:
        try:
            parsed_total_floors = int(str(total_floors).replace("階", "").strip())
        except ValueError:
            parsed_total_floors = None
    risks = analyze_text_risks(
        full_text,
        chikunengetsu_str=chikunengetsu_str,
        kaisu_str=str(kaisu_str) if kaisu_str is not None else None,
        total_floors=parsed_total_floors,
    )
    for k, v in risks.items():
        setattr(evaluation_record, k, v)


def build_or_update_eval_record(
    item: Any,
    price_stage1: float,
    existing: Any,
    company: str,
    property_type: str,
) -> tuple[Any, bool]:
    """単一物件の評価レコードを生成または更新する"""
    page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
    asking_price = (float(item.price) / 10000.0) if getattr(item, "price", None) else 0.0
    is_passed = bool(price_stage1 > 0 and asking_price > 0 and price_stage1 >= asking_price)

    monthly_rent, liability = extract_land_rent_and_liability(item)

    if existing and existing.pk:
        rec = existing
        rec.company = company
        rec.property_type = property_type
        rec.property_id = item.id
        rec.first_stage_predicted_price = price_stage1
        rec.is_first_stage_passed = is_passed
        rec.analysis_status = "pending"
        rec.monthly_land_rent = monthly_rent
        rec.land_rent_liability = liability
        populate_text_risks(rec, item)
        is_new = False
    else:
        rec = PropertyEvaluation(
            property_url=page_url,
            company=company,
            property_type=property_type,
            property_id=item.id,
            first_stage_predicted_price=price_stage1,
            is_first_stage_passed=is_passed,
            analysis_status="pending",
            monthly_land_rent=monthly_rent,
            land_rent_liability=liability,
        )
        populate_text_risks(rec, item)
        is_new = True

    if is_passed and not rec.duplicate_of_id:
        dup = find_duplicate_property(rec, new_prop=item)
        if dup:
            rec.duplicate_of = dup
            rec.is_slack_notified = True

    if "investment" in property_type or "invest" in property_type:
        rec = evaluate_investment_property(item, rec)

    return rec, is_new

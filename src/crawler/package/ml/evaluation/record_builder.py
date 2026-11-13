"""
評価レコード生成およびプロ目線テキストリスク抽出モジュール (Issue #716)
"""

from decimal import Decimal
from typing import Any

from django.utils import timezone
from package.ml.constants import COMPANIES
from package.ml.dcf_valuation import evaluate_dcf_and_yields
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
    liability = (
        Decimal(int((monthly_rent * 12.0) / 10000.0 / 0.05)) if monthly_rent else None
    )
    return monthly_rent, liability


def populate_text_risks(evaluation_record: Any, item: Any) -> None:
    """物件テキストからプロ目線リスクフラグを抽出し評価レコードに反映する"""
    full_text = " ".join(
        filter(
            None,
            [
                getattr(item, "propertyName", ""),
                getattr(item, "address", ""),
                getattr(item, "traffic", ""),
                getattr(item, "biko", ""),
                getattr(item, "tochikenri", ""),
                getattr(item, "genkyo", ""),
                getattr(item, "torihiki", ""),
                getattr(item, "setsubi", ""),
            ],
        )
    )
    chikunengetsu = getattr(item, "chikunengetsu", None)
    if chikunengetsu:
        chikunengetsu_str = (
            chikunengetsu.strftime("%Y年%m月")
            if hasattr(chikunengetsu, "strftime")
            else str(chikunengetsu)
        )
    else:
        chikunengetsu_str = getattr(item, "chikunengetsuStr", None)
    kaisu_str = getattr(item, "kaisu", None) or getattr(item, "shozaikai", None)
    total_floors = getattr(item, "chijoKaisu", None) or getattr(
        item, "totalFloors", None
    )
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


def _resolve_p10_and_uncertainty(
    price_stage1: float, p10_stage1: float | None
) -> tuple[Decimal | None, float | None]:
    if p10_stage1 is None or p10_stage1 <= 0.0 or price_stage1 <= 0.0:
        return None, None
    bounded = min(float(price_stage1), float(p10_stage1))
    unc = round(
        max(0.0, min(0.9999, (float(price_stage1) - bounded) / float(price_stage1))), 4
    )
    return Decimal(round(bounded)), unc


def _extract_current_dup_id(rec: Any) -> Any:
    """DB遅延クエリを発火させずに現在の duplicate_of_id を取得する"""
    inst_dict = getattr(rec, "__dict__", None)
    if isinstance(inst_dict, dict):
        dup_obj = inst_dict.get("duplicate_of")
        if dup_obj is not None and getattr(dup_obj, "id", None) is not None:
            return dup_obj.id
    return getattr(rec, "duplicate_of_id", None)


def _check_first_stage_passed(
    asking_price: float, price_stage1: float, p10_dec: Decimal | None
) -> bool:
    """Issue #1399: 下限予測価格P10での予測精度が高いため一次スクリーニング判定基準をP10基準に変更"""
    benchmark_price = (
        float(p10_dec) if p10_dec is not None and p10_dec > 0 else float(price_stage1)
    )
    return bool(
        benchmark_price > 0 and asking_price > 0 and benchmark_price >= asking_price
    )


def build_or_update_eval_record(
    item: Any,
    price_stage1: float,
    existing: Any,
    company: str,
    property_type: str,
    candidate_pool: list[Any] | None = None,
    skip_duplicate_check: bool = False,
    p10_stage1: float | None = None,
) -> tuple[Any, bool]:
    """単一物件の評価レコードを生成または更新する"""
    page_url = getattr(item, "pageUrl", None) or getattr(item, "url", None)
    asking_price = (
        (float(item.price) / 10000.0) if getattr(item, "price", None) else 0.0
    )

    monthly_rent, liability = extract_land_rent_and_liability(item)
    p10_dec, unc_ratio = _resolve_p10_and_uncertainty(price_stage1, p10_stage1)
    is_passed = _check_first_stage_passed(asking_price, price_stage1, p10_dec)

    prev_dup_id = None
    prev_identity = None
    if existing and existing.pk:
        prev_dup_id = getattr(existing, "duplicate_of_id", None)
        prev_identity = (
            getattr(existing, "company", None),
            getattr(existing, "property_type", None),
            getattr(existing, "property_id", None),
        )
        rec = existing
        rec.company = company
        rec.property_type = property_type
        rec.property_id = item.id
        rec.first_stage_predicted_price = price_stage1
        rec.first_stage_p10_price = p10_dec
        rec.prediction_uncertainty_ratio = unc_ratio
        rec.is_first_stage_passed = is_passed
        rec.analysis_status = "pending"
        rec.analyzed_at = timezone.now()
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
            first_stage_p10_price=p10_dec,
            prediction_uncertainty_ratio=unc_ratio,
            is_first_stage_passed=is_passed,
            analysis_status="pending",
            analyzed_at=timezone.now(),
            monthly_land_rent=monthly_rent,
            land_rent_liability=liability,
        )
        populate_text_risks(rec, item)
        is_new = True

    if not skip_duplicate_check and is_passed and not rec.duplicate_of_id:
        dup = find_duplicate_property(rec, new_prop=item, candidate_pool=candidate_pool)
        if dup:
            rec.duplicate_of = dup
            rec.is_slack_notified = True

    if "investment" in property_type or "invest" in property_type:
        rec = evaluate_investment_property(item, rec)

    int_score = float(getattr(rec, "interior_score", None) or 3.0)
    lay_score = float(getattr(rec, "layout_score", None) or 3.0)
    dcf_res = evaluate_dcf_and_yields(
        item, property_type, interior_score=int_score, layout_score=lay_score
    )
    rec.expected_gross_yield = Decimal(f"{dcf_res.expected_gross_yield:.2f}")
    rec.expected_net_yield = Decimal(f"{dcf_res.expected_net_yield:.2f}")
    rec.estimated_annual_rent = dcf_res.estimated_annual_rent
    rec.dcf_theoretical_price = dcf_res.dcf_theoretical_price

    if not is_new:
        rec._duplicate_of_changed = bool(_extract_current_dup_id(rec) != prev_dup_id)
        rec._identity_changed = bool(
            (rec.company, rec.property_type, rec.property_id) != prev_identity
        )

    return rec, is_new

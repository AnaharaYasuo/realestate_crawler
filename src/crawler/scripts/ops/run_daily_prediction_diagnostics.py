# ruff: noqa: E402
# -*- coding: utf-8 -*-
"""
日次価格推定精度診断スクリプト (Daily Prediction Diagnostics)

docs/internal_design/ml_prediction_diagnostics_policy.md に基づき、
最新の物件評価（PropertyEvaluation）と実際の販売価格のズレを日次で分析・可視化し、
ワースト乖離物件の自動原因タギングおよびSlackレポートを行います。
"""
import os
import sys
import re
import json
import datetime
import argparse
import logging
import asyncio
import numpy as np
import pandas as pd

# Django 設定のロード
_scripts_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_crawler_dir = os.path.dirname(_scripts_dir)
if _crawler_dir not in sys.path:
    sys.path.insert(0, _crawler_dir)

import realestateSettings
realestateSettings.configure()

from django.apps import apps
from package.models.evaluation import PropertyEvaluation
from package.utils.slack import send_slack_message, send_dev_report

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def calculate_metrics(y_true, y_pred) -> dict:
    """
    価格推定の精度指標（MdAPE, MAPE, RMSE, Hit Rate）を計算する。
    金額単位は万円を想定。
    """
    y_true = np.array(y_true, dtype=np.float64)
    y_pred = np.array(y_pred, dtype=np.float64)

    # ゼロ除算および異常値除外
    valid_mask = (y_true > 0) & (y_pred > 0) & np.isfinite(y_true) & np.isfinite(y_pred)
    y_t = y_true[valid_mask]
    y_p = y_pred[valid_mask]

    n_samples = len(y_t)
    if n_samples == 0:
        return {
            "count": 0,
            "mdape": 0.0,
            "mape": 0.0,
            "rmse": 0.0,
            "hit_rate_10": 0.0,
            "hit_rate_20": 0.0
        }

    abs_percent_errors = np.abs((y_p - y_t) / y_t) * 100.0
    mdape = float(np.median(abs_percent_errors))
    mape = float(np.mean(abs_percent_errors))
    rmse = float(np.sqrt(np.mean((y_p - y_t) ** 2)))

    hit_10 = float(np.mean(abs_percent_errors <= 10.0) * 100.0)
    hit_20 = float(np.mean(abs_percent_errors <= 20.0) * 100.0)

    return {
        "count": int(n_samples),
        "mdape": round(mdape, 2),
        "mape": round(mape, 2),
        "rmse": round(rmse, 2),
        "hit_rate_10": round(hit_10, 2),
        "hit_rate_20": round(hit_20, 2)
    }


def _classify_over_prediction(text: str, features: dict) -> list:
    causes = []
    if re.search(r"借地|地上権|定期借地|地代", text):
        causes.append("leasehold")
    if re.search(r"再建築不可|市街化調整|建築不可|セットバック要", text):
        causes.append("unbuildable")
    if re.search(r"告知事項|心理的瑕疵|事故|特別募集", text):
        causes.append("hazard_stigma")

    maguchi = float(features.get("maguchi") or 0.0)
    road_width = float(features.get("roadWidth") or features.get("road_width") or 0.0)
    if 0 < maguchi < 2.0 or 0 < road_width < 4.0:
        causes.append("shape_penalty")

    if not causes:
        causes.append("unclassified_over")
    return causes


def _classify_under_prediction(text: str, features: dict) -> list:
    causes = []
    if re.search(r"リノベ|リフォーム|内装一新|水回り新|改装済", text):
        causes.append("renovated")

    floor = int(features.get("floor_number") or features.get("floor") or 0)
    total_floors = int(features.get("total_floors") or 0)
    if total_floors >= 20 or (floor > 0 and floor == total_floors) or re.search(r"タワー|最上階|角部屋|ルーフバルコニー", text):
        causes.append("premium_tower")

    if not causes:
        causes.append("unclassified_under")
    return causes


def classify_error_cause(error_ratio: float, text: str = "", ptype: str = "", features: dict | None = None) -> list:
    """
    乖離率および物件テキスト・属性から、ズレの主要因を自動推定（タギング）する。
    error_ratio = (predicted - actual) / actual
    """
    _ = ptype
    text = text or ""
    features = features or {}

    if error_ratio >= 0.20:
        return _classify_over_prediction(text, features)
    elif error_ratio <= -0.20:
        return _classify_under_prediction(text, features)
    return ["within_tolerance"]


def _generate_rule_based_insight(worst_items: list) -> str:
    over_causes = []
    under_causes = []
    for it in worst_items:
        if it.get("type") == "over_prediction":
            over_causes.extend(it.get("causes", []))
        else:
            under_causes.extend(it.get("causes", []))

    from collections import Counter
    over_cnt = Counter(over_causes)
    under_cnt = Counter(under_causes)

    lines = [
        "【ルールベース診断サマリー】",
        f"- 過大評価の主要因: {', '.join([f'{k}({v}件)' for k, v in over_cnt.most_common(3)]) or '特記事項なし'}",
        f"- 過小評価の主要因: {', '.join([f'{k}({v}件)' for k, v in under_cnt.most_common(3)]) or '特記事項なし'}",
        "- 推奨アクション: 借地権・再建築不可・フルリノベのテキスト抽出パーサー強化および価格単位の検証を実施してください。"
    ]
    return "\n".join(lines)


def _generate_gemini_insight(worst_items: list, api_key: str):
    if not genai:
        return None
    try:
        http_options = types.HttpOptions(timeout=10000) if types else None
        with genai.Client(api_key=api_key, http_options=http_options) as client:
            sample_texts = []
            for i, item in enumerate(worst_items[:6], 1):
                direction = "過大評価 (推論 > 実売出)" if item.get("type") == "over_prediction" else "過小評価 (推論 < 実売出)"
                sample_texts.append(
                    f"【物件{i}】種別: {item.get('property_type')}, 方向: {direction}, "
                    f"実売出: {item.get('actual_price_man')}万円, 推論: {item.get('predicted_price_man')}万円, "
                    f"乖離率: {item.get('error_percent')}, 自動判定タグ: {', '.join(item.get('causes', []))}\n"
                    f"物件概要・テキスト: {item.get('text', '')[:200]}"
                )

            prompt = (
                "あなたは不動産鑑定士および機械学習データエンジニアです。以下の価格推定乖離ワースト物件を分析し、\n"
                "1. 乖離の主因（なぜモデルがこの価格を推論したか、何を見落としているか）\n"
                "2. パーサーまたは特徴量への即日改修アクション（具体的にどのフィールドや正規表現を追加すべきか）\n"
                "を簡潔な日本語箇条書き（合計4〜6行程度）で出力してください。\n\n"
                + "\n\n".join(sample_texts)
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            if response and hasattr(response, "text") and response.text:
                return response.text.strip()
    except Exception as e:
        logger.warning(f"AI diagnostics analysis failed, fallback to rule-based: {e}")
    return None


def generate_ai_diagnostics_insight(worst_items: list) -> str:
    """
    AI (Gemini Flash) を用いて、乖離ワースト物件の原因分析および即日改善アクションを生成する。
    APIキー未設定時や障害時はルールベースのサマリーにフォールバック。
    """
    if not worst_items:
        return "ワースト乖離物件はありませんでした。"

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        ai_res = _generate_gemini_insight(worst_items, api_key)
        if ai_res:
            return ai_res

    return _generate_rule_based_insight(worst_items)


def _get_price_tier(price_man: float) -> str:
    """価格帯セグメント判定"""
    if price_man < 3000:
        return "tier_low (<3000万)"
    elif price_man < 10000:
        return "tier_mid (3000万-1億)"
    elif price_man < 30000:
        return "tier_high (1億-3億)"
    else:
        return "tier_ultra (3億超)"


def _extract_single_eval_item(ev, model_cache: dict):
    company = ev.company
    ptype = ev.property_type
    model_key = f"{company}{ptype}".lower()
    prop_model = model_cache.get(model_key) or model_cache.get(f"{company}_{ptype}".lower())
    if not prop_model:
        return None

    prop_obj = prop_model.objects.filter(id=ev.property_id).first()
    if not prop_obj:
        return None

    raw_price = getattr(prop_obj, "price", 0)
    if not raw_price or float(raw_price) <= 0:
        return None

    raw_p = float(raw_price)
    actual_price_man = (raw_p / 10000.0) if raw_p >= 100_000.0 else raw_p
    predicted_price_man = float(ev.first_stage_predicted_price)
    if actual_price_man <= 0 or predicted_price_man <= 0:
        return None

    error_ratio = (predicted_price_man - actual_price_man) / actual_price_man
    biko = str(getattr(prop_obj, "biko", "") or "")
    title = str(getattr(prop_obj, "propertyName", "") or getattr(prop_obj, "title", "") or "")
    address = str(getattr(prop_obj, "address", "") or "")
    text_context = f"{title} {biko} {address}"

    features = {
        "maguchi": getattr(prop_obj, "maguchi", None),
        "roadWidth": getattr(prop_obj, "roadWidth", None),
        "floor_number": getattr(prop_obj, "floorNumber", None) or getattr(prop_obj, "floor", None),
        "total_floors": getattr(prop_obj, "totalFloors", None)
    }

    causes = classify_error_cause(error_ratio, text_context, ptype, features)

    return {
        "url": ev.property_url,
        "company": company,
        "property_type": ptype,
        "address": address,
        "actual_price_man": actual_price_man,
        "predicted_price_man": predicted_price_man,
        "error_ratio": error_ratio,
        "abs_error_ratio": abs(error_ratio),
        "causes": causes,
        "price_tier": _get_price_tier(actual_price_man),
        "text": text_context
    }


def _collect_diagnostics_data(eval_records: list) -> list:
    model_cache = {}
    app_config = apps.get_app_config("package")
    for m in app_config.get_models():
        model_cache[m.__name__.lower()] = m

    diagnostics_data = []
    for ev in eval_records:
        try:
            item = _extract_single_eval_item(ev, model_cache)
            if item:
                diagnostics_data.append(item)
        except Exception as e:
            logger.warning(f"Error extracting property {ev.property_url}: {e}")
            continue

    return diagnostics_data


def _extract_worst_items(df: pd.DataFrame) -> list:
    worst_over = df.sort_values(by="error_ratio", ascending=False).head(5)
    worst_under = df.sort_values(by="error_ratio", ascending=True).head(5)

    worst_items = []
    for _, row in worst_over.iterrows():
        worst_items.append({
            "type": "over_prediction",
            "url": row["url"],
            "property_type": row["property_type"],
            "actual_price_man": round(row["actual_price_man"], 1),
            "predicted_price_man": round(row["predicted_price_man"], 1),
            "error_percent": f"+{row['error_ratio']*100:.1f}%",
            "causes": row["causes"],
            "text": str(row.get("text", ""))
        })
    for _, row in worst_under.iterrows():
        worst_items.append({
            "type": "under_prediction",
            "url": row["url"],
            "property_type": row["property_type"],
            "actual_price_man": round(row["actual_price_man"], 1),
            "predicted_price_man": round(row["predicted_price_man"], 1),
            "error_percent": f"{row['error_ratio']*100:.1f}%",
            "causes": row["causes"],
            "text": str(row.get("text", ""))
        })
    return worst_items


def run_diagnostics(limit: int = 5000, target_date: str = None, dry_run: bool = False, notify: bool = False):
    """
    価格推定の最新精度診断を一括実行し、レポートを出力する。
    """
    logger.info(f"Starting daily prediction diagnostics (limit={limit}, dry_run={dry_run})...")

    # 1. 評価済みレコードの収集
    qs = PropertyEvaluation.objects.filter(first_stage_predicted_price__isnull=False)
    if target_date:
        qs = qs.filter(analyzed_at__date=target_date)

    total_evals = qs.count()
    if total_evals == 0:
        logger.warning("No evaluated properties found for diagnostics.")
        return None

    # 最新順に取得
    eval_records = list(qs.order_by("-id")[:limit])
    logger.info(f"Loaded {len(eval_records)} evaluation records.")

    # 2. 元物件モデルから実際の販売価格（price）およびテキストを取得
    diagnostics_data = _collect_diagnostics_data(eval_records)

    if not diagnostics_data:
        logger.warning("No valid pairs of actual vs predicted prices could be constructed.")
        return None

    df = pd.DataFrame(diagnostics_data)
    logger.info(f"Successfully processed {len(df)} diagnostic property samples.")

    # 3. 全体指標の算出
    overall_metrics = calculate_metrics(df["actual_price_man"].values, df["predicted_price_man"].values)

    # 4. セグメント別集計 (種別別)
    type_metrics = {}
    for ptype, group in df.groupby("property_type"):
        type_metrics[ptype] = calculate_metrics(group["actual_price_man"].values, group["predicted_price_man"].values)

    # 5. 価格帯別集計
    tier_metrics = {}
    for tier, group in df.groupby("price_tier"):
        tier_metrics[tier] = calculate_metrics(group["actual_price_man"].values, group["predicted_price_man"].values)

    # 6. ワースト乖離物件の抽出 (上位5件ずつ)
    worst_items = _extract_worst_items(df)

    # AI によるワースト物件の乖離要因分析 & アクション提案
    ai_insight = generate_ai_diagnostics_insight(worst_items)

    # 7. レポート生成
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    report = {
        "date": today_str,
        "sample_count": len(df),
        "overall": overall_metrics,
        "by_property_type": type_metrics,
        "by_price_tier": tier_metrics,
        "worst_outliers": worst_items,
        "ai_insight": ai_insight
    }

    # ログ・レポートファイル保存
    log_dir = os.path.join(_crawler_dir, "package", "ml", "logs")
    os.makedirs(log_dir, exist_ok=True)
    report_json_path = os.path.join(log_dir, f"diagnostics_{today_str}.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Markdown レポート
    md_report = _generate_markdown_report(report)
    report_md_path = os.path.join(log_dir, f"diagnostics_{today_str}.md")
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(md_report)

    logger.info(f"Diagnostics report generated: {report_md_path}")
    print(md_report)

    # 8. Slack 通知
    if notify and not dry_run:
        slack_msg = _format_slack_notification(report)
        channel = os.getenv("SLACK_DEV_CHANNEL", "dev-agent")
        asyncio.run(send_dev_report(slack_msg, channel=channel))
        logger.info(f"Slack notification sent to {channel}.")

    return report


# エイリアス
diagnose_predictions = run_diagnostics


def _generate_markdown_report(report: dict) -> str:
    """Markdown 形式の日次診断サマリー生成"""
    ov = report["overall"]
    lines = [
        f"# 日次価格推定精度診断レポート ({report['date']})",
        "",
        f"- **評価サンプル数**: {report['sample_count']:,} 件",
        f"- **主KPI (MdAPE)**: **{ov['mdape']}%** (目標 12.0% 以下)",
        f"- **MAPE**: {ov['mape']}% | **RMSE**: {ov['rmse']} 万円",
        f"- **Hit Rate (±10%以内)**: **{ov['hit_rate_10']}%**",
        f"- **Hit Rate (±20%以内)**: **{ov['hit_rate_20']}%**",
        "",
        "## 種別別精度スコアカード",
        "| 種別 | サンプル数 | MdAPE (%) | MAPE (%) | Hit@10% | Hit@20% |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |"
    ]
    for ptype, m in report["by_property_type"].items():
        lines.append(f"| {ptype} | {m['count']:,} | {m['mdape']}% | {m['mape']}% | {m['hit_rate_10']}% | {m['hit_rate_20']}% |")

    lines.extend([
        "",
        "## 価格帯別精度",
        "| 価格帯 | サンプル数 | MdAPE (%) | Hit@20% |",
        "| :--- | :---: | :---: | :---: |"
    ])
    for tier, m in report["by_price_tier"].items():
        lines.append(f"| {tier} | {m['count']:,} | {m['mdape']}% | {m['hit_rate_20']}% |")

    lines.extend([
        "",
        "## ワースト乖離物件 (抽出上位)",
        "| 種別 | 方向 | 実価格 | 推論価格 | 乖離率 | 推定要因 | URL |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :--- |"
    ])
    for w in report["worst_outliers"]:
        direction = "過大 (Over)" if w["type"] == "over_prediction" else "過小 (Under)"
        causes_str = ", ".join(w["causes"])
        lines.append(f"| {w['property_type']} | {direction} | {w['actual_price_man']}万 | {w['predicted_price_man']}万 | {w['error_percent']} | `{causes_str}` | [Link]({w['url']}) |")

    lines.extend([
        "",
        "## AI によるワースト乖離分析 ＆ 改善アクション提案",
        report.get("ai_insight", "特記事項なし")
    ])

    return "\n".join(lines)


def _format_slack_notification(report: dict) -> str:
    """Slack 用ダイジェスト生成"""
    ov = report["overall"]
    msg = [
        f"📊 *【日次価格推定精度診断】 ({report['date']})*",
        f"• サンプル数: `{report['sample_count']:,}` 件",
        f"• *主KPI (MdAPE)*: *{ov['mdape']}%* (目標 12.0%以下)",
        f"• Hit Rate: ±10%以内=`{ov['hit_rate_10']}%` / ±20%以内=`{ov['hit_rate_20']}%`",
        "",
        "*種別別 MdAPE*:"
    ]
    for ptype, m in report["by_property_type"].items():
        msg.append(f"• `{ptype}`: {m['mdape']}% (Hit@20: {m['hit_rate_20']}%, {m['count']}件)")

    msg.extend([
        "",
        "*乖離ワースト物件 (上位改善対象)*:"
    ])
    for w in report["worst_outliers"][:4]:
        direction = "過大" if w["type"] == "over_prediction" else "過小"
        msg.append(f"• [{direction}] `{w['error_percent']}` ({w['actual_price_man']}万 ➔ {w['predicted_price_man']}万) 要因: `{', '.join(w['causes'])}`\n  <{w['url']}>")

    if report.get("ai_insight"):
        msg.extend([
            "",
            "🤖 *AI 診断インサイト ＆ 改善アクション:*",
            report["ai_insight"]
        ])

    return "\n".join(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="日次価格推定精度診断")
    parser.add_argument("--limit", type=int, default=5000, help="診断対象件数")
    parser.add_argument("--date", type=str, default=None, help="対象日付 (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Slack通知を行わず画面出力のみ")
    parser.add_argument("--notify", action="store_true", help="Slack通知を送信する")
    args = parser.parse_args()

    run_diagnostics(limit=args.limit, target_date=args.date, dry_run=args.dry_run, notify=args.notify)

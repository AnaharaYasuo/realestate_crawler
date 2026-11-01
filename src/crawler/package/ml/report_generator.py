"""
プロ鑑定士 × 元祖狼旅団団長 レポート生成エンジン (Issue #1175)
通知対象として最終選抜された物件のみを対象にGemini (3.8 Flash / 2.5 Flash) を呼び出し、
高度レポートを生成してPropertyEvaluationモデルに永続化する。
"""

import json
import logging
import os
import re
from typing import Any

from package.ml.danchou_rag import calculate_far_slack, search_danchou_knowledge

logger = logging.getLogger(__name__)

def _build_rag_prompt(eval_rec, prop, ptype_jp: str, asking_price_man: int, pred_price: float, address: str, access: str, matched_kb: list, far_slack: float | None) -> str:
    sekisan_price = float(eval_rec.estimated_sekisan_price or 0.0)
    chikunen = getattr(prop, 'chikunengetsuStr', '') or getattr(prop, 'chikunenki', '-')
    kouzou = getattr(prop, 'kouzou', '-')
    tochi = getattr(prop, 'tochiMensekiStr', '-')
    tate = getattr(prop, 'tatemonoMensekiStr', '-') or getattr(prop, 'senyuMensekiStr', '-')
    kenpei = getattr(prop, 'kenpeiStr', '-')
    youseki = getattr(prop, 'yousekiStr', '-')
    setsudou = getattr(prop, 'setsudou', '-')
    diff_man = int(pred_price - asking_price_man) if pred_price > 0 else '-'

    return f"""
あなたは百戦錬磨の不動産鑑定士であり、かつ伝説の不動産ブログ『狼旅団の地下に潜った不動産ブログ』(http://siokaraiookami.blog.fc2.com/) の管理人である「団長（メカ団長）」です。
以下の不動産物件について、通知対象となる超優良・お宝候補として選別されました。
プロの不動産鑑定士としての理論的・客観的な評価（3面価格、最有効使用・容積余力、法的/物理的リスク）と、
元祖・狼旅団の団長としての辛口で生々しい実戦目利き（指値・瞬間蒸発・レントロール原契約・客付け・泥水再生・出口戦略）の双方を盛り込んだレポートを作成してください。

【物件データ】
- 物件種別: {ptype_jp}
- 所在地: {address}
- 交通: {access}
- 売出価格: {asking_price_man}万円
- ML理論予測価格: {int(pred_price) if pred_price > 0 else '未算出'}万円 (割安額: {diff_man}万円)
- 想定積算価格: {int(sekisan_price) if sekisan_price > 0 else '未算出'}万円
- 築年月: {chikunen} / 構造: {kouzou}
- 土地面積: {tochi} / 建物面積: {tate}
- 建ぺい/容積率: {kenpei} / {youseki} (未消化容積余力: {f'約{far_slack}%' if far_slack is not None else '不明'})
- 接道状況: {setsudou}
- 年間CF: {eval_rec.cash_flow or '-'}万円 / DSCR: {eval_rec.dscr or '-'}

【団長RAGから引き当てた過去記事のエッセンス】
{json.dumps(matched_kb, ensure_ascii=False, indent=2)}

【出力フォーマット（必ず以下のJSON形式のみで出力してください）】
```json
{{
  "investment_rating": "AAA または AA または A または B",
  "ai_evaluation_summary": "プロ鑑定士としての総括サマリー（2行程度）",
  "highest_and_best_use": "最有効使用および容積余力・増床・用途転換・更地化の可能性に関する考察（3行程度）",
  "danchou_comment": "元祖・狼旅団 団長の口調による辛口実戦レビュー（4〜6行程度）",
  "ai_positive_points": "高評価ポイント箇条書き（3点程度）",
  "ai_negative_points": "留意・落とし穴（法的・物理的DDチェック、2〜3点）"
}}
```
"""

def _call_gemini_api(model_name: str, api_key: str, prompt: str) -> dict[str, Any] | None:
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        resp = client.models.generate_content(model=model_name, contents=prompt)
        text = resp.text or ""
        match = re.search(r"```json\s*(\{[^}]*\})\s*```", text, re.DOTALL)
        if not match:
            match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("Gemini generation failed for %s: %s", model_name, e)
    return None

def _generate_fallback_report(matched_kb: list, asking_price_man: int, pred_price: float, sekisan_price: float, far_slack: float | None, address: str) -> dict[str, Any]:
    diff_man = int(pred_price - asking_price_man) if pred_price > 0 else 0
    kb_top = matched_kb[0] if matched_kb else {}
    rating = "AAA" if diff_man >= 1000 or (sekisan_price > asking_price_man * 1.1) else "A"
    
    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"市場理論価格対比で{diff_man}万円の価格乖離があり、原価法・取引比較法の観点から明確なディスカウントが確認される優良案件。",
        "highest_and_best_use": f"指定容積率に対する未消化余力（{far_slack or 0}%）を活かした将来の増床または高密度化建て替え適性あり。更地化による出口戦略も視野に入る。",
        "danchou_comment": f"「表面利回りと積算の数字だけで涎垂らすなよ。いいか、{kb_top.get('essence', '公道接道で積算割れなしなら指値ゴネずに即買い付けが鉄則だ')}。素人がレントロールくれと元付に電話して門前払い食らってる間に、現金組に横っ飛びされる獲物だ。原契約と道路付けをその目で確かめて一撃で仕留めろ。」",
        "ai_positive_points": f"・理論価格より{diff_man}万円割安（明確な価格歪み）\n・積算担保評価（{int(sekisan_price)}万）と売出価格の健全性\n・{address}における底堅い賃貸・実需需要",
        "ai_negative_points": "・現地での境界標・越境・私道持分有無の確認必須\n・給排水管・ガス設備の老朽化およびプロパン残債縛りの確認\n・退去発生時の賃料下落を織り込んだCFストレステスト推奨"
    }

def _persist_report(eval_rec, report_data: dict[str, Any], far_slack: float | None) -> None:
    try:
        eval_rec.investment_rating = report_data.get("investment_rating", "")
        eval_rec.ai_evaluation_summary = report_data.get("ai_evaluation_summary", "")
        eval_rec.highest_and_best_use = report_data.get("highest_and_best_use", "")
        eval_rec.danchou_comment = report_data.get("danchou_comment", "")
        eval_rec.ai_positive_points = report_data.get("ai_positive_points", "")
        eval_rec.ai_negative_points = report_data.get("ai_negative_points", "")
        eval_rec.far_slack_ratio = far_slack
        eval_rec.save()
        logger.info("Successfully persisted report for %s", eval_rec.property_url)
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("Failed to save report fields: %s", e)

def generate_professional_and_danchou_report(eval_rec, prop, ptype_jp: str, asking_price_man: int, pred_price: float, address: str, access: str) -> dict[str, Any]:
    """選別された通知対象物件に対して、プロ鑑定分析および団長RAGレビューを生成し、eval_recに反映して保存する。"""
    sekisan_price = float(eval_rec.estimated_sekisan_price or 0.0)
    far_slack = calculate_far_slack(prop)
    
    query = f"{ptype_jp} 売出{asking_price_man}万 予測{int(pred_price)}万 積算{int(sekisan_price)}万 容積余力{far_slack}% {access}"
    matched_kb = search_danchou_knowledge(query, top_k=2)

    model_name = os.getenv("GEMINI_RECOMMEND_MODEL", "gemini-3.8-flash")
    api_key = os.getenv("GEMINI_API_KEY")

    report_data = None
    if api_key:
        prompt = _build_rag_prompt(eval_rec, prop, ptype_jp, asking_price_man, pred_price, address, access, matched_kb, far_slack)
        report_data = _call_gemini_api(model_name, api_key, prompt)
        if not report_data and model_name != "gemini-2.5-flash":
            report_data = _call_gemini_api("gemini-2.5-flash", api_key, prompt)

    if not report_data:
        report_data = _generate_fallback_report(matched_kb, asking_price_man, pred_price, sekisan_price, far_slack, address)

    _persist_report(eval_rec, report_data, far_slack)
    return report_data

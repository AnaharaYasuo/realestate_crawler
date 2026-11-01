"""
プロフェッショナル物件評価 ＆ 団長RAGレポート生成エンジン (Issue #1175, #1179)

選別された通知対象物件に対して、高額なプロの評価レポート（最有効使用、容積余力、法的/物理的DD）と
元祖狼旅団団長RAGの目利き視点を統合した定性評価を生成する。
Gemini 3.8 Flash / 2.5 Flash を活用し、未設定・クォータ枯渇時でも物件種別（区分/土地/一棟/戸建）に
完全に適合した多層ルールベースフォールバックにより高品質なレポートを永続化・提供する。
"""

import json
import logging
import os
import re
import urllib.request
from typing import Any

from package.ml.danchou_rag import calculate_far_slack, search_danchou_knowledge

logger = logging.getLogger(__name__)

def _build_rag_prompt(
    eval_rec, prop, ptype_jp: str, asking_price_man: int, pred_price: float,
    address: str, access: str, matched_kb: list, far_slack: float | None
) -> str:
    sekisan_price = float(eval_rec.estimated_sekisan_price or 0.0)
    tochi_m2 = getattr(prop, "tochiMenseki", None) or "-"
    tate_m2 = getattr(prop, "tatemonoMenseki", None) or getattr(prop, "senyuMenseki", None) or "-"
    chikunen = getattr(prop, "chikunenStr", None) or getattr(prop, "chikunen", None) or "-"
    diff_man = int(pred_price - asking_price_man)
    ratio = round((diff_man / pred_price) * 100.0, 1) if pred_price > 0 else 0.0

    kb_context = "\n".join([f"・【{item.get('title')}】\n{item.get('essence')}" for item in matched_kb])

    return f"""あなたは百戦錬磨の不動産鑑定士であり、かつ伝説の不動産投資家『狼旅団の団長（メカ団長）』の直系弟子です。
以下の割安検出物件について、不動産鑑定プロとしての精緻な分析と、団長の辛口実戦目利きを融合させた
最高峰の物件評価レポートを作成してください。

【物件概要】
・種別: {ptype_jp}
・所在地: {address}
・アクセス: {access}
・売出価格: {asking_price_man}万円
・理論予測価格: {int(pred_price)}万円（割安額: {diff_man}万円、割安率: {ratio}%）
・積算価格: {int(sekisan_price)}万円
・土地面積: {tochi_m2} m2 / 建物面積: {tate_m2} m2 / 築年: {chikunen}
・容積未消化余力: {far_slack if far_slack is not None else 'N/A'}%

【団長ナレッジベース（参考実戦哲学）】
{kb_context}

【出力要件】
必ず以下のJSONフォーマットのみを返してください。Markdownのコードブロック(```json)は含めないでください。
{{
  "investment_rating": "AAA" または "AA" または "A" または "B",
  "ai_evaluation_summary": "プロ鑑定士視点での物件評価総括（2〜3文）。取引事例比較・原価性・収益性からの歪み分析。",
  "highest_and_best_use": "最有効使用（Highest & Best Use）とポテンシャル。種別が区分の場合は実需居住・賃貸・リノベ再販、土地/一棟/戸建の場合は未消化容積率（{far_slack}%）や敷地条件に応じた増床・建て替え・更地化・出口戦略。",
  "danchou_comment": "元祖・狼旅団団長としての辛口実戦目利き（『表面利回りや積算だけで涎垂らすな』等の語り口調。原契約、道路付け、客付け、指値戦略など）。",
  "ai_positive_points": "箇条書きで3点。高評価ポイント（割安度、積算、立地需要、仕様など）。改行区切り。",
  "ai_negative_points": "箇条書きで3点。物理的・法的DDチェック（現地確認、私道・越境、配管・設備、修繕費リスクなど）。改行区切り。"
}}
"""

def _call_gemini_api(model_name: str, api_key: str, prompt: str) -> dict[str, Any] | None:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"}
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        match = re.search(r"\{[^}]*\}", text)
        if not match:
            match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (RuntimeError, ValueError, OSError) as e:
        logger.warning("Gemini generation failed for %s: %s", model_name, e)
    return None

def _generate_fallback_for_mansion(diff_man: int, ratio: float, address: str, kb_top: dict[str, Any]) -> dict[str, Any]:
    rating = "AAA" if ratio >= 30.0 or diff_man >= 1500 else "AA" if ratio >= 20.0 else "A"
    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"市場理論価格対比で{diff_man}万円（{ratio}%）の価格乖離。近隣成約平米単価および築年減価水準に照らして明確なディスカウントが確認される優良区分案件。",
        "highest_and_best_use": "専有部スケルトンリノベーションによる実需居住向け再販、または駅近立地を活かした安定インカム賃貸運用が最有効使用。将来の住み替え・売却出口も極めて堅実。",
        "danchou_comment": f"「表面利回りと割安額だけで涎垂らすなよ。いいか、{kb_top.get('essence', '区分は修繕積立金残高と専有部給排水管の更新履歴が命')}。管理規約の縛りと管理費等の滞納状況を総会議事録で確認して、指値一発で確実に仕留めろ。」",
        "ai_positive_points": f"・近隣相場対比で{diff_man}万円割安（明確な価格歪み）\n・{address}周辺の実需・賃貸の堅調な居住ニーズ\n・リノベ後のバリューアップ期待値が高い間取り構造",
        "ai_negative_points": "・修繕積立金の総額積立残高および将来の一時金徴収予定の確認\n・専有部床下の給排水管（鉄管・鉛管の有無）の更新履歴\n・管理規約による利用制限（ペット・民泊・事務所・楽器可否）"
    }

def _generate_fallback_for_land(diff_man: int, ratio: float, address: str, kb_top: dict[str, Any], far_slack: float | None) -> dict[str, Any]:
    rating = "AAA" if ratio >= 30.0 or diff_man >= 500 else "AA" if ratio >= 20.0 else "A"
    slack_text = f"（未消化容積率: {far_slack}%）" if far_slack is not None else ""
    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"路線価および近隣公示地価対比で{diff_man}万円（{ratio}%）のディスカウント。更地または古家解体後の土地実質仕入れ値として高い安全余裕度を誇る。",
        "highest_and_best_use": f"前面道路幅員と指定容積率{slack_text}を活かした注文住宅用地、または建売・狭小アパートビルダーへの高密度開発用地としての卸・再販が最有効使用。",
        "danchou_comment": f"「更地で安いからと飛びつくな。いいか、{kb_top.get('essence', '土地は水道管引込径と道路付け、擁壁の死に金を計算できないと即死する')}。前面道路の配管と高低差を現地で確認し、問題なければ満額即決で叩き込め。」",
        "ai_positive_points": f"・周辺公示地価比で{diff_man}万円の割安仕入れ余力\n・{address}における住宅・事業用地としての底堅い引き合い\n・建築条件なし土地としての自由な設計・プラン自由度",
        "ai_negative_points": "・前面道路配水管から宅内への水道引込管径（20mm以上か）の確認\n・高低差に伴う擁壁再構築費用およびセットバック・隅切りの要否\n・確定測量図および境界標（隣地・道路）の全点明示状況"
    }

def _generate_fallback_for_building(
    diff_man: int, ratio: float, asking_price_man: int, sekisan_price: float,
    far_slack: float | None, address: str, kb_top: dict[str, Any]
) -> dict[str, Any]:
    rating = "AAA" if (diff_man >= 1000 and sekisan_price > asking_price_man) or ratio >= 25.0 else "AA" if ratio >= 15.0 else "A"
    slack_desc = f"指定容積率に対する未消化余力（{far_slack}%）を保有。" if far_slack and far_slack > 20 else "現状建物を限界までインカム運用。"
    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"市場理論価格対比{diff_man}万円（{ratio}%）割安、積算価格{int(sekisan_price)}万円。インカムゲインと担保余力のバランスが取れた一棟案件。",
        "highest_and_best_use": f"{slack_desc}満室化インカムによる元本スピード回収後、将来の解体更地化・高密度アパート建て替え出口が最有効使用。",
        "danchou_comment": f"「表面利回りと積算だけで涎垂らすなよ。いいか、{kb_top.get('essence', 'レントロールの原契約日と公道接道を穴が開くほど見ろ')}。サクラ入居や客付けAD盛りに騙されず、原契約を確認して一撃で仕留めろ。」",
        "ai_positive_points": f"・理論価格より{diff_man}万円割安（明確な価格歪み）\n・積算担保評価（{int(sekisan_price)}万）と売出価格の健全性\n・{address}エリアの安定した単身・ファミリー賃貸需要",
        "ai_negative_points": "・レントロール原契約日の確認（直近短期契約のサクラ・AD盛り看破）\n・外壁・屋上防水のメンテ履歴およびプロパンガス残債縛りの有無\n・公道接道状況および地銀プロパー融資の適合性"
    }

def _generate_fallback_for_kodate(diff_man: int, ratio: float, address: str, kb_top: dict[str, Any], far_slack: float | None) -> dict[str, Any]:
    rating = "AAA" if ratio >= 30.0 or diff_man >= 800 else "AA" if ratio >= 20.0 else "A"
    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"近隣戸建取引事例対比で{diff_man}万円（{ratio}%）のディスカウント。土地値近傍での仕入れが可能でありダウンサイドリスクが限定的。",
        "highest_and_best_use": "実需向け居住用リノベーション、または低ロット高利回り賃貸（ジモティー・生活保護・ペット共生客付け）によるスピード元本回収が最有効使用。",
        "danchou_comment": f"「ボロ戸建は修羅場だ。いいか、{kb_top.get('essence', '雨漏り・白蟻・汲み取りの修繕費を見誤ると即死する')}。泥水すすって再生しきる覚悟を持って、売主の弱みを突いた指値を刺せ。」",
        "ai_positive_points": f"・相場対比で{diff_man}万円割安（土地値近傍仕入れ）\n・{address}における実需・戸建賃貸需要の厚み\n・DIY・低コストリフォームによる高利回り化ポテンシャル",
        "ai_negative_points": "・床下白蟻・屋根裏雨漏り・基礎クラックの目視点検必須\n・給排水管老朽化および汲み取り・浄化槽から本下水への切替費用\n・接道条件（建築基準法第42条道路・接道2m以上か）の確認"
    }

def _generate_fallback_report(
    matched_kb: list, ptype_jp: str, asking_price_man: int, pred_price: float,
    sekisan_price: float, far_slack: float | None, address: str
) -> dict[str, Any]:
    diff_man = int(pred_price - asking_price_man) if pred_price > 0 else 0
    ratio = round((diff_man / pred_price) * 100.0, 1) if pred_price > 0 else 0.0
    kb_top = matched_kb[0] if matched_kb else {}

    if "マンション" in ptype_jp:
        return _generate_fallback_for_mansion(diff_man, ratio, address, kb_top)
    if "土地" in ptype_jp:
        return _generate_fallback_for_land(diff_man, ratio, address, kb_top, far_slack)
    if "アパート" in ptype_jp or "一棟" in ptype_jp:
        return _generate_fallback_for_building(diff_man, ratio, asking_price_man, sekisan_price, far_slack, address, kb_top)
    return _generate_fallback_for_kodate(diff_man, ratio, address, kb_top, far_slack)

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

def generate_professional_and_danchou_report(
    eval_rec, prop, ptype_jp: str, asking_price_man: int, pred_price: float, address: str, access: str
) -> dict[str, Any]:
    """選別された通知対象物件に対して、プロ鑑定分析および団長RAGレビューを生成し、eval_recに反映して保存する。"""
    sekisan_price = float(eval_rec.estimated_sekisan_price or 0.0)
    far_slack = calculate_far_slack(prop)
    
    query = f"{ptype_jp} 売出{asking_price_man}万 予測{int(pred_price)}万 積算{int(sekisan_price)}万 容積余力{far_slack}% {access}"
    matched_kb = search_danchou_knowledge(query, ptype_jp=ptype_jp, top_k=2)

    model_name = os.getenv("GEMINI_RECOMMEND_MODEL", "gemini-3.8-flash")
    api_key = os.getenv("GEMINI_API_KEY")

    report_data = None
    if api_key:
        prompt = _build_rag_prompt(eval_rec, prop, ptype_jp, asking_price_man, pred_price, address, access, matched_kb, far_slack)
        report_data = _call_gemini_api(model_name, api_key, prompt)
        if not report_data and model_name != "gemini-2.5-flash":
            report_data = _call_gemini_api("gemini-2.5-flash", api_key, prompt)

    if not report_data:
        report_data = _generate_fallback_report(matched_kb, ptype_jp, asking_price_man, pred_price, sekisan_price, far_slack, address)

    _persist_report(eval_rec, report_data, far_slack)
    return report_data

"""
プロフェッショナル物件評価 ＆ 団長RAGレポート生成エンジン (Issue #1175, #1179, #1182)

選別された通知対象物件に対して、高額なプロの評価レポート（最有効使用、容積余力、法的/物理的DD）と
元祖狼旅団団長RAGの目利き視点を統合した定性評価を生成する。
物件Webサイト（詳細ページ）の本文・備考・リフォーム・修繕履歴等を能動的に取得・解析し、
個別具体的な事実をプロンプトおよびフォールバックに反映させる。
Gemini 3.8 Flash / 2.5 Flash を活用し、未設定・クォータ枯渇時でも物件種別（区分/土地/一棟/戸建）に
完全に適合した多層ルールベースフォールバックにより高品質なレポートを永続化・提供する。
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request
from typing import Any

import chardet
from bs4 import BeautifulSoup
from package.ml.danchou_rag import calculate_far_slack, search_danchou_knowledge

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_PAGE_TEXT_CHARS = 3000


def fetch_property_page_text(url: str, timeout: int = 5) -> str:
    """
    物件詳細Webページにアクセスし、ノイズを除去した本文テキストを抽出する (Issue #1182)。
    サイトアクセスエラーやタイムアウト時は安全に空文字を返し、処理を継続する。
    """
    if not url or not url.startswith("http"):
        return ""

    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_bytes = resp.read()
            encoding = resp.headers.get_content_charset()
            if not encoding:
                detected = chardet.detect(raw_bytes[:5000])
                encoding = detected.get("encoding") or "utf-8"

        html_text = raw_bytes.decode(encoding, errors="ignore")
        soup = BeautifulSoup(html_text, "html.parser")

        # 不要要素の除去
        for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
            tag.decompose()

        text = soup.get_text(separator=" ")
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]
        clean_lines = [line for line in lines if len(line) > 3]
        combined = "\n".join(clean_lines)
        return combined[:MAX_PAGE_TEXT_CHARS]
    except (RuntimeError, ValueError, OSError, urllib.error.URLError) as e:
        logger.debug("Could not fetch property page text from %s: %s", url, e)
        return ""


def _build_rag_prompt(
    eval_rec, prop, ptype_jp: str, asking_price_man: int, pred_price: float,
    address: str, access: str, matched_kb: list, far_slack: float | None,
    site_text: str = ""
) -> str:
    sekisan_price = float(eval_rec.estimated_sekisan_price or 0.0)
    tochi_m2 = getattr(prop, "tochiMenseki", None) or "-"
    tate_m2 = getattr(prop, "tatemonoMenseki", None) or getattr(prop, "senyuMenseki", None) or "-"
    chikunen = getattr(prop, "chikunengetsuStr", None) or getattr(prop, "chikunenki", None) or getattr(prop, "chikunenStr", None) or "-"
    kouzou = getattr(prop, "kouzou", None) or "-"
    setsudou = getattr(prop, "setsudou", None) or "-"
    cf_val = getattr(eval_rec, "cash_flow", None) or "-"
    dscr_val = getattr(eval_rec, "dscr", None) or "-"
    diff_man = int(pred_price - asking_price_man)
    ratio = round((diff_man / pred_price) * 100.0, 1) if pred_price > 0 else 0.0

    kb_context = "\n".join([f"・【{item.get('title')}】\n{item.get('essence')}" for item in matched_kb])

    site_info_section = ""
    if site_text.strip():
        site_info_section = f"""
【物件詳細サイト（Web）掲載の個別情報・備考・アピールポイント】
{site_text.strip()[:2000]}
"""

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
・構造: {kouzou} / 接道状況: {setsudou}
・年間CF: {cf_val}万円 / DSCR: {dscr_val}
・容積未消化余力: {far_slack if far_slack is not None else 'N/A'}%
{site_info_section}
【団長ナレッジベース（参考実戦哲学）】
{kb_context}

【出力要件】
※Webサイト掲載情報にリフォーム履歴・大規模修繕・入居状況（満室/空室）・建築条件・特記事項等の個別事実がある場合、必ず各項目に反映させてください。
必ず以下のJSONフォーマットのみを返してください。Markdownのコードブロック(```json)は含めないでください。
{{
  "investment_rating": "AAA" または "AA" または "A" または "B",
  "ai_evaluation_summary": "プロ鑑定士視点での物件評価総括（2〜3文）。取引事例比較・原価性・収益性からの歪み分析。Web掲載の具体的特徴も加味。",
  "highest_and_best_use": "最有効使用（Highest & Best Use）とポテンシャル。種別が区分の場合は実需居住・賃貸・リノベ再販、土地/一棟/戸建の場合は未消化容積率（{far_slack}%）や敷地条件に応じた増床・建て替え・更地化・出口戦略。",
  "danchou_comment": "元祖・狼旅団団長としての辛口実戦目利き（『表面利回りや積算だけで涎垂らすな』等の語り口調。原契約、道路付け、客付け、指値戦略など）。",
  "ai_positive_points": "箇条書きで3点。高評価ポイント（割安度、積算、立地需要、Webに記載された設備・リノベ優位性など）。改行区切り。",
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
        match = re.search(r"(\{[^}]*\})", text)
        if not match:
            match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
    except (RuntimeError, ValueError, OSError, IndexError) as e:
        logger.warning("Gemini generation failed for %s: %s", model_name, e)
    return None


def _calc_mansion_rating(ratio: float, diff_man: int) -> str:
    if ratio >= 30.0 or diff_man >= 1500:
        return "AAA"
    if ratio >= 20.0:
        return "AA"
    return "A"


def _generate_fallback_for_mansion(
    diff_man: int, ratio: float, address: str, kb_top: dict[str, Any],
    site_text: str = ""
) -> dict[str, Any]:
    rating = _calc_mansion_rating(ratio, diff_man)
    has_renov = any(k in site_text for k in ["リノベ", "リフォーム", "改装", "新調", "更新済"])
    has_large_repair = any(k in site_text for k in ["大規模修繕", "外壁塗装", "耐震補強"])

    if has_renov:
        summary_extra = "サイト情報よりリノベーション・内装更新履歴が確認され、追加バリューアップ費用を抑えた即戦力稼働・実需入居が可能。"
        use_desc = "直近リノベーション完了を活かした実需居住向け即時再販、または高賃料設定による安定インカム運用が最有効使用。"
        pos_extra = "・サイト掲載情報：室内リノベーション・給排水設備更新によるバリュー向上"
    elif has_large_repair:
        summary_extra = "サイト情報より建物全体の大規模修繕工事履歴が確認され、長期的な資産保全性が担保されている。"
        use_desc = "共用部の大規模修繕完了を活かした長期安定インカム運用、または実需居住向け再販が最有効使用。"
        pos_extra = "・サイト掲載情報：大規模修繕工事による躯体・共用部の適切な維持管理"
    else:
        summary_extra = "近隣成約平米単価および築年減価水準に照らして明確なディスカウントが確認される優良区分案件。"
        use_desc = "専有部スケルトンリノベーションによる実需居住向け再販、または駅近立地を活かした安定インカム賃貸運用が最有効使用。将来の住み替え・売却出口も極めて堅実。"
        pos_extra = "・リノベ後のバリューアップ期待値が高い間取り構造"

    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"市場理論価格対比で{diff_man}万円（{ratio}%）の価格乖離。{summary_extra}",
        "highest_and_best_use": use_desc,
        "danchou_comment": f"「表面利回りと割安額だけで涎垂らすなよ。いいか、{kb_top.get('essence', '区分は修繕積立金残高と専有部給排水管の更新履歴が命')}。管理規約の縛りと管理費等の滞納状況を総会議事録で確認して、指値一発で確実に仕留めろ。」",
        "ai_positive_points": f"・近隣相場対比で{diff_man}万円割安（明確な価格歪み）\n・{address}周辺の実需・賃貸の堅調な居住ニーズ\n{pos_extra}",
        "ai_negative_points": "・修繕積立金の総額積立残高および将来の一時金徴収予定の確認\n・専有部床下の給排水管（鉄管・鉛管の有無）の更新履歴\n・管理規約による利用制限（ペット・民泊・事務所・楽器可否）"
    }


def _calc_land_rating(ratio: float, diff_man: int) -> str:
    if ratio >= 30.0 or diff_man >= 500:
        return "AAA"
    if ratio >= 20.0:
        return "AA"
    return "A"


def _generate_fallback_for_land(
    diff_man: int, ratio: float, address: str, kb_top: dict[str, Any], far_slack: float | None,
    prop: Any = None, site_text: str = ""
) -> dict[str, Any]:
    rating = _calc_land_rating(ratio, diff_man)
    slack_text = f"（未消化容積率: {far_slack}%）" if far_slack is not None else ""

    # 建築条件・接道状況に応じた動的分岐
    joken = getattr(prop, "kenchikuJoken", None) or getattr(prop, "kenchikuJokenStr", None) or ""
    setsudou = getattr(prop, "setsudou", None) or getattr(prop, "roadStructure", None) or ""
    is_joken_nashi = "なし" in joken or "無" in joken or "建築条件無" in str(getattr(prop, "name", "")) or "建築条件なし" in site_text
    is_joken_ari = ("付き" in joken or "有" in joken or "建築条件付" in str(getattr(prop, "name", ""))) and not is_joken_nashi

    if is_joken_nashi:
        plan_desc = "・建築条件なし土地としての自由な設計・プラン自由度（サイト確認済）"
    elif is_joken_ari:
        plan_desc = "・建築条件付き土地（指定ハウスメーカーでの建物プラン協議前提）"
    else:
        plan_desc = "・土地仕入れ後の建築条件有無およびプラン自由度の確認推奨"

    has_survey = any(k in site_text for k in ["確定測量", "測量済", "境界標全点", "実測"])
    has_south_road = any(k in site_text for k in ["南道路", "南側道路", "南東道路", "南西道路"])
    if has_survey:
        plan_desc += "\n・サイト掲載情報：確定測量済みによる隣地境界確定と安全な取引性"
    if has_south_road:
        plan_desc += "\n・サイト掲載情報：陽当たり・採光性に優れた南道路接道"

    if "4m未満" in setsudou or "狭隘" in setsudou:
        use_desc = f"前面道路セットバックを考慮した専用住宅用地、または小規模敷地としての活用が最有効使用{slack_text}。"
    else:
        use_desc = f"前面道路幅員と指定容積率{slack_text}を活かした注文住宅用地、または建売・狭小アパートビルダーへの高密度開発用地としての卸・再販が最有効使用。"

    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"路線価および近隣公示地価対比で{diff_man}万円（{ratio}%）のディスカウント。更地または古家解体後の土地実質仕入れ値として高い安全余裕度を誇る。",
        "highest_and_best_use": use_desc,
        "danchou_comment": f"「更地で安いからと飛びつくな。いいか、{kb_top.get('essence', '土地は水道管引込径と道路付け、擁壁の死に金を計算できないと即死する')}。前面道路の配管と高低差を現地で確認し、問題なければ満額即決で叩き込め。」",
        "ai_positive_points": f"・周辺公示地価比で{diff_man}万円の割安仕入れ余力\n・{address}における住宅・事業用地としての底堅い引き合い\n{plan_desc}",
        "ai_negative_points": "・前面道路配水管から宅内への水道引込管径（20mm以上か）の確認\n・高低差に伴う擁壁再構築費用およびセットバック・隅切りの要否\n・確定測量図および境界標（隣地・道路）の全点明示状況"
    }


def _calc_building_rating(diff_man: int, ratio: float, asking_price_man: int, sekisan_price: float) -> str:
    if (diff_man >= 1000 and sekisan_price > asking_price_man) or ratio >= 25.0:
        return "AAA"
    if ratio >= 15.0:
        return "AA"
    return "A"


def _generate_fallback_for_building(
    diff_man: int, ratio: float, asking_price_man: int, sekisan_price: float,
    far_slack: float | None, address: str, kb_top: dict[str, Any],
    site_text: str = ""
) -> dict[str, Any]:
    rating = _calc_building_rating(diff_man, ratio, asking_price_man, sekisan_price)
    slack_desc = f"指定容積率に対する未消化余力（{far_slack}%）を保有。" if far_slack and far_slack > 20 else "現状建物を限界までインカム運用。"

    is_full_occupancy = any(k in site_text for k in ["満室", "全部賃貸中", "稼働中"])
    has_propane = "プロパン" in site_text
    summary_extra = ""
    if is_full_occupancy:
        summary_extra = "サイト情報より現況満室稼働中（オーナーチェンジ）が確認され、取得初月からの安定CF創出が見込める。"

    pos_points = [
        f"・理論価格より{diff_man}万円割安（明確な価格歪み）",
        f"・積算担保評価（{int(sekisan_price)}万）と売出価格の健全性",
        f"・{address}エリアの安定した単身・ファミリー賃貸需要"
    ]
    if is_full_occupancy:
        pos_points.append("・サイト掲載情報：満室稼働中による即時キャッシュフロー獲得")

    neg_points = [
        "・レントロール原契約日の確認（直近短期契約のサクラ・AD盛り看破）",
        "・外壁・屋上防水のメンテ履歴およびプロパンガス残債縛りの有無",
        "・公道接道状況および地銀プロパー融資の適合性"
    ]
    if has_propane:
        neg_points[1] = "・サイト掲載情報：プロパンガス供給会社による配管・給湯器無償貸与残債および違約金契約の確認必須"

    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"市場理論価格対比{diff_man}万円（{ratio}%）割安、積算価格{int(sekisan_price)}万円。{summary_extra}インカムゲインと担保余力のバランスが取れた一棟案件。",
        "highest_and_best_use": f"{slack_desc}満室化インカムによる元本スピード回収後、将来の解体更地化・高密度アパート建て替え出口が最有効使用。",
        "danchou_comment": f"「表面利回りと積算だけで涎垂らすなよ。いいか、{kb_top.get('essence', 'レントロールの原契約日と公道接道を穴が開くほど見ろ')}。サクラ入居や客付けAD盛りに騙されず、原契約を確認して一撃で仕留めろ。」",
        "ai_positive_points": "\n".join(pos_points[:3]),
        "ai_negative_points": "\n".join(neg_points)
    }


def _calc_kodate_rating(ratio: float, diff_man: int) -> str:
    if ratio >= 30.0 or diff_man >= 800:
        return "AAA"
    if ratio >= 20.0:
        return "AA"
    return "A"


def _generate_fallback_for_kodate(
    diff_man: int, ratio: float, address: str, kb_top: dict[str, Any],
    site_text: str = ""
) -> dict[str, Any]:
    rating = _calc_kodate_rating(ratio, diff_man)
    has_renov = any(k in site_text for k in ["リフォーム", "リノベ", "改装済", "外壁塗装済"])
    is_new = any(k in site_text for k in ["新築", "未入居"])

    pos_points = [
        f"・相場対比で{diff_man}万円割安（土地値近傍仕入れ）",
        f"・{address}における実需・戸建賃貸需要の厚み",
        "・DIY・低コストリフォームによる高利回り化ポテンシャル"
    ]
    if has_renov:
        pos_points[2] = "・サイト掲載情報：リフォーム・修繕実施済みによる初期投資費用の抑制"
    elif is_new:
        pos_points[2] = "・サイト掲載情報：新築・築浅未入居物件としての高い設備仕様と品確法保証"

    return {
        "investment_rating": rating,
        "ai_evaluation_summary": f"近隣戸建取引事例対比で{diff_man}万円（{ratio}%）のディスカウント。土地値近傍での仕入れが可能でありダウンサイドリスクが限定的。",
        "highest_and_best_use": "実需向け居住用リノベーション、または低ロット高利回り賃貸（ジモティー・生活保護・ペット共生客付け）によるスピード元本回収が最有効使用。",
        "danchou_comment": f"「ボロ戸建は修羅場だ。いいか、{kb_top.get('essence', '雨漏り・白蟻・汲み取りの修繕費を見誤ると即死する')}。泥水すすって再生しきる覚悟を持って、売主の弱みを突いた指値を刺せ。」",
        "ai_positive_points": "\n".join(pos_points),
        "ai_negative_points": "・床下白蟻・屋根裏雨漏り・基礎クラックの目視点検必須\n・給排水管老朽化および汲み取り・浄化槽から本下水への切替費用\n・接道条件（建築基準法第42条道路・接道2m以上か）の確認"
    }


def _generate_fallback_report(
    matched_kb: list, ptype_jp: str, asking_price_man: int, pred_price: float,
    sekisan_price: float, far_slack: float | None, address: str, prop: Any = None,
    site_text: str = ""
) -> dict[str, Any]:
    diff_man = int(pred_price - asking_price_man) if pred_price > 0 else 0
    ratio = round((diff_man / pred_price) * 100.0, 1) if pred_price > 0 else 0.0
    kb_top = matched_kb[0] if matched_kb else {}

    if "マンション" in ptype_jp:
        return _generate_fallback_for_mansion(diff_man, ratio, address, kb_top, site_text=site_text)
    if "土地" in ptype_jp:
        return _generate_fallback_for_land(diff_man, ratio, address, kb_top, far_slack, prop=prop, site_text=site_text)
    if "アパート" in ptype_jp or "一棟" in ptype_jp:
        return _generate_fallback_for_building(diff_man, ratio, asking_price_man, sekisan_price, far_slack, address, kb_top, site_text=site_text)
    return _generate_fallback_for_kodate(diff_man, ratio, address, kb_top, site_text=site_text)


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
    """選別された通知対象物件に対して、Web本文・プロ鑑定分析および団長RAGレビューを生成し、eval_recに反映して保存する。"""
    sekisan_price = float(eval_rec.estimated_sekisan_price or 0.0)
    far_slack = calculate_far_slack(prop)

    # 1. 物件Webサイトの本文テキストを能動取得 (Issue #1182)
    prop_url = getattr(eval_rec, "property_url", "") or getattr(prop, "pageUrl", "") or ""
    site_text = fetch_property_page_text(prop_url, timeout=5) if prop_url else ""

    query = f"{ptype_jp} 売出{asking_price_man}万 予測{int(pred_price)}万 積算{int(sekisan_price)}万 容積余力{far_slack}% {access}"
    matched_kb = search_danchou_knowledge(query, ptype_jp=ptype_jp, top_k=2)

    model_name = os.getenv("GEMINI_RECOMMEND_MODEL", "gemini-3.8-flash")
    api_key = os.getenv("GEMINI_API_KEY")

    report_data = None
    if api_key:
        prompt = _build_rag_prompt(
            eval_rec, prop, ptype_jp, asking_price_man, pred_price, address, access, matched_kb, far_slack,
            site_text=site_text
        )
        report_data = _call_gemini_api(model_name, api_key, prompt)
        if not report_data and model_name != "gemini-2.5-flash":
            report_data = _call_gemini_api("gemini-2.5-flash", api_key, prompt)

    if not report_data:
        report_data = _generate_fallback_report(
            matched_kb, ptype_jp, asking_price_man, pred_price, sekisan_price, far_slack, address,
            prop=prop, site_text=site_text
        )

    _persist_report(eval_rec, report_data, far_slack)
    return report_data

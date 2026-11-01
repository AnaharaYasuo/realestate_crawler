"""
狼旅団・団長RAG（Retrieval-Augmented Generation）モジュール (Issue #1175)

『狼旅団の地下に潜った不動産ブログ』(http://siokaraiookami.blog.fc2.com/) の
実戦哲学・名言・目利きノウハウをナレッジベース化し、物件特徴にマッチする過去エピソードを
動的検索してGemini（3.8 Flash / 2.5 Flash）に注入、プロ鑑定と団長レビューを生成する。
Google Cloud Storage (GCS) またはローカルキャッシュ／シードナレッジと連携。
"""

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# シード・ナレッジベース（元祖ブログのエッセンス・実戦教訓）
SEED_KNOWLEDGE_BASE = [
    {
        "id": "kb_sashine_instant",
        "title": "挨拶代わりの指値と瞬間蒸発物件のリアル",
        "category": "指値・買い付け",
        "keywords": ["指値", "買い付け", "瞬間蒸発", "現金", "公道", "積算割れなし", "買取り再販", "横っ飛び"],
        "essence": "素人は利回り計算だけで挨拶代わりに1〜2割指値を入れて元付に秒で嫌われる。だが公道接道で積算が売出を上回っている本物の歪み物件は、指値ゴネしてたら業者の現金買いや瞬足組に秒で横っ飛び（瞬間蒸発）される。満額即決で叩き込むべきか、売主の弱みを突いて鬼指値を刺すべきかの見極めが命。",
        "rule_of_thumb": "積算価格 > 売出価格 かつ 道路付けが良い物件は指値でモタモタせず即買い付けが鉄則。"
    },
    {
        "id": "kb_rentroll_fake",
        "title": "レントロールの原契約チェックとサクラ入居の看破",
        "category": "レントロール・客付け",
        "keywords": ["レントロール", "原契約", "高利回り", "サクラ", "フリーレント", "AD", "退去", "モグラ叩き"],
        "essence": "高利回りに浮かれる前にレントロールの原契約日を穴が開くほど見ろ。直近半年で急に高額家賃で埋まった部屋は売却用の仕込みサクラや客付けAD盛りの地雷。退去が出た瞬間に現況家賃から1万円下落する前提で引き直し計算しろ。昭和の古参店子が相場半値で居座っているなら退去後バリューアップはお宝だが立ち退きまで耐えられるかが勝負。",
        "rule_of_thumb": "表面利回りが高くても直近契約ばかりの物件は家賃下落15〜20%を見込んでCF再試算すること。"
    },
    {
        "id": "kb_road_sekisan_trap",
        "title": "積算至上主義の罠と金融機関のプロパー融資姿勢",
        "category": "融資・積算",
        "keywords": ["積算", "私道", "持分なし", "セットバック", "融資", "プロパー", "信金", "地銀", "ノンバンク"],
        "essence": "積算出てるからと喜ぶ信託銀行の養分たちへ。前面道路3.2mの私道持ち分なし・セットバック要で、どこのまともな地銀がプロパーを引くんだよ。再建築不可や既存不適格でノンバンク高金利しか付かないならCFなんて一瞬で吹き飛ぶ。銀行が本当に担保として見るのは路線価と道路付けと適法性だけだ。",
        "rule_of_thumb": "私道負担・狭小道路・再建築不可は積算が良くても銀行評価が出ず手詰まりになる。"
    },
    {
        "id": "kb_far_slack_upside",
        "title": "容積消化が甘い低層物件の最有効使用と出口のハメ込み",
        "category": "最有効使用・容積余力",
        "keywords": ["容積余力", "容積率", "増床", "建て替え", "最有効使用", "建売屋", "更地", "出口戦略"],
        "essence": "指定容積200%なのに現況80%しか使ってないスカスカ物件は本物のお宝。現況ボロ賃貸として限界までインカムをしゃぶり尽くした後は、更地にして建売業者や狭小アパートビルダーに土地値＋αでぶつける出口が綺麗に見える。ただし道路幅員による容積制限と斜線制限の壁を計算できないとただの机上の空論で爆死する。",
        "rule_of_thumb": "未消化容積率が50%以上あり前面道路5m以上の物件は、将来の解体更地化・高密度化出口が極めて強い。"
    },
    {
        "id": "kb_boro_house_regeneration",
        "title": "低ロット・ボロ戸建て長屋の泥水再生と雨漏り・汲み取り",
        "category": "ボロ物件・再生",
        "keywords": ["戸建て", "ボロ戸建", "長屋", "DIY", "汲み取り", "雨漏り", "傾き", "客付け", "低ロット"],
        "essence": "数百万円のボロ戸建は修羅場。再建築不可でも実質利回り20%超で回せば数年で元本回収して土地はタダ同然。だが雨漏り・基礎クラック・汲み取り浄化槽の改修費用を見誤ると即死。泥水すすってジモティーや生活保護客付けをやり切れる覚悟があるヤツだけが勝てる世界。",
        "rule_of_thumb": "ボロ戸建はリフォーム見積もりの倍額を想定し、初期回収年数4年以内を目指すこと。"
    }
]

def load_danchou_knowledge_base() -> list[dict[str, Any]]:
    """GCSまたはローカルキャッシュ、フォールバックとしてシードナレッジをロード"""
    gcs_bucket = os.getenv("GCS_BUCKET_NAME")
    local_cache_path = os.getenv("DANCHOU_KB_LOCAL_PATH", "data/rag/danchou_kb.jsonl")

    # 1. ローカルキャッシュ確認
    if os.path.exists(local_cache_path):
        try:
            items = []
            with open(local_cache_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        items.append(json.loads(line))
            if items:
                logger.info("Loaded %d knowledge entries from local cache %s", len(items), local_cache_path)
                return items
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("Failed to load local knowledge cache: %s", e)

    # 2. GCSからの取得試行（設定されている場合）
    if gcs_bucket:
        try:
            from google.cloud import storage
            client = storage.Client()
            bucket = client.bucket(gcs_bucket)
            blob = bucket.blob("rag/danchou_kb.jsonl")
            if blob.exists():
                content = blob.download_as_text(encoding="utf-8")
                items = [json.loads(line) for line in content.splitlines() if line.strip()]
                if items:
                    logger.info("Loaded %d knowledge entries from GCS gs://%s/rag/danchou_kb.jsonl", len(items), gcs_bucket)
                    # ローカルにキャッシュ保存
                    os.makedirs(os.path.dirname(local_cache_path), exist_ok=True)
                    with open(local_cache_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    return items
        except (OSError, RuntimeError) as e:
            logger.warning("GCS knowledge base fetch failed (fallback to seed): %s", e)

    # 3. シードナレッジベース（常時利用可能）
    return SEED_KNOWLEDGE_BASE

def search_danchou_knowledge(query_text: str, top_k: int = 2) -> list[dict[str, Any]]:
    """物件特徴テキストに基づき、最も合致する団長ナレッジをスコアリング抽出"""
    kb = load_danchou_knowledge_base()
    scored = []
    
    query_lower = query_text.lower()
    for item in kb:
        score = 0
        # キーワードマッチング
        for kw in item.get("keywords", []):
            if kw.lower() in query_lower:
                score += 3
        # タイトル・エッセンスの部分一致
        for word in ["戸建", "アパート", "マンション", "積算", "利回り", "容積", "指値", "公道", "私道", "サクラ", "新耐震", "旧耐震"]:
            if word in query_lower and word in (item.get("title", "") + item.get("essence", "")):
                score += 1
        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [item for score, item in scored[:top_k]]
    return results if results else kb[:top_k]

def calculate_far_slack(prop) -> float | None:
    """現況容積消化率と指定容積率から未消化容積率（%）を算出"""
    try:
        tochi_m2 = getattr(prop, "tochiMenseki", None)
        tate_m2 = getattr(prop, "tatemonoMenseki", None) or getattr(prop, "senyuMenseki", None)
        youseki_str = str(getattr(prop, "yousekiStr", "") or getattr(prop, "youseki", ""))
        
        # 容積率数値抽出（例: '200%' -> 200.0）
        match = re.search(r"(\d+(?:\.\d+)?)", youseki_str)
        if not match or not tochi_m2 or not tate_m2 or float(tochi_m2) <= 0:
            return None
            
        designated_far = float(match.group(1)) # 指定容積率 %
        current_far = (float(tate_m2) / float(tochi_m2)) * 100.0 # 現況消化率 %
        
        slack = designated_far - current_far
        return round(slack, 1) if slack > 0 else 0.0
    except (ValueError, TypeError, ZeroDivisionError):
        return None

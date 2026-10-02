import json
import logging
import os
import sys

# Django初期化設定
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
import realestateSettings

realestateSettings.configure()

from package.utils.html_sanitizer import sanitize_html_for_llm

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def collect_failures_for_site(
    site: str, property_type: str, failures_dir: str | None = None
) -> tuple[list[dict], int]:
    """
    指定されたサイト・種別の失敗スナップショット（JSONまたはHTMLファイル）を収集する。
    戻り値: (収集された失敗リスト, 読み込みエラー件数)
    """
    if not failures_dir:
        curr = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(os.path.dirname(curr)))
        failures_dir = os.path.join(root, "Temp", "failed_snapshots", site, property_type)

    if not os.path.exists(failures_dir):
        logger.info("No failure directory found at: %s", failures_dir)
        return [], 0

    collected = []
    read_errors = 0
    for fname in os.listdir(failures_dir):
        if fname.endswith(".json"):
            fpath = os.path.join(failures_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    collected.append(data)
            except Exception as e:  # noqa: BLE001
                read_errors += 1
                logger.warning("Failed to read snapshot %s: %s", fpath, e)
        elif fname.endswith(".html"):
            fpath = os.path.join(failures_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    raw_html = f.read()
                cleaned = sanitize_html_for_llm(raw_html, max_length=20000)
                collected.append({
                    "url": fname.replace(".html", ""),
                    "reason": "Extraction failure from raw html",
                    "html": cleaned,
                })
            except Exception as e:  # noqa: BLE001
                read_errors += 1
                logger.warning("Failed to read html file %s: %s", fpath, e)

    return collected, read_errors


def build_bulk_prompt(
    site: str, property_type: str, failures: list[dict], max_items: int = 200, max_payload_chars: int = 400000
) -> str:
    """
    最大200件の失敗データを極限圧縮し、Gemini Flash 向けの一括診断プロンプトを構築する。
    """
    limited_failures = failures[:max_items]
    per_item_limit = max(1000, max_payload_chars // max(1, len(limited_failures)))
    sample_payload = []
    current_chars = 0
    for idx, item in enumerate(limited_failures, 1):
        raw_html = item.get("html", "")
        cleaned = sanitize_html_for_llm(raw_html, max_length=per_item_limit) if raw_html else ""
        sample_entry = {
            "sample_id": idx,
            "url": item.get("url"),
            "failed_field": item.get("failed_field", "unknown"),
            "reason": item.get("reason", ""),
            "html_structure": cleaned,
        }
        entry_len = len(cleaned)
        if current_chars + entry_len > max_payload_chars and sample_payload:
            break
        current_chars += entry_len
        sample_payload.append(sample_entry)

    payload_json = json.dumps(sample_payload, ensure_ascii=False, indent=1)
    prompt = f"""
あなたは不動産クローラー専門の自律型修正エンジニアです。
対象サイト: {site} / 物件種別: {property_type}
合計 {len(limited_failures)} 件の失敗HTMLおよびエラー情報が提供されています。

これらの全サンプルを網羅的に分析し、以下の形式の有効なJSONのみ（マークダウン記法 ```json 不要）を出力してください。

{{
  "site": "{site}",
  "property_type": "{property_type}",
  "total_analyzed": {len(limited_failures)},
  "summary": "失敗全体の根本原因の要約（簡潔・Caveman形式）",
  "patterns": [
    {{
      "pattern_id": "P1",
      "count": 180,
      "failed_field": "price",
      "root_cause": "セレクター変更",
      "old_selector": "...",
      "recommended_selector": "..."
    }}
  ],
  "parser_file": "src/crawler/package/parser/{site}/{property_type}_parser.py",
  "recommended_fix": "全パターンを救済するための具体的なコード修正（Micro-Diff）"
}}

--- 失敗データ（最大200件） ---
{payload_json}
"""
    return prompt.strip()


def run_bulk_diagnosis_with_gemini(
    site: str, property_type: str, failures: list[dict]
) -> dict:
    """
    Gemini 2.5 Flash に最大200件の失敗HTML群を一括投入し、包括的な修正マニフェスト（JSON）を生成する。
    """
    if not failures:
        return {
            "site": site,
            "property_type": property_type,
            "total_analyzed": 0,
            "diagnosis_status": "no_failures",
            "summary": "No failures to analyze",
            "patterns": [],
        }

    api_key = os.getenv("GEMINI_API_KEY")
    prompt = build_bulk_prompt(site, property_type, failures, max_items=200)

    default_result = {
        "site": site,
        "property_type": property_type,
        "total_analyzed": len(failures),
        "diagnosis_status": "fallback",
        "summary": f"{len(failures)}件の失敗を検知。フォールバック集計。",
        "patterns": [
            {
                "pattern_id": "P1",
                "count": len(failures),
                "failed_field": failures[0].get("failed_field", "unknown"),
                "root_cause": failures[0].get("reason", "Unknown parse failure"),
            }
        ],
        "parser_file": f"src/crawler/package/parser/{site}/{property_type}_parser.py",
    }

    if not api_key or genai is None:
        logger.warning("GEMINI_API_KEY not set or genai module unavailable. Using fallback manifest.")
        return default_result

    model_name = "gemini-2.5-flash"
    try:
        http_options = types.HttpOptions(timeout=30000) if types else None
        with genai.Client(api_key=api_key, http_options=http_options) as client:
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            raw_text = (getattr(resp, "text", "") or "").strip()
            # Clean markdown codeblocks if present
            if raw_text.startswith("```json"):
                raw_text = raw_text.replace("```json", "", 1)
            if raw_text.startswith("```"):
                raw_text = raw_text.replace("```", "", 1)
            raw_text = raw_text.removesuffix("```")
            parsed = json.loads(raw_text.strip())
            if isinstance(parsed, dict):
                parsed.setdefault("diagnosis_status", "success")
                return parsed
            logger.warning("Gemini response is not a JSON object: %s", type(parsed))
            fallback = dict(default_result)
            fallback["diagnosis_status"] = "parse_error"
            return fallback
    except Exception as e:  # noqa: BLE001
        err_msg = str(e).lower()
        status = "timeout" if any(k in err_msg for k in ("timeout", "timed out", "deadline")) else "api_error"
        logger.warning("Gemini bulk diagnosis failed (%s): %s. Using default fallback manifest.", status, e)
        fallback = dict(default_result)
        fallback["diagnosis_status"] = status
        return fallback


def save_manifest(manifest: dict, output_path: str | None = None) -> str:
    if not output_path:
        curr = os.path.dirname(os.path.abspath(__file__))
        root = os.path.dirname(os.path.dirname(os.path.dirname(curr)))
        output_path = os.path.join(root, "Temp", "auto_heal_bulk_fix_manifest.json")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    logger.info("Successfully generated bulk auto-heal fix manifest at: %s", output_path)
    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Bulk Auto-Heal Diagnosis via Gemini Flash")
    parser.add_argument("--site", required=True, help="Site name (e.g. mitsui)")
    parser.add_argument("--type", required=True, help="Property type (e.g. mansion)")
    parser.add_argument("--dir", default=None, help="Directory containing failed snapshots")
    parser.add_argument("--out", default=None, help="Output manifest path")

    args = parser.parse_args()
    failures, read_errors = collect_failures_for_site(args.site, args.type, args.dir)
    if not failures and read_errors > 0:
        logger.error("No valid snapshots could be loaded due to %d read errors.", read_errors)
        sys.exit(1)

    manifest = run_bulk_diagnosis_with_gemini(args.site, args.type, failures)
    manifest["read_errors"] = read_errors
    save_manifest(manifest, args.out)

    diag_status = manifest.get("diagnosis_status")
    if diag_status in ("timeout", "api_error", "parse_error"):
        logger.error("Bulk diagnosis completed with critical failure status: %s", diag_status)
        sys.exit(2)


if __name__ == "__main__":
    main()

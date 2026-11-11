"""国交省 不動産情報ライブラリ（XIT001 API / 公式CSV）＆成約・売止スプレッド統合モジュール (Issue #1360)

1. `REINFOLIB_API_KEY` 設定時: 公式 `XIT001` API（実取引価格＋レインズ成約価格, gzip JSON）を取得
2. 公式WebダウンロードCSV/ZIP指定時: APIキー不要で全取引・成約レコードを一括パース
3. 公的L01/L02正常取引価格＋自社DB掲載終了（成約・売止）最終価格と現在売出価格のスプレッド統合
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import logging
import re
import threading
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import requests
from package.utils.open_data_cache_sync import ensure_local_cache_from_storage

logger = logging.getLogger(__name__)
MLIT_TX_BENCH_FILENAME = "mlit_transaction_benchmarks.json"

REINFOLIB_XIT001_URL = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001"
_DEFAULT_BENCH_PATH = Path(__file__).resolve().parents[2] / "data" / "mlit_transaction_benchmarks.json"
_NUM_RE = re.compile(r"(\d{1,9}(?:\.\d{1,3})?)")
_LOCK = threading.Lock()
_LOADED = False
_CHOME_BENCH: dict[str, tuple[float, float, int]] = {}
_CITY_BENCH: dict[str, tuple[float, float, int]] = {}
_PREF_BENCH: dict[str, tuple[float, float, int]] = {}

PREF_CODE_TO_NAME: dict[str, str] = {
    "01": "北海道", "02": "青森県", "03": "岩手県", "04": "宮城県", "05": "秋田県", "06": "山形県",
    "07": "福島県", "08": "茨城県", "09": "栃木県", "10": "群馬県", "11": "埼玉県", "12": "千葉県",
    "13": "東京都", "14": "神奈川県", "15": "新潟県", "16": "富山県", "17": "石川県", "18": "福井県",
    "19": "山梨県", "20": "長野県", "21": "岐阜県", "22": "静岡県", "23": "愛知県", "24": "三重県",
    "25": "滋賀県", "26": "京都府", "27": "大阪府", "28": "兵庫県", "29": "奈良県", "30": "和歌山県",
    "31": "鳥取県", "32": "島根県", "33": "岡山県", "34": "広島県", "35": "山口県", "36": "徳島県",
    "37": "香川県", "38": "愛媛県", "39": "高知県", "40": "福岡県", "41": "佐賀県", "42": "長崎県",
    "43": "熊本県", "44": "大分県", "45": "宮崎県", "46": "鹿児島県", "47": "沖縄県",
}


@dataclass(slots=True, frozen=True)
class TransactionBenchmarkHit:
    """町丁目・市区町村別の実成約基準単価および売出上乗せ倍率"""

    tx_unit_price_man: float = 0.0
    asking_to_tx_spread_ratio: float = 1.05
    sample_count: int = 0


DEFAULT_TX_HIT = TransactionBenchmarkHit()


def _norm_key(text: str) -> str:
    return "".join(unicodedata.normalize("NFKC", str(text or "")).split())


def _extract_positive_float(raw: object) -> float:
    if raw is None:
        return 0.0
    s = unicodedata.normalize("NFKC", str(raw)).replace(",", "")
    m = _NUM_RE.search(s)
    return float(m.group(1)) if m else 0.0


def classify_mlit_trade_type(raw_type: str, raw_structure: str = "", floor_area: float = 0.0) -> str | None:
    """国交省取引データの『種類』文字列を4大物件種別へ分類する。"""
    t = unicodedata.normalize("NFKC", str(raw_type or ""))
    if "中古マンション" in t:
        return "mansion"
    if "宅地(土地と建物)" in t or ("土地と建物" in t):
        s = unicodedata.normalize("NFKC", str(raw_structure or "")).upper()
        if floor_area >= 220.0 or ("RC" in s and floor_area >= 160.0):
            return "apartment"
        return "kodate"
    if "宅地(土地)" in t or t == "宅地":
        return "tochi"
    return None


def _pick_first(rec: dict[str, object], keys: tuple[str, ...]) -> object:
    for k in keys:
        val = rec.get(k)
        if val not in (None, ""):
            return val
    return ""


def _resolve_denom_area_m2(ptype: str, floor_m2: float, land_m2: float) -> float:
    if ptype in ("kodate", "apartment") and floor_m2 > 10.0:
        return floor_m2
    return land_m2


def parse_mlit_trade_record(rec: dict[str, object]) -> tuple[str, str, str, str, float] | None:
    """XIT001 JSON または公式CSVの1行辞書を `(pref, city, chome_key, ptype, unit_price_man)` へ変換する。"""
    raw_type = str(_pick_first(rec, ("Type", "種類")))
    raw_struct = str(_pick_first(rec, ("Structure", "建物の構造")))
    floor_m2 = _extract_positive_float(_pick_first(rec, ("TotalFloorArea", "延床面積（㎡）", "延床面積(㎡)")))
    ptype = classify_mlit_trade_type(raw_type, raw_struct, floor_m2)
    if ptype is None:
        return None

    pref = _norm_key(str(_pick_first(rec, ("Prefecture", "都道府県名"))))
    city = _norm_key(str(_pick_first(rec, ("Municipality", "City", "市区町村名"))))
    district = _norm_key(str(_pick_first(rec, ("DistrictName", "地区名"))))
    if not pref or not city:
        return None

    price_yen = _extract_positive_float(_pick_first(rec, ("TradePrice", "取引価格（総額）", "取引価格(総額)")))
    land_m2 = _extract_positive_float(_pick_first(rec, ("Area", "面積（㎡）", "面積(㎡)")))
    denom_m2 = _resolve_denom_area_m2(ptype, floor_m2, land_m2)
    if price_yen <= 100_000.0 or denom_m2 <= 5.0:
        return None

    unit_man = (price_yen / 10000.0) / denom_m2
    if not (0.05 <= unit_man <= 2500.0):
        return None

    chome_key = f"{pref}{city}{district}" if district else f"{pref}{city}"
    return pref, city, chome_key, ptype, round(unit_man, 4)


def _decode_xit001_response(content: bytes) -> list[dict[str, object]]:
    raw = content
    if len(raw) >= 2 and raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def fetch_reinfolib_xit001_trades(
    api_key: str,
    pref_code: str,
    year: int,
    quarter: int | None = None,
    timeout: float = 30.0,
) -> list[dict[str, object]]:
    """公式 `XIT001` API から指定都道府県・年の実取引＆レインズ成約データを取得する。"""
    if not api_key:
        return []
    params: dict[str, str] = {"year": str(year), "area": str(pref_code).zfill(2)}
    if quarter is not None:
        params["quarter"] = str(quarter)
    headers = {"Ocp-Apim-Subscription-Key": api_key, "Accept-Encoding": "gzip"}
    try:
        resp = requests.get(REINFOLIB_XIT001_URL, params=params, headers=headers, timeout=timeout)
        if resp.status_code == 200 and resp.content:
            return _decode_xit001_response(resp.content)
        logger.warning("Reinfolib XIT001 HTTP %s for area=%s year=%s", resp.status_code, pref_code, year)
    except Exception as e:  # noqa: BLE001
        logger.warning("Reinfolib XIT001 request error (area=%s year=%s): %s", pref_code, year, e)
    return []


def _decode_csv_bytes(raw_bytes: bytes) -> str:
    for enc in ("utf-8-sig", "cp932", "utf-8"):
        try:
            return raw_bytes.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="ignore")


def load_mlit_csv_or_zip_records(path: Path) -> list[tuple[str, str, str, str, float]]:
    """公式ダウンロードCSVまたはZIPから有効な成約単価タプル群を読み込む。"""
    parsed: list[tuple[str, str, str, str, float]] = []
    if not path.exists():
        return parsed

    csv_blobs: list[bytes] = []
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as zf:
            csv_blobs.extend(zf.read(n) for n in zf.namelist() if n.lower().endswith(".csv"))
    elif path.suffix.lower() == ".csv":
        csv_blobs.append(path.read_bytes())

    for blob in csv_blobs:
        reader = csv.DictReader(io.StringIO(_decode_csv_bytes(blob)))
        for row in reader:
            item = parse_mlit_trade_record(row)
            if item is not None:
                parsed.append(item)
    return parsed


def _pack_benchmark_group(
    group_dict: dict[str, list[float]],
    spread_lookup: dict[str, float],
) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for k, vals in group_dict.items():
        if vals:
            out[k] = [round(float(np.median(vals)), 4), round(spread_lookup.get(k, 1.05), 4), len(vals)]
    return out


def _compute_city_spreads(
    tx_by_city: dict[str, list[float]],
    ask_by_city: dict[str, list[float]],
) -> dict[str, float]:
    spreads: dict[str, float] = {}
    for ck, tx_vals in tx_by_city.items():
        ask_vals = ask_by_city.get(ck)
        if not tx_vals or not ask_vals:
            continue
        tx_med = float(np.median(tx_vals))
        if tx_med > 0:
            spreads[ck] = float(np.clip(float(np.median(ask_vals)) / tx_med, 0.80, 1.80))
    return spreads


def build_benchmark_maps(
    tx_records: list[tuple[str, str, str, str, float]],
    asking_records: list[tuple[str, str, str, str, float]] | None = None,
) -> dict[str, dict[str, list[float]]]:
    """`(pref, city, chome_key, ptype, unit_man)` 群から階層別中央値＆売出スプレッド辞書を構築する。"""
    tx_by_chome: dict[str, list[float]] = defaultdict(list)
    tx_by_city: dict[str, list[float]] = defaultdict(list)
    tx_by_pref: dict[str, list[float]] = defaultdict(list)

    for pref, city, chome, ptype, u_man in tx_records:
        if u_man > 0.0:
            tx_by_chome[f"{chome}|{ptype}"].append(u_man)
            tx_by_city[f"{pref}|{city}|{ptype}"].append(u_man)
            tx_by_pref[f"{pref}|{ptype}"].append(u_man)

    ask_by_city: dict[str, list[float]] = defaultdict(list)
    for pref, city, _chome, ptype, u_man in asking_records or []:
        if u_man > 0.0:
            ask_by_city[f"{pref}|{city}|{ptype}"].append(u_man)

    city_spreads = _compute_city_spreads(tx_by_city, ask_by_city)
    chome_spreads = {
        f"{chome}|{ptype}": city_spreads[f"{pref}|{city}|{ptype}"]
        for pref, city, chome, ptype, _ in tx_records
        if f"{pref}|{city}|{ptype}" in city_spreads
    }

    return {
        "chome": _pack_benchmark_group(tx_by_chome, chome_spreads),
        "city": _pack_benchmark_group(tx_by_city, city_spreads),
        "pref": _pack_benchmark_group(tx_by_pref, {}),
    }


def save_transaction_benchmarks(payload: dict[str, dict[str, list[float]]], path: Path | None = None) -> Path:
    """構築した成約ベンチマーク辞書をJSON保存し、インメモリキャッシュを即時更新する。"""
    target = path or _DEFAULT_BENCH_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    load_transaction_benchmarks(target, force_reload=True)
    return target


def _populate_bench_dict(src: object, dst: dict[str, tuple[float, float, int]]) -> None:
    dst.clear()
    if not isinstance(src, dict):
        return
    for k, v in src.items():
        if isinstance(v, list) and len(v) >= 3:
            dst[str(k)] = (float(v[0]), float(v[1]), int(v[2]))


def load_transaction_benchmarks(path: Path | None = None, *, force_reload: bool = False) -> None:
    """JSONファイル（未配置時はGCS `ml_reference_data/` から自動取得）より実成約ベンチマーク辞書をロードする。"""
    global _LOADED
    if _LOADED and not force_reload:
        return
    target = path or _DEFAULT_BENCH_PATH
    with _LOCK:
        if _LOADED and not force_reload:
            return
        ensure_local_cache_from_storage(target, MLIT_TX_BENCH_FILENAME)
        if target.exists():
            try:
                raw = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    _populate_bench_dict(raw.get("chome"), _CHOME_BENCH)
                    _populate_bench_dict(raw.get("city"), _CITY_BENCH)
                    _populate_bench_dict(raw.get("pref"), _PREF_BENCH)
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to load MLIT transaction benchmarks (%s): %s", target, e)
        _LOADED = True


def _lookup_city_bench_hit(p: str, c: str, ch: str, pt: str) -> TransactionBenchmarkHit | None:
    if not p or not c:
        return None
    hit_city = _CITY_BENCH.get(f"{p}|{c}|{pt}")
    if hit_city is None:
        return None
    ch_hit = _CHOME_BENCH.get(f"{ch}|{pt}") if ch else None
    if ch_hit is not None:
        ch_u, ch_sp, ch_n = ch_hit
        blended = (ch_n * ch_u + 3.0 * hit_city[0]) / (ch_n + 3.0)
        return TransactionBenchmarkHit(round(blended, 4), ch_sp, ch_n)
    return TransactionBenchmarkHit(*hit_city)


def lookup_transaction_benchmark(
    prefecture: str,
    city: str,
    chome_group: str,
    property_type: str,
    path: Path | None = None,
) -> TransactionBenchmarkHit:
    """町丁目 ➔ 市区町村 ➔ 都道府県の順で実成約単価ベンチマークを O(1) 参照する。"""
    load_transaction_benchmarks(path)
    p = _norm_key(prefecture)
    c = _norm_key(city)
    ch = _norm_key(chome_group)
    pt = str(property_type or "tochi").strip().lower()

    ch_hit = _CHOME_BENCH.get(f"{ch}|{pt}") if ch else None
    if ch_hit is not None and ch_hit[2] >= 2:
        return TransactionBenchmarkHit(*ch_hit)

    city_res = _lookup_city_bench_hit(p, c, ch, pt)
    if city_res is not None:
        return city_res

    hit_pref = _PREF_BENCH.get(f"{p}|{pt}") if p else None
    return TransactionBenchmarkHit(*hit_pref) if hit_pref is not None else DEFAULT_TX_HIT


def reset_transaction_benchmark_cache() -> None:
    """テスト用: 成約ベンチマークメモリキャッシュをクリアする。"""
    global _LOADED
    with _LOCK:
        _CHOME_BENCH.clear()
        _CITY_BENCH.clear()
        _PREF_BENCH.clear()
        _LOADED = False

"""全国ポータル・統計サイトの家賃相場・空室率・利回り・REIT指標の決定論的パーサー群 (Issue #1354).

AI（LLM）を一切使用せず、純粋なDOM/正規表現解析（1ページあたり < 1,000ms）により
構造化数値レコードを抽出する。
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from bs4 import BeautifulSoup

_HTML_PARSER = "html.parser"
STANDARD_LAYOUT_AREAS_SQM: dict[str, float] = {
    "1R": 18.0,
    "1K": 22.0,
    "1DK": 28.0,
    "1LDK": 40.0,
    "2K": 32.0,
    "2DK": 42.0,
    "2LDK": 55.0,
    "3K": 48.0,
    "3DK": 55.0,
    "3LDK": 70.0,
    "4K": 65.0,
    "4DK": 72.0,
    "4LDK+": 85.0,
    "all": 38.0,
}

BUILDING_BASE_AREAS_SQM: dict[str, float] = {
    "mansion": 35.0,
    "apartment": 28.0,
    "kodate": 78.0,
    "all": 38.0,
}

_LAYOUT_EXACT_MAP: dict[str, str] = {
    "ワンルーム": "1R",
    "1r": "1R",
    "1k": "1K",
    "1dk": "1DK",
    "1ldk": "1LDK",
    "2k": "2K",
    "2dk": "2DK",
    "2ldk": "2LDK",
    "3k": "3K",
    "3dk": "3DK",
    "3ldk": "3LDK",
    "4k": "4K",
    "4dk": 
    "4DK",
    "すべて": "all",
    "全体": "all",
    "平均": "all",
    "1k・1dk": "1K",
    "1ldk・2k・2dk": "1LDK",
    "2ldk・3k・3dk": "2LDK",
    "3ldk・4k〜": "3LDK",
}

_HEADER_SKIP_WORDS = frozenset({
    "間取り", "家賃相場", "市区郡", "市区町村", "駅", "所要時間", "該当物件",
})

_RESIDENTIAL_REIT_KEYWORDS = (
    "レジデンス", "レジデンシャル", "アコモデーション", "コンフォリア", "プロシード", "住宅",
)
_COMMERCIAL_REIT_KEYWORDS = (
    "ビル", "オフィス", "都市ファンド", "プライム", "商業", "リテール", "フロンティア", "物流", "プロロジス",
)

_MAN_YEN_RE = re.compile(r"(\d{1,4}(?:\.\d{1,2})?)\s*万円")
_PERCENT_RE = re.compile(r"([+-]?\d{1,3}(?:\.\d{1,2})?)\s*[％%]")
_ATHOME_PAIR_RE = re.compile(
    r"(すべて|ワンルーム|4LDK以上|[1-4][KLDR]{1,3})\s+(\d{1,3}(?:\.\d{1,2})?)\s*万円"
)


def normalize_station_label(station_name: str) -> str:
    cleaned = (station_name or "").strip()
    if cleaned.endswith("駅") and len(cleaned) > 1:
        cleaned = cleaned[:-1]
    return cleaned.strip()


def normalize_layout_label(raw_label: str) -> str | None:
    label = (raw_label or "").strip()
    if not label or any( label.startswith(h) for h in _HEADER_SKIP_WORDS ):
        return None
    low = label.lower()
    if low in _LAYOUT_EXACT_MAP:
        return _LAYOUT_EXACT_MAP[low]
    if low.startswith("4ldk"):
        return "4LDK+"
    return None


def parse_man_yen_to_yen(raw_text: str) -> int | None:
    if not raw_text or raw_text.strip() in ("-", "―", "ー"):
        return None
    m = _MAN_YEN_RE.search(raw_text)
    if not m:
        return None
    yen = round(float(m.group(1)) * 10_000)
    if 10_000 <= yen <= 5_000_000:
        return yen
    return None


def _build_rent_record(
    prefecture: str,
    city: str,
    station_name: str,
    building_type: str,
    layout_type: str,
    monthly_rent_yen: int,
    source: str,
    age_band: str = "all",
    town_name: str = "",
) -> dict[str, Any]:
    if layout_type == "all":
        std_area = BUILDING_BASE_AREAS_SQM.get(building_type, 38.0)
    else:
        std_area = STANDARD_LAYOUT_AREAS_SQM.get(layout_type, 38.0)
    rent_per_sqm = max(100, round(monthly_rent_yen / std_area))
    return {
        "prefecture": prefecture.strip(),
        "city": city.strip(),
        "station_name": normalize_station_label(station_name),
        "town_name": town_name.strip(),
        "building_type": building_type,
        "layout_type": layout_type,
        "age_band": age_band,
        "monthly_rent_yen": monthly_rent_yen,
        "standard_area_sqm": Decimal(f"{std_area:.2f}"),
        "rent_per_sqm": rent_per_sqm,
        "sample_count": None,
        "source": source,
    }


def _parse_two_col_rent_row(
    cols: list[str],
    prefecture: str,
    city: str,
    station_name: str,
    building_type: str,
    source: str,
) -> dict[str, Any] | None:
    if len(cols) < 2:
        return None
    first_col, second_col = cols[0].strip(), cols[1].strip()
    yen = parse_man_yen_to_yen(second_col)
    if yen is None:
        return None

    layout = normalize_layout_label(first_col)
    if layout is not None:
        return _build_rent_record(
            prefecture, city, station_name, building_type, layout, yen, source
        )

    if any(first_col.startswith(h) for h in _HEADER_SKIP_WORDS):
        return None
    if not city and first_col.endswith(("区", "市", "町", "村")):
        return _build_rent_record(
            prefecture, first_col, station_name, building_type, "all", yen, source
        )
    if not station_name and first_col not in ("-", "未設定"):
        return _build_rent_record(
            prefecture, city, first_col, building_type, "all", yen, source
        )
    return None


def parse_suumo_rent_table(
    html_content: str,
    prefecture: str,
    city: str = "",
    station_name: str = "",
    building_type: str = "mansion",
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_content, _HTML_PARSER)
    results: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for tb in soup.find_all("table"):
        for tr in tb.find_all("tr"):
            cols = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            rec = _parse_two_col_rent_row(
                cols, prefecture, city, station_name, building_type, "suumo_soba"
            )
            if rec is None:
                continue
            dedup = (rec["city"], rec["station_name"], rec["building_type"], rec["layout_type"])
            if dedup not in seen_keys:
                seen_keys.add(dedup)
                results.append(rec)
    return results


def _collect_athome_dl_and_tr_pairs(soup: BeautifulSoup) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            pairs.append((dt.get_text(" ", strip=True), dd.get_text(" ", strip=True)))
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) >= 2:
            pairs.append((cells[0], cells[1]))
    return pairs


def parse_athome_rent_page(
    html_content: str,
    prefecture: str,
    city: str = "",
    station_name: str = "",
    building_type: str = "all",
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_content, _HTML_PARSER)
    resolved_city = city.strip()
    if not resolved_city and not station_name and soup.title:
        title_txt = soup.title.get_text(" ", strip=True)
        m_city = re.search(r"】(?:東京都|北海道|(?:京都|大阪)府|.{2,3}県)?([^駅｜|\s]{1,15}?[市区町村])の家賃相場", title_txt)
        if m_city:
            resolved_city = m_city.group(1)

    pairs = _collect_athome_dl_and_tr_pairs(soup)
    body_txt = soup.get_text(" ", strip=True)
    for m in _ATHOME_PAIR_RE.finditer(body_txt):
        pairs.append((m.group(1), f"{m.group(2)} 万円"))

    results: list[dict[str, Any]] = []
    seen_layouts: set[str] = set()
    for raw_label, raw_price in pairs:
        layout = normalize_layout_label(raw_label)
        yen = parse_man_yen_to_yen(raw_price)
        if layout is None or yen is None or layout in seen_layouts:
            continue
        seen_layouts.add(layout)
        results.append(
            _build_rent_record(
                prefecture, resolved_city, station_name, building_type, layout, yen, "athome_souba"
            )
        )
    return results


def _parse_homes_single_row(
    cols: list[str],
    headers: list[str],
    prefecture: str,
    city: str,
    station_name: str,
) -> list[dict[str, Any]]:
    if len(cols) < 2:
        return []
    # 路線ページ: ['未設定', '東京', '14.68 万円 0 円', '物件一覧を見る']
    if len(cols) >= 3 and ("駅" in " ".join(headers) or cols[0] in ("未設定", "-")):
        yen = parse_man_yen_to_yen(cols[2])
        if yen is not None and cols[1] not in ("-", "駅"):
            return [_build_rent_record(prefecture, city, cols[1], "all", "all", yen, "homes_price")]
        return []

    # マンション・アパート2列比較テーブル
    layout = normalize_layout_label(cols[0])
    if layout is not None and len(cols) >= 3 and "マンション" in " ".join(headers):
        out: list[dict[str, Any]] = []
        m_yen = parse_man_yen_to_yen(cols[1])
        a_yen = parse_man_yen_to_yen(cols[2])
        if m_yen is not None:
            out.append(_build_rent_record(prefecture, city, station_name, "mansion", layout, m_yen, "homes_price"))
        if a_yen is not None:
            out.append(_build_rent_record(prefecture, city, station_name, "apartment", layout, a_yen, "homes_price"))
        return out

    rec = _parse_two_col_rent_row(cols, prefecture, city, station_name, "all", "homes_price")
    return [rec] if rec is not None else []


def parse_homes_rent_table(
    html_content: str,
    prefecture: str,
    city: str = "",
    station_name: str = "",
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_content, _HTML_PARSER)
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()

    for tb in soup.find_all("table"):
        rows = tb.find_all("tr")
        headers = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])] if rows else []
        for tr in rows:
            cols = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            for rec in _parse_homes_single_row(cols, headers, prefecture, city, station_name):
                key = (rec["city"], rec["station_name"], rec["building_type"], rec["layout_type"])
                if key not in seen:
                    seen.add(key)
                    results.append(rec)
    return results


def _extract_toushi_detail_metrics(soup: BeautifulSoup) -> tuple[float | None, float | None, float | None]:
    full_txt = soup.get_text(" ", strip=True)
    total_vac = None
    rental_vac = None
    gross_yield = None

    m_total = re.search(r"住宅全般\D{0,25}(\d{1,2}(?:\.\d{1,2})?)\s*[％%]", full_txt)
    if m_total:
        total_vac = float(m_total.group(1))

    m_rent = re.search(r"賃貸用住宅\D{0,25}(\d{1,2}(?:\.\d{1,2})?)\s*[％%]", full_txt)
    if m_rent:
        rental_vac = float(m_rent.group(1))

    for h in soup.find_all(["h2", "h3"]):
        htxt = h.get_text(" ", strip=True)
        if "の利回り" in htxt and h.parent:
            ptxt = h.parent.get_text(" ", strip=True)
            pcts = _PERCENT_RE.findall(ptxt)
            # 末尾の正のパーセント値が実勢表面利回り（その前は前月比）
            positive_pcts = [float(x) for x in pcts if not x.startswith(("+", "-")) and 1.0 <= float(x) <= 25.0]
            if positive_pcts:
                gross_yield = positive_pcts[-1]
                break
    return gross_yield, rental_vac, total_vac


def _compute_demand_supply_score(soup: BeautifulSoup) -> float | None:
    demand_sum = 0.0
    supply_sum = 0.0
    for tb in soup.find_all("table"):
        hdr = tb.find("tr")
        if not hdr or "検索回数" not in hdr.get_text(" ", strip=True):
            continue
        for tr in tb.find_all("tr")[1:]:
            pcts = [float(x) for x in _PERCENT_RE.findall(tr.get_text(" ", strip=True)) if float(x) >= 0.0]
            if len(pcts) >= 2:
                demand_sum += pcts[0]
                supply_sum += pcts[1]
        break
    if demand_sum > 0 and supply_sum > 0:
        return round(demand_sum / supply_sum, 2)
    return None


def _parse_toushi_prefecture_city_table(soup: BeautifulSoup, prefecture: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for tb in soup.find_all("table"):
        rows = tb.find_all("tr")
        if not rows or "空室率" not in rows[0].get_text(" ", strip=True):
            continue
        for tr in rows[1:]:
            cols = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if len(cols) < 2:
                continue
            m = _PERCENT_RE.search(cols[1])
            if not m or not cols[0]:
                continue
            results.append({
                "prefecture": prefecture.strip(),
                "city": cols[0].strip(),
                "station_name": "",
                "asset_type": "all",
                "expected_gross_yield": None,
                "expected_net_cap_rate": None,
                "standard_opex_ratio": Decimal("20.00"),
                "rental_vacancy_rate": Decimal(f"{float(m.group(1)):.2f}"),
                "total_vacancy_rate": None,
                "jgb_spread_bps": None,
                "demand_supply_score": None,
                "sample_count": None,
                "survey_period": "",
                "source": "homes_toushi",
            })
    return results


def parse_homes_toushi_page(
    html_content: str,
    prefecture: str,
    city: str = "",
    station_name: str = "",
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_content, _HTML_PARSER)
    gross_yield, rental_vac, total_vac = _extract_toushi_detail_metrics(soup)
    ds_score = _compute_demand_supply_score(soup)

    if gross_yield is not None or rental_vac is not None or total_vac is not None:
        net_cap = round(gross_yield * 0.80, 2) if gross_yield is not None else None
        return [{
            "prefecture": prefecture.strip(),
            "city": city.strip(),
            "station_name": normalize_station_label(station_name),
            "asset_type": "all",
            "expected_gross_yield": Decimal(f"{gross_yield:.2f}") if gross_yield is not None else None,
            "expected_net_cap_rate": Decimal(f"{net_cap:.2f}") if net_cap is not None else None,
            "standard_opex_ratio": Decimal("20.00"),
            "rental_vacancy_rate": Decimal(f"{rental_vac:.2f}") if rental_vac is not None else None,
            "total_vacancy_rate": Decimal(f"{total_vac:.2f}") if total_vac is not None else None,
            "jgb_spread_bps": None,
            "demand_supply_score": Decimal(f"{ds_score:.2f}") if ds_score is not None else None,
            "sample_count": None,
            "survey_period": "",
            "source": "homes_toushi",
        }]

    return _parse_toushi_prefecture_city_table(soup, prefecture)


def _classify_reit_sector(corp_name: str, sector_cell: str) -> str:
    if any(k in corp_name or k in sector_cell for k in _RESIDENTIAL_REIT_KEYWORDS) or sector_cell == "2":
        return "mansion"
    if any(k in corp_name or k in sector_cell for k in _COMMERCIAL_REIT_KEYWORDS) or sector_cell in ("1", "3", "4"):
        return "commercial"
    return "all"


def _parse_single_reit_row(cols: list[str]) -> tuple[str, float, float, float] | None:
    if len(cols) < 8 or not re.match(r"^\d{4}[A-Z]?$", cols[0].strip()):
        return None
    try:
        div_yield = float(cols[4].replace("%", "").strip())
        nav_ratio = float(cols[6].strip()) if cols[6].strip() else 0.92
        mkt_cap = float(cols[7].replace(",", "").strip())
    except ValueError:
        return None
    if div_yield <= 0 or mkt_cap <= 0:
        return None
    sector_col = cols[10].strip() if len(cols) > 10 else ""
    asset_type = _classify_reit_sector(cols[1].strip(), sector_col)
    # インプライドNCF利回り近似: 分配金利回り × (0.88 / max(0.65, min(1.30, NAV倍率)))
    clamped_nav = max(0.65, min(1.30, nav_ratio))
    implied_ncf = round(div_yield * (0.88 / clamped_nav), 2)
    return asset_type, div_yield, implied_ncf, mkt_cap


def parse_japan_reit_rimawari(
    html_content: str,
    jgb_10y_yield: float = 1.10,
) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_content, _HTML_PARSER)
    buckets: dict[str, list[tuple[float, float, float]]] = {"mansion": [], "commercial": [], "all": []}

    for tb in soup.find_all("table"):
        for tr in tb.find_all("tr"):
            cols = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            parsed = _parse_single_reit_row(cols)
            if parsed is None:
                continue
            atype, div_y, imp_ncf, mcap = parsed
            buckets["all"].append((div_y, imp_ncf, mcap))
            if atype in ("mansion", "commercial"):
                buckets[atype].append((div_y, imp_ncf, mcap))

    results: list[dict[str, Any]] = []
    opex_by_asset = {"mansion": Decimal("18.00"), "commercial": Decimal("22.00"), "all": Decimal("20.00")}
    for atype, items in buckets.items():
        if not items:
            continue
        total_w = sum(x[2] for x in items)
        w_ncf = sum(x[1] * x[2] for x in items) / total_w
        opex_ratio = float(opex_by_asset[atype]) / 100.0
        gross_est = w_ncf / (1.0 - opex_ratio)
        spread_bps = round((w_ncf - jgb_10y_yield) * 100)
        results.append({
            "prefecture": "全国",
            "city": "",
            "station_name": "",
            "asset_type": atype,
            "expected_gross_yield": Decimal(f"{gross_est:.2f}"),
            "expected_net_cap_rate": Decimal(f"{w_ncf:.2f}"),
            "standard_opex_ratio": opex_by_asset[atype],
            "rental_vacancy_rate": None,
            "total_vacancy_rate": None,
            "jgb_spread_bps": spread_bps,
            "demand_supply_score": None,
            "sample_count": len(items),
            "survey_period": "",
            "source": "japan_reit",
        })
    return results


def extract_portal_sublinks(html_content: str, base_url: str, pattern: str) -> list[tuple[str, str]]:
    """一覧ページ内の市区町村・駅詳細リンク (テキスト, URL) を重複排除して抽出する。"""
    from urllib.parse import urljoin

    soup = BeautifulSoup(html_content, _HTML_PARSER)
    rx = re.compile(pattern)
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=True):
        href = str(a.get("href", "")).strip()
        if not rx.search(href):
            continue
        full_url = urljoin(base_url, href)
        if full_url not in seen:
            seen.add(full_url)
            found.append((a.get_text(" ", strip=True), full_url))
    return found

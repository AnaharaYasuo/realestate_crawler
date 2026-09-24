# -*- coding: utf-8 -*-
"""
建物名寄せおよびマスタ解決リゾルバ。
同一マンションやアパートを名寄せし、建物マスタへの蓄積および未設定属性の自動補完を行う。
"""
import re
import unicodedata
import logging
from typing import Tuple, Dict, Any, Optional

from package.models.building_master import BuildingMaster

MAJOR_DEVELOPERS = [
    "三井不動産", "パークホームズ", "パークコート", "パークタワー", "パークシティ", "パークリュクス",
    "三菱地所", "ザ・パークハウス", "パークハウス",
    "住友不動産", "シティタワー", "シティハウス", "シティテラス", "グランドヒルズ",
    "野村不動産", "プラウド", "PROUD",
    "東京建物", "ブリリア", "Brillia",
    "東急不動産", "ブランズ", "BRANZ",
    "大京", "ライオンズマンション", "ザ・ライオンズ"
]

SUPER_GENERAL_CONTRACTORS = [
    "清水建設", "鹿島建設", "鹿島", "大林組", "竹中工務店", "大成建設"
]

MAJOR_CONTRACTORS = [
    "長谷工", "長谷工コーポレーション", "前田建設", "戸田建設", "安藤ハザマ",
    "三井住友建設", "熊谷組", "西松建設", "五洋建設", "東急建設", "フジタ", "鴻池組", "松井建設"
]


def normalize_building_name(raw_name: str) -> str:
    """
    建物名から部屋番号・階数表記・広告文言・全角スペースを除去し、名寄せ用キーを生成。
    """
    if not raw_name:
        return ""

    # 1. NFKC正規化 (全角英数・記号の統一)
    name = unicodedata.normalize("NFKC", raw_name).strip()

    # 2. 広告タグや囲み文字の除去 (【...】, （...）, (...), [ ... ])
    name = re.sub(r"【[^】]*】", "", name)
    name = re.sub(r"\[[^\]]*\]", "", name)
    name = re.sub(r"（[^）]*）", "", name)
    name = re.sub(r"\([^)]*\)", "", name)

    # 3. 部屋番号・階数表現の除去 (例: 2901号室, 301, 15階, 3F, 4階部分)
    name = re.sub(r"\d{1,6}号室?", "", name)
    name = re.sub(r"\d{1,5}階(?:部分)?", "", name)
    name = re.sub(r"\d{1,5}[Ff]", "", name)

    # 4. 中黒・カンマ・ドット・空白の除去
    name = re.sub(r"[・･\s\-_,.]+", "", name)

    return name.strip()


def normalize_building_address(raw_address: str) -> str:
    """
    住所から都道府県・市区町村・町丁目（○丁目まで）を抽出し、正規化キーを生成。
    例: 「東京都港区浜松町１丁目２－３ パークコート2901」 ➔ 「東京都港区浜松町1丁目」
    """
    if not raw_address:
        return ""

    addr = unicodedata.normalize("NFKC", raw_address).strip()

    # パターン1: ○丁目表記
    m_chome = re.search(r"^([^市区町村\n]{1,20}[市区町村][^丁目\n]{0,20}\d{1,5}丁目)", addr)
    if m_chome:
        return m_chome.group(1).replace(" ", "")

    # パターン2: ハイフン表記 (例: 浜松町1-2-3) ➔ 1丁目へ正規化
    m_hyphen = re.search(r"^([^市区町村\n]{1,20}[市区町村][^\d\-\n]{1,20})(\d{1,5})[\-－ー]", addr)
    if m_hyphen:
        return f"{m_hyphen.group(1)}{m_hyphen.group(2)}丁目".replace(" ", "")

    # パターン3: 町名まで (大字・小字)
    m_town = re.search(r"^([^市区町村\n]{1,20}[市区町村][^町男女東西南北\n]{0,20}[町男女東西南北])", addr)
    if m_town:
        return m_town.group(1).replace(" ", "")

    # フォールバック: 先頭30文字
    return addr[:30].replace(" ", "")


def classify_developer_tier(name: Optional[str]) -> str:
    """デベロッパーの格付け"""
    if not name:
        return "unknown"
    for dev in MAJOR_DEVELOPERS:
        if dev in name:
            return "major_reputable"
    return "standard"


def classify_contractor_tier(name: Optional[str]) -> str:
    """ゼネコンの格付け"""
    if not name:
        return "unknown"
    for super_c in SUPER_GENERAL_CONTRACTORS:
        if super_c in name:
            return "super_general"
    for maj_c in MAJOR_CONTRACTORS:
        if maj_c in name:
            return "major"
    return "local"


class BuildingResolver:
    """建物マスタ解決・名寄せエンジン"""

    def _create_master(
        self,
        norm_name: str,
        raw_name: str,
        norm_addr: str,
        raw_addr: str,
        prop_data: Dict[str, Any],
        dev_brand: Any,
        dev_tier: Any,
        contractor: Any,
        contractor_tier: Any,
    ) -> BuildingMaster:
        bm = BuildingMaster.objects.create(
            normalized_name=norm_name,
            raw_name=raw_name,
            normalized_address=norm_addr,
            raw_address=raw_addr,
            developer_brand=dev_brand or "",
            developer_tier=dev_tier,
            contractor_name=contractor or "",
            contractor_tier=contractor_tier,
            structure_type=prop_data.get("structure_type") or prop_data.get("structure") or "",
            earthquake_resistance=prop_data.get("earthquake_resistance") or "",
            total_units=prop_data.get("total_units"),
            total_floors=prop_data.get("total_floors"),
            built_year=prop_data.get("built_year"),
            built_month=prop_data.get("built_month"),
            elevator_available=prop_data.get("elevator_available"),
            elevator_count=prop_data.get("elevator_count"),
            hallway_type=prop_data.get("hallway_type") or "",
            garbage_disposal_24h=prop_data.get("garbage_disposal_24h"),
            management_company=prop_data.get("management_company") or "",
            management_type=prop_data.get("management_type") or "",
            manager_working_style=prop_data.get("manager_working_style") or "",
        )
        logging.info(f"BuildingResolver: Created new BuildingMaster [{norm_name}] in [{norm_addr}]")
        return bm

    def _enrich_master(
        self,
        bm: BuildingMaster,
        prop_data: Dict[str, Any],
        dev_brand: Any,
        contractor: Any,
    ) -> None:
        fields_to_check = [
            ("developer_brand", dev_brand),
            ("contractor_name", contractor),
            ("structure_type", prop_data.get("structure_type") or prop_data.get("structure")),
            ("earthquake_resistance", prop_data.get("earthquake_resistance")),
            ("total_units", prop_data.get("total_units")),
            ("total_floors", prop_data.get("total_floors")),
            ("elevator_available", prop_data.get("elevator_available")),
            ("hallway_type", prop_data.get("hallway_type")),
            ("garbage_disposal_24h", prop_data.get("garbage_disposal_24h")),
            ("management_type", prop_data.get("management_type")),
            ("manager_working_style", prop_data.get("manager_working_style")),
        ]
        updated = False
        for field_name, new_val in fields_to_check:
            curr_val = getattr(bm, field_name)
            if new_val is not None and (curr_val is None or curr_val == ""):
                setattr(bm, field_name, new_val)
                updated = True

        if updated:
            if bm.developer_brand and bm.developer_tier == "unknown":
                bm.developer_tier = classify_developer_tier(bm.developer_brand)
            if bm.contractor_name and bm.contractor_tier == "unknown":
                bm.contractor_tier = classify_contractor_tier(bm.contractor_name)
            bm.save()
            logging.info(f"BuildingResolver: Enriched existing BuildingMaster [{bm.normalized_name}]")

    def resolve_and_update(self, prop_data: Dict[str, Any]) -> Tuple[BuildingMaster, bool]:
        """
        物件データから建物マスタを検索または新規登録し、(BuildingMaster, created) を返す。
        既に登録済みの場合は、既存マスタに欠損している情報があれば最新データで補完する。
        """
        raw_name = prop_data.get("propertyName") or prop_data.get("buildingName") or prop_data.get("title") or ""
        raw_addr = prop_data.get("address") or prop_data.get("location") or ""

        norm_name = normalize_building_name(raw_name)
        norm_addr = normalize_building_address(raw_addr)

        if not norm_name or not norm_addr:
            return BuildingMaster(
                normalized_name=norm_name or "不明建物",
                raw_name=raw_name,
                normalized_address=norm_addr or "不明住所",
                raw_address=raw_addr
            ), False

        bm = BuildingMaster.objects.filter(normalized_name=norm_name, normalized_address=norm_addr).first()
        dev_brand = prop_data.get("developer_brand")
        contractor = prop_data.get("contractor_name")

        if not bm:
            created_bm = self._create_master(
                norm_name, raw_name, norm_addr, raw_addr, prop_data,
                dev_brand, classify_developer_tier(dev_brand),
                contractor, classify_contractor_tier(contractor)
            )
            return created_bm, True

        self._enrich_master(bm, prop_data, dev_brand, contractor)
        return bm, False

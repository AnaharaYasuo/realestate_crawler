# -*- coding: utf-8 -*-
"""クローラー会社別並行度スケジューリング制御モジュール

取扱物件数およびブラウザリソース負荷に応じた階層的並行度制御:
- 超大規模ポータル (HTTP: Homes): 5本 (大量物件を高速消化)
- 超大規模ポータル (Browser: Athome): 2本 (Playwright のメモリ枯渇・OOM防止)
- 大手仲介5社 (三井, 住友, 東急, 野村, ミサワ): 2本 (居住用+投資用のバランス消化)
- 中小・電鉄・ハウスメーカー (積水, 大和, 旭化成, 小田急等 17社): 1本 (同一会社内完全直列)
"""
from typing import Dict, List, Optional, Tuple

# 会社別の最大同時実行プロセス数
COMPANY_CONCURRENCY_LIMITS: Dict[str, int] = {
    # 超大規模ポータル (HTTP)
    "homes": 5,
    # 超大規模ポータル (Playwright)
    "athome": 3,
    # 大手仲介5社
    "mitsui": 2,
    "sumifu": 2,
    "tokyu": 2,
    "nomura": 2,
    "misawa": 2,
}

# 中小・電鉄・ハウスメーカー等のデフォルト並行数 (同一会社内直列)
DEFAULT_COMPANY_CONCURRENCY: int = 1


def get_company_concurrency_limit(company: str) -> int:
    """指定された会社の同時プロセス数上限を取得"""
    return COMPANY_CONCURRENCY_LIMITS.get(company.lower(), DEFAULT_COMPANY_CONCURRENCY)


def select_next_job(
    job_queue: List[Tuple[str, str]],
    active_company_counts: Dict[str, int],
    max_playwright_parallel: Optional[int] = None,
    current_playwright_count: int = 0,
    playwright_companies: Optional[List[str]] = None,
) -> Optional[Tuple[int, Tuple[str, str]]]:
    """
    キューの中から、会社別並行度上限およびPlaywright上限に空きのある次のジョブを選択して
    (キュー内のインデックス, (company, ptype)) を返す。
    実行可能なジョブが存在しない場合は None を返す。
    """
    if playwright_companies is None:
        playwright_companies = ["athome"]

    pw_set = {c.lower() for c in playwright_companies}

    for i, (company, ptype) in enumerate(job_queue):
        c_lower = company.lower()
        is_pw = c_lower in pw_set

        # Playwright 全体上限チェック
        if is_pw and max_playwright_parallel is not None:
            if current_playwright_count >= max_playwright_parallel:
                continue

        # 会社別上限チェック
        c_limit = get_company_concurrency_limit(c_lower)
        current_active = active_company_counts.get(c_lower, 0)

        if current_active < c_limit:
            return i, (company, ptype)

    return None

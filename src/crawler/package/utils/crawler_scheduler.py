# -*- coding: utf-8 -*-
"""クローラー会社別並行度スケジューリング制御モジュール

取扱物件数およびブラウザリソース負荷に応じた階層的並行度制御:
- 超大規模ポータル (HTTP: Homes): 5本 (大量物件を高速消化)
- 超大規模ポータル (Browser: Athome): 2本 (Playwright のメモリ枯渇・OOM防止)
- 大手仲介5社 (三井, 住友, 東急, 野村, ミサワ): 2本 (居住用+投資用のバランス消化)
- 中小・電鉄・ハウスメーカー (積水, 大和, 旭化成, 小田急等 17社): 1本 (同一会社内完全直列)
"""

# 会社別の最大同時実行プロセス数
COMPANY_CONCURRENCY_LIMITS: dict[str, int] = {
    # 超大規模ポータル (HTTP)
    "homes": 5,
    # 超大規模ポータル (Playwright)
    "athome": 3,
    # 大手仲介5社 (全種別同時並行実行を可能にするため5本に緩和)
    "mitsui": 5,
    "sumifu": 5,
    "tokyu": 5,
    "nomura": 5,
    "misawa": 5,
}

# 中小・電鉄・ハウスメーカー等のデフォルト並行数 (同一会社内直列)
DEFAULT_COMPANY_CONCURRENCY: int = 1


def get_company_concurrency_limit(company: str) -> int:
    """指定された会社の同時プロセス数上限を取得"""
    return COMPANY_CONCURRENCY_LIMITS.get(company.lower(), DEFAULT_COMPANY_CONCURRENCY)


def select_next_job(
    job_queue: list[tuple[str, str]],
    active_company_counts: dict[str, int],
    max_playwright_parallel: int | None = None,
    current_playwright_count: int = 0,
    playwright_companies: list[str] | None = None,
) -> tuple[int, tuple[str, str]] | None:
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


# 優先度判定用の主要仲介グループ (Issue #985)
# 最優先: 主要仲介大手 (mitsui, sumifu, tokyu, nomura, misawa) および 信託系 (smtrc, sumai1, mizuho), 大京 (daikyo)
MAJOR_BROKER_COMPANIES: set[str] = {
    "mitsui",
    "sumifu",
    "tokyu",
    "nomura",
    "misawa",
    "smtrc",
    "sumai1",
    "mizuho",
    "daikyo",
}


def calculate_job_priority(
    company: str, property_type: str, host_company: str | None = None
) -> tuple[int, int, int]:
    """
    ユーザー指定の優先度タプルを算出 (値が大きいほど優先):
    軸0 (自タスク主担当大手): host_company と一致する会社 -> 1, その他 -> 0 (最優先で全種別起動)
    軸1 (主要仲介大手): 大手仲介 (大手5社 + 信託3社 + 大京) -> 1, その他 -> 0
    軸2 (マンション優先): マンション (mansion) -> 1, その他種別 -> 0
    """
    c_lower = company.lower()
    p_lower = property_type.lower()

    is_host = 1 if host_company and c_lower == host_company.lower() else 0
    is_major_broker = 1 if c_lower in MAJOR_BROKER_COMPANIES else 0
    is_mansion = 1 if p_lower == "mansion" else 0

    return (is_host, is_major_broker, is_mansion)


def sort_jobs_by_priority(
    jobs: list[tuple[str, str]], host_company: str | None = None
) -> list[tuple[str, str]]:
    """
    各端末で「自タスク主担当大手 ➔ 主要仲介 ➔ マンション優先」で順次処理できるようソート (Issue #985)
    1. 自タスク主担当大手の全種別（マンション優先で開始直後に全種別並列実行）
    2. 空いたスロットに投入される他社ジョブ（大手仲介優先 ➔ マンション優先）
    """
    return sorted(
        jobs, key=lambda j: calculate_job_priority(j[0], j[1], host_company=host_company), reverse=True
    )

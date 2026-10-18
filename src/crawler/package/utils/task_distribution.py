# -*- coding: utf-8 -*-
"""
Cloud Run Jobs タスク分散ユーティリティ
"""
import datetime
import os

EXECUTION_DATE_ENV = "CRAWLER_EXECUTION_DATE"
STANDALONE_EXECUTION_PREFIX = "cloud-tasks-"


def get_task_config() -> tuple[int | None, int]:
    """環境変数から Cloud Run Jobs のタスク番号と総タスク数を取得"""
    raw_index = os.getenv("CLOUD_RUN_TASK_INDEX")
    raw_count = os.getenv("CLOUD_RUN_TASK_COUNT")
    
    task_index = int(raw_index) if raw_index is not None and raw_index.isdigit() else None
    task_count = int(raw_count) if raw_count is not None and raw_count.isdigit() else 1
    
    return task_index, task_count


def get_execution_id() -> str:
    """同一 Cloud Run Jobs 実行の全タスクで共通の実行名 (CLOUD_RUN_EXECUTION) を返す (ローカル実行時は空文字)"""
    return os.getenv("CLOUD_RUN_EXECUTION", "")


def _parse_pinned_date(raw: str) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        return None


def get_execution_date() -> datetime.date:
    """パイプライン起動時に固定した実行日 (CRAWLER_EXECUTION_DATE) を返す (未固定・不正値ならローカル日付)"""
    pinned = _parse_pinned_date(os.getenv(EXECUTION_DATE_ENV, ""))
    return pinned or datetime.datetime.now(datetime.timezone.utc).astimezone().date()


def pin_execution_date() -> datetime.date:
    """実行日を環境変数に固定し、日付を跨いでも子プロセスを含め同一の実行日を参照させる"""
    execution_date = get_execution_date()
    os.environ[EXECUTION_DATE_ENV] = execution_date.isoformat()
    return execution_date


MAJOR_5_COMPANIES = {"mitsui", "sumifu", "tokyu", "nomura", "misawa"}
PORTAL_COMPANIES = {"athome", "homes"}
TRUST_3_COMPANIES = {"smtrc", "sumai1", "mizuho"}
UNCRAWLED_COMPANIES = {"kenbiya", "ietan", "haseko", "adcast", "toho"}


def _assign_8_task_index(c_lower: str, p_lower: str) -> int:
    # 1. ポータルサイト
    if c_lower == "homes":
        return 5
    if c_lower == "athome":
        return 6 if p_lower == "mansion" else 7
    # 2. 投資用・事業用全般
    if p_lower in ("invest_kodate", "invest_apartment", "invest_building", "investment"):
        return 3
    # 3. 大手5社 居住用
    if c_lower in MAJOR_5_COMPANIES:
        mapping = {"mansion": 0, "kodate": 1, "tochi": 2}
        return mapping.get(p_lower, 3)
    # 4. 大京 (mansion -> Task 0, kodate/tochi -> Task 1)
    if c_lower == "daikyo":
        return 0 if p_lower == "mansion" else 1
    # 5. 信託3社 居住用 -> Task 2 (大手tochi枠に合流)
    if c_lower in TRUST_3_COMPANIES:
        return 2
    # 6. 中堅仲介 居住用・土地 -> Task 6 (athome mansion枠に合流)
    if c_lower in UNCRAWLED_COMPANIES:
        return 6
    # 7. 電鉄・ハウスメーカー系 居住用 (sekisui, afr, daiwa, totate, odakyu, sumirin, heim, rearie, keio, seibu, keikyu, sotetsu, keisei)
    #    mansion -> Task 7 (athomeその他枠に合流)
    #    kodate / tochi -> Task 4
    if p_lower == "mansion":
        return 7
    return 4


def _distribute_8_tasks(jobs: list[tuple[str, str]], task_index: int) -> list[tuple[str, str]]:
    """
    8タスク専用の決定論的マッピング (Issue #608, #851, #980 仕様):
    - Task 0: 大手仲介5社 mansion + daikyo mansion (6 jobs)
    - Task 1: 大手仲介5社 kodate + daikyo kodate / tochi (7 jobs)
    - Task 2: 大手仲介5社 tochi + 信託3社居住用 (14 jobs)
    - Task 3: 投資用・事業用全般 (18 jobs)
    - Task 4: 電鉄・ハウスメーカー系居住用 kodate & tochi (26 jobs)
    - Task 5: homes 全種別 (4 jobs)
    - Task 6: athome mansion + 中堅仲介全種別 (13 jobs)
    - Task 7: athome その他 + 電鉄・ハウスメーカー系 mansion (16 jobs)
    """
    task_map: dict[int, list[tuple[str, str]]] = {i: [] for i in range(8)}

    for company, ptype in jobs:
        idx = _assign_8_task_index(company.lower(), ptype.lower())
        task_map[idx].append((company, ptype))

    return task_map[task_index]


BIG_3_COMPANIES = ["mitsui", "sumifu", "tokyu"]


def _distribute_3_tasks(jobs: list[tuple[str, str]], task_index: int) -> list[tuple[str, str]]:
    """
    3タスク専用の決定論的マッピング (Issue #985 仕様):
    三大仲介（三井・住友・東急）を各インスタンスの専任主担当とし、
    全種別を先頭で並列実行。空いたスロットに残りのジョブを均等投入する。
    - Task 0: 三井不動産リアルティ全種別 (5 jobs) + その他ジョブ (modulo 0)
    - Task 1: 住友不動産販売全種別 (5 jobs) + その他ジョブ (modulo 1)
    - Task 2: 東急リバブル全種別 (5 jobs) + その他ジョブ (modulo 2)
    """
    host_company = BIG_3_COMPANIES[task_index]
    host_jobs = [j for j in jobs if j[0].lower() == host_company]
    # 自タスクの主担当はマンションを先頭にソート
    host_jobs_sorted = sorted(host_jobs, key=lambda j: 1 if j[1].lower() == "mansion" else 0, reverse=True)

    other_jobs = [j for j in jobs if j[0].lower() not in BIG_3_COMPANIES]
    assigned_others = [j for i, j in enumerate(other_jobs) if i % 3 == task_index]

    return host_jobs_sorted + assigned_others


def distribute_jobs(
    jobs: list[tuple[str, str]],
    task_index: int | None = None,
    task_count: int = 1
) -> list[tuple[str, str]]:
    """
    全ジョブリストをタスクインデックスに応じて分割して返す。
    task_count == 3 の場合は三大仲介（三井・住友・東急）専任マッピングを適用 (Issue #985)。
    task_count == 8 の場合は決定論的マッピングを適用 (Issue #608, #980)。
    それ以外の task_count の場合は従来の Modulo 分割を適用。
    task_count <= 1 または task_index is None の場合は全ジョブを返す。
    """
    if task_count <= 1 or task_index is None:
        return list(jobs)
    
    if task_index < 0 or task_index >= task_count:
        raise ValueError(f"task_index ({task_index}) out of range for task_count ({task_count})")

    if task_count == 3:
        return _distribute_3_tasks(jobs, task_index)

    if task_count == 8:
        return _distribute_8_tasks(jobs, task_index)
    
    return [job for i, job in enumerate(jobs) if i % task_count == task_index]


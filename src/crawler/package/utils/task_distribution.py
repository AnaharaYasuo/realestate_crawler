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


def _distribute_8_tasks(jobs: list[tuple[str, str]], task_index: int) -> list[tuple[str, str]]:
    """
    8タスク専用の決定論的マッピング (Issue #608 仕様):
    - Task 0: 大手仲介5社 mansion
    - Task 1: 大手仲介5社 kodate
    - Task 2: 大手仲介5社 tochi
    - Task 3: 大手仲介5社 + 信託3社 + odakyu/sumirin の投資用
    - Task 4: 信託3社居住用 + 電鉄・ハウスメーカー系17社居住用
    - Task 5: homes 全種別
    - Task 6: athome mansion
    - Task 7: athome その他種別
    """
    task_map: dict[int, list[tuple[str, str]]] = {i: [] for i in range(8)}

    for company, ptype in jobs:
        c_lower = company.lower()
        p_lower = ptype.lower()

        if c_lower == "homes":
            task_map[5].append((company, ptype))
        elif c_lower == "athome":
            if p_lower == "mansion":
                task_map[6].append((company, ptype))
            else:
                task_map[7].append((company, ptype))
        elif c_lower in MAJOR_5_COMPANIES:
            if p_lower == "mansion":
                task_map[0].append((company, ptype))
            elif p_lower == "kodate":
                task_map[1].append((company, ptype))
            elif p_lower == "tochi":
                task_map[2].append((company, ptype))
            else:
                task_map[3].append((company, ptype))
        elif p_lower in ("invest_kodate", "invest_apartment", "investment"):
            task_map[3].append((company, ptype))
        else:
            task_map[4].append((company, ptype))

    return task_map[task_index]


def distribute_jobs(
    jobs: list[tuple[str, str]],
    task_index: int | None = None,
    task_count: int = 1
) -> list[tuple[str, str]]:
    """
    全ジョブリストをタスクインデックスに応じて分割して返す。
    task_count == 8 の場合は Issue #608 の決定論的マッピングを適用。
    それ以外の task_count の場合は従来の Modulo 分割を適用。
    task_count <= 1 または task_index is None の場合は全ジョブを返す。
    """
    if task_count <= 1 or task_index is None:
        return list(jobs)
    
    if task_index < 0 or task_index >= task_count:
        raise ValueError(f"task_index ({task_index}) out of range for task_count ({task_count})")

    if task_count == 8:
        return _distribute_8_tasks(jobs, task_index)
    
    return [job for i, job in enumerate(jobs) if i % task_count == task_index]


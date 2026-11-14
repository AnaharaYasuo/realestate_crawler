"""GitHub Issue-Driven Auto-Heal Syncer & Lifecycle Manager (Issue #1412).

Bridges daily Cloud Run anomaly instructions (`auto_heal/latest_instruction.json` in GCS)
into deduplicated GitHub Issues (`auto-heal` label) using zero LLM API tokens, and provides
deterministic CLI subcommands (`--list-actionable`, `--record-attempt`, `--escalate`,
`--mark-criteria-done`) for the Antigravity Scheduled Automation self-healing loop.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Protocol

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

AUTO_HEAL_LABEL = "auto-heal"
NEEDS_HUMAN_LABEL = "auto-heal:needs-human"
DEFAULT_GCS_BUCKET = "realestate-images-sumifu-prod"
DEFAULT_GCS_KEY = "auto_heal/latest_instruction.json"
DEFAULT_MAX_ATTEMPTS = 2

_KEY_MARKER_RE = re.compile(r"<!-- auto-heal-key:([^\s>]+) -->")
_ATTEMPTS_MARKER_RE = re.compile(r"<!-- auto-heal-attempts:(\d+) -->")
_CLOSING_REF_RE = re.compile(r"\b(?:close[sd]?|fixe?[sd]?|resolve[sd]?)\s{1,5}#(\d+)\b", re.IGNORECASE)
_TITLE_REF_RE = re.compile(r"^\[#(\d+)\]")


class GhClientProtocol(Protocol):
    """Protocol abstracting GitHub CLI interactions for testability."""

    def ensure_labels(self) -> None: ...
    def list_open_auto_heal_issues(self) -> list[dict[str, Any]]: ...
    def list_open_prs(self) -> list[dict[str, Any]]: ...
    def get_issue(self, number: int) -> dict[str, Any]: ...
    def create_issue(self, title: str, body: str, labels: list[str]) -> int: ...
    def update_issue_body(self, number: int, body: str) -> None: ...
    def comment_issue(self, number: int, body: str) -> None: ...
    def update_labels(self, number: int, add_labels: list[str], remove_labels: list[str]) -> None: ...
    def close_issue(self, number: int, comment: str) -> None: ...


class SubprocessGhClient:
    """Production GitHub CLI (`gh`) adapter."""

    def _run_gh(self, args: list[str]) -> str:
        res = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        return res.stdout.strip()

    def ensure_labels(self) -> None:
        self._run_gh(
            [
                "label",
                "create",
                AUTO_HEAL_LABEL,
                "--color",
                "D93F0B",
                "--description",
                "Automated parser self-healing target queue",
                "--force",
            ]
        )
        self._run_gh(
            [
                "label",
                "create",
                NEEDS_HUMAN_LABEL,
                "--color",
                "B60205",
                "--description",
                "Auto-heal circuit breaker tripped; requires manual investigation",
                "--force",
            ]
        )

    def _normalize_labels(self, raw_labels: list[Any]) -> list[str]:
        normalized: list[str] = []
        for item in raw_labels:
            if isinstance(item, dict) and item.get("name"):
                normalized.append(str(item["name"]))
            elif isinstance(item, str):
                normalized.append(item)
        return normalized

    def list_open_auto_heal_issues(self) -> list[dict[str, Any]]:
        out = self._run_gh(
            [
                "issue",
                "list",
                "--state",
                "open",
                "--limit",
                "200",
                "--json",
                "number,title,body,state,labels,comments",
            ]
        )
        items = json.loads(out) if out else []
        matched: list[dict[str, Any]] = []
        for iss in items:
            labels = self._normalize_labels(iss.get("labels", []))
            if AUTO_HEAL_LABEL in labels or NEEDS_HUMAN_LABEL in labels:
                iss["labels"] = labels
                matched.append(iss)
        return matched

    def list_open_prs(self) -> list[dict[str, Any]]:
        out = self._run_gh(
            [
                "pr",
                "list",
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                "number,title,body,headRefName",
            ]
        )
        return json.loads(out) if out else []

    def get_issue(self, number: int) -> dict[str, Any]:
        out = self._run_gh(
            [
                "issue",
                "view",
                str(number),
                "--json",
                "number,title,body,state,labels,comments",
            ]
        )
        data = json.loads(out)
        data["labels"] = self._normalize_labels(data.get("labels", []))
        return data

    def create_issue(self, title: str, body: str, labels: list[str]) -> int:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tf:
            tf.write(body)
            tmp_path = tf.name
        try:
            cmd = ["issue", "create", "--title", title, "--body-file", tmp_path]
            for lbl in labels:
                cmd.extend(["--label", lbl])
            url = self._run_gh(cmd)
            tail = url.rstrip("/").rsplit("/", 1)[-1]
            return int(tail)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def update_issue_body(self, number: int, body: str) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tf:
            tf.write(body)
            tmp_path = tf.name
        try:
            self._run_gh(["issue", "edit", str(number), "--body-file", tmp_path])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def comment_issue(self, number: int, body: str) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as tf:
            tf.write(body)
            tmp_path = tf.name
        try:
            self._run_gh(["issue", "comment", str(number), "--body-file", tmp_path])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def update_labels(self, number: int, add_labels: list[str], remove_labels: list[str]) -> None:
        cmd = ["issue", "edit", str(number)]
        for ad in add_labels:
            cmd.extend(["--add-label", ad])
        for rm in remove_labels:
            cmd.extend(["--remove-label", rm])
        self._run_gh(cmd)

    def close_issue(self, number: int, comment: str) -> None:
        self.comment_issue(number, comment)
        self._run_gh(["issue", "close", str(number)])


def _slugify_step(step_name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", step_name.lower()).strip("-")
    return cleaned[:40] or "step"


def group_instruction_targets(instruction: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Aggregate targets from instruction JSON by `(company, property_type)` key."""
    groups: dict[str, dict[str, Any]] = {}
    for target in instruction.get("targets", []) or []:
        reason = str(target.get("reason") or "")
        if "[source_data_invalid]" in reason:
            continue
        company = str(target.get("company") or "unknown").strip()
        prop_type = str(target.get("property_type") or "unknown").strip()
        key = f"{company}:{prop_type}"
        entry = groups.setdefault(
            key,
            {
                "company": company,
                "property_type": prop_type,
                "total_frequency": 0,
                "sample_urls": [],
                "reasons": [],
            },
        )
        entry["total_frequency"] += int(target.get("frequency") or 1)
        url = str(target.get("url") or "").strip()
        if url and url not in entry["sample_urls"] and len(entry["sample_urls"]) < 5:
            entry["sample_urls"].append(url)
        if reason and reason not in entry["reasons"] and len(entry["reasons"]) < 5:
            entry["reasons"].append(reason)

    for step in instruction.get("failed_pipeline_steps", []) or []:
        step_str = str(step).strip()
        if not step_str:
            continue
        slug = _slugify_step(step_str)
        key = f"pipeline:{slug}"
        groups[key] = {
            "company": "pipeline",
            "property_type": slug,
            "total_frequency": 1,
            "sample_urls": [],
            "reasons": [f"パイプラインステップ失敗: {step_str}"],
        }

    return groups


def build_issue_body(key: str, group: dict[str, Any], instruction: dict[str, Any]) -> str:
    """Build a CI-Governance-4-Gate compliant GitHub Issue body for an auto-heal target."""
    generated_at = str(instruction.get("generated_at") or "unknown")
    ai_summary = str(instruction.get("ai_summary") or "(AI要約なし)").strip()
    if len(ai_summary) > 1200:
        ai_summary = ai_summary[:1200] + "\n...(省略)..."

    urls_md = "\n".join(f"- {u}" for u in group.get("sample_urls", [])) or "- (対象URLなし / パイプライン異常)"
    reasons_md = "\n".join(f"- `{r}`" for r in group.get("reasons", [])) or "- `(理由未記録)`"

    return (
        f"<!-- auto-heal-key:{key} -->\n"
        f"<!-- auto-heal-attempts:0 -->\n"
        f"<!-- auto-heal-sync-ts:{generated_at} -->\n\n"
        f"## 自動検知されたパーサー・データ整合性異常 (`{group['company']}` / `{group['property_type']}`)\n\n"
        f"- **検知タイムスタンプ (UTC)**: `{generated_at}`\n"
        f"- **累計異常件数 (Frequency)**: `{group['total_frequency']}` 件\n"
        f"- **対象キー**: `{key}`\n\n"
        f"### 検知エラー理由\n{reasons_md}\n\n"
        f"### 代表サンプルURL\n{urls_md}\n\n"
        f"### Gemini 事前診断サマリー抜粋\n{ai_summary}\n\n"
        f"## 自動修復のゴール・完了定義 (Definition of Done)\n"
        f"- **最終ゴールは `production` ブランチへのマージ完了および本番デプロイ（`Deploy Production`）の成功確認である。**\n"
        f"- PRの作成のみ、Auto-merge の設定のみ、あるいは `master` ブランチへのマージ時点で作業を終了してはならない。\n"
        f"- Stage 1（作業ブランチ ➔ `master` PR の全CI合格・マージ）に続き、Stage 2（`master` ➔ `production` リリースPR のCI合格・マージ）および GitHub Actions `Deploy Production` ワークフローの成功（Cloud Run デプロイ ＆ 異常物件再クロール起動）まで一貫して監視・完遂すること。\n\n"
        f"## アクセプタンスクライテリア (受入基準)\n"
        f"- [ ] SDD正本ドキュメント（対象サイトの仕様書 `docs/2_crawlers/sites/` または運用設計書）を先行確認・同期更新する\n"
        f"- [ ] 不整合・パース失敗を再現・防止する単体テスト（`src/crawler/tests/unit/`）を追加・更新し合格させる\n"
        f"- [ ] 対象パーサー／セレクタを最小差分で修正し、実URL検証・`test_architecture_harness.py`・`check_local_sonar.py --diff` をすべて通過させる\n"
        f"- [ ] `master` へのPRマージ完了後、`production` ブランチへのリリースPRマージおよび本番デプロイ（`Deploy Production`）完了まで見届ける\n"
    )


def _extract_issue_key(body: str) -> str | None:
    match = _KEY_MARKER_RE.search(body or "")
    return match.group(1) if match else None


def _has_sync_timestamp(issue: dict[str, Any], generated_at: str) -> bool:
    if not generated_at:
        return True
    marker = f"<!-- auto-heal-sync-ts:{generated_at} -->"
    if marker in str(issue.get("body") or ""):
        return True
    for cmt in issue.get("comments", []) or []:
        if marker in str(cmt.get("body") or ""):
            return True
    return False


def _collect_issue_numbers_with_open_prs(open_prs: list[dict[str, Any]]) -> set[int]:
    linked: set[int] = set()
    for pr in open_prs:
        body = str(pr.get("body") or "")
        for m in _CLOSING_REF_RE.finditer(body):
            linked.add(int(m.group(1)))
        title = str(pr.get("title") or "")
        tm = _TITLE_REF_RE.match(title)
        if tm:
            linked.add(int(tm.group(1)))
    return linked


def _build_refresh_comment(key: str, group: dict[str, Any], generated_at: str) -> str:
    urls_md = "\n".join(f"- {u}" for u in group.get("sample_urls", [])) or "- (URLなし)"
    reasons_md = "\n".join(f"- `{r}`" for r in group.get("reasons", [])) or "- `(理由未記録)`"
    return (
        f"<!-- auto-heal-sync-ts:{generated_at} -->\n"
        f"🔄 **日次テレメトリ自動更新 (`{generated_at}` UTC)**\n"
        f"- 対象 `{key}` の最新検知件数: **{group['total_frequency']} 件**\n"
        f"- 最新エラー理由:\n{reasons_md}\n"
        f"- 最新サンプルURL:\n{urls_md}\n"
    )


def _sync_single_active_group(
    key: str,
    group: dict[str, Any],
    instruction: dict[str, Any],
    existing_by_key: dict[str, dict[str, Any]],
    gh: GhClientProtocol,
    *,
    dry_run: bool,
    summary: dict[str, list[int]],
) -> None:
    generated_at = str(instruction.get("generated_at") or "")
    existing = existing_by_key.get(key)
    if existing is None:
        title = f"[Auto-Heal] {group['company']}/{group['property_type']} パーサー不整合・取得異常の自動修復"
        body = build_issue_body(key, group, instruction)
        if dry_run:
            logger.info("[DRY-RUN] Would create Issue: %s", title)
            return
        num = gh.create_issue(title=title, body=body, labels=[AUTO_HEAL_LABEL])
        summary["created"].append(num)
        logger.info("Created auto-heal Issue #%d for %s", num, key)
        return

    num = int(existing["number"])
    labels = set(existing.get("labels", []))
    if NEEDS_HUMAN_LABEL in labels:
        summary["skipped_needs_human"].append(num)
        logger.info("Skipping Issue #%d (%s): circuit breaker %s active.", num, key, NEEDS_HUMAN_LABEL)
        return

    if _has_sync_timestamp(existing, generated_at):
        return

    comment = _build_refresh_comment(key, group, generated_at)
    if dry_run:
        logger.info("[DRY-RUN] Would append telemetry comment on Issue #%d", num)
        return
    gh.comment_issue(num, comment)
    summary["updated"].append(num)


def _close_resolved_issues(
    active_keys: set[str],
    existing_by_key: dict[str, dict[str, Any]],
    linked_pr_issues: set[int],
    generated_at: str,
    gh: GhClientProtocol,
    *,
    dry_run: bool,
    summary: dict[str, list[int]],
) -> None:
    if not generated_at:
        return
    for key, iss in existing_by_key.items():
        num = int(iss["number"])
        labels = set(iss.get("labels", []))
        if key in active_keys or AUTO_HEAL_LABEL not in labels or num in linked_pr_issues:
            continue
        msg = (
            f"✅ 最新の日次整合性スキャン（`{generated_at}` UTC）において、`{key}` の未解決異常は **0件** となりました。"
            f" 自動解決が確認されたため本 Issue をクローズします。"
        )
        if dry_run:
            logger.info("[DRY-RUN] Would auto-close resolved Issue #%d (%s)", num, key)
            continue
        gh.close_issue(num, msg)
        summary["closed_resolved"].append(num)
        logger.info("Auto-closed resolved Issue #%d (%s)", num, key)


def sync_instruction_to_issues(
    instruction: dict[str, Any],
    gh: GhClientProtocol,
    *,
    dry_run: bool = False,
) -> dict[str, list[int]]:
    """Synchronize `auto_heal_instruction.json` payload into deduplicated GitHub Issues."""
    if not dry_run:
        gh.ensure_labels()

    open_issues = gh.list_open_auto_heal_issues()
    open_prs = gh.list_open_prs()
    linked_pr_issues = _collect_issue_numbers_with_open_prs(open_prs)

    existing_by_key: dict[str, dict[str, Any]] = {}
    for iss in open_issues:
        key = _extract_issue_key(str(iss.get("body") or ""))
        if key and key not in existing_by_key:
            existing_by_key[key] = iss

    active_groups = group_instruction_targets(instruction)
    summary: dict[str, list[int]] = {
        "created": [],
        "updated": [],
        "skipped_needs_human": [],
        "closed_resolved": [],
    }

    for key, group in active_groups.items():
        _sync_single_active_group(
            key,
            group,
            instruction,
            existing_by_key,
            gh,
            dry_run=dry_run,
            summary=summary,
        )

    _close_resolved_issues(
        set(active_groups.keys()),
        existing_by_key,
        linked_pr_issues,
        str(instruction.get("generated_at") or ""),
        gh,
        dry_run=dry_run,
        summary=summary,
    )
    return summary


def list_actionable_issues(gh: GhClientProtocol) -> dict[str, Any]:
    """Return OPEN `auto-heal` issues ready for Antigravity Scheduled Automation."""
    open_issues = gh.list_open_auto_heal_issues()
    linked_pr_issues = _collect_issue_numbers_with_open_prs(gh.list_open_prs())

    actionable: list[dict[str, Any]] = []
    for iss in open_issues:
        num = int(iss["number"])
        labels = set(iss.get("labels", []))
        if NEEDS_HUMAN_LABEL in labels or AUTO_HEAL_LABEL not in labels or num in linked_pr_issues:
            continue
        body = str(iss.get("body") or "")
        attempts_match = _ATTEMPTS_MARKER_RE.search(body)
        attempts = int(attempts_match.group(1)) if attempts_match else 0
        actionable.append(
            {
                "number": num,
                "title": iss.get("title", ""),
                "key": _extract_issue_key(body) or "",
                "attempts": attempts,
            }
        )
    actionable.sort(key=lambda x: x["number"])
    return {"count": len(actionable), "issues": actionable}


def escalate_issue_to_human(number: int, reason: str, gh: GhClientProtocol) -> dict[str, Any]:
    """Trip circuit breaker on an Issue: swap `auto-heal` -> `auto-heal:needs-human`."""
    gh.update_labels(number, add_labels=[NEEDS_HUMAN_LABEL], remove_labels=[AUTO_HEAL_LABEL])
    gh.comment_issue(
        number,
        (
            f"⚠️ **自動修復サーキットブレーカー作動 (`{NEEDS_HUMAN_LABEL}`)**\n\n"
            f"- 理由: {reason}\n"
            f"- 無限リトライおよび不要なトークン消費を防止するため、`{AUTO_HEAL_LABEL}` ラベルを解除しました。\n"
            f"- 人手または対話セッションでの確認後、再試行する場合は `{AUTO_HEAL_LABEL}` ラベルを再付与してください。"
        ),
    )
    return {"issue_number": number, "escalated": True, "reason": reason}


def record_heal_attempt(
    number: int,
    gh: GhClientProtocol,
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> dict[str, Any]:
    """Increment `auto-heal-attempts` counter on an Issue and escalate if exceeding `max_attempts`."""
    iss = gh.get_issue(number)
    body = str(iss.get("body") or "")
    match = _ATTEMPTS_MARKER_RE.search(body)
    current = int(match.group(1)) if match else 0
    next_attempts = current + 1

    new_marker = f"<!-- auto-heal-attempts:{next_attempts} -->"
    if match:
        updated_body = _ATTEMPTS_MARKER_RE.sub(new_marker, body, count=1)
    else:
        updated_body = f"{new_marker}\n{body}"
    gh.update_issue_body(number, updated_body)

    if next_attempts > max_attempts:
        escalate_issue_to_human(
            number,
            f"自動修復の最大試行回数（{max_attempts}回）を超過したため自動停止しました（試行 {next_attempts} 回目）。",
            gh,
        )
        return {"issue_number": number, "attempts": next_attempts, "escalated": True}

    return {"issue_number": number, "attempts": next_attempts, "escalated": False}


def _check_single_checkbox_line(line: str) -> str:
    leading_len = len(line) - len(line.lstrip())
    prefix = line[:leading_len]
    rest = line[leading_len:]
    if not rest.startswith(("- [ ] ", "* [ ] ")):
        return line
    tail = rest[6:]
    if not tail.strip():
        return line
    bullet = rest[0]
    return f"{prefix}{bullet} [x] {tail}"


def _check_markdown_boxes_outside_fences(markdown_text: str) -> str:
    in_fence = False
    out_lines: list[str] = []
    for line in markdown_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        out_lines.append(line if in_fence else _check_single_checkbox_line(line))
    trailing_nl = "\n" if markdown_text.endswith("\n") else ""
    return "\n".join(out_lines) + trailing_nl


def mark_issue_criteria_done(number: int, gh: GhClientProtocol) -> dict[str, Any]:
    """Check off all Acceptance Criteria checkboxes outside code blocks on an Issue."""
    iss = gh.get_issue(number)
    body = str(iss.get("body") or "")
    updated = _check_markdown_boxes_outside_fences(body)
    if updated != body:
        gh.update_issue_body(number, updated)
    return {"issue_number": number, "criteria_checked": True}


def pull_instruction_from_gcs_direct(
    bucket_name: str = DEFAULT_GCS_BUCKET,
    blob_key: str = DEFAULT_GCS_KEY,
) -> dict[str, Any] | None:
    """Fetch `auto_heal/latest_instruction.json` directly from GCS without requiring Django/DB."""
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_key)
    if not blob.exists():
        logger.info("GCS blob gs://%s/%s does not exist yet.", bucket_name, blob_key)
        return None
    raw = blob.download_as_text(encoding="utf-8")
    return json.loads(raw) if raw else None


def _load_instruction_for_cli(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.instruction_file:
        path = Path(args.instruction_file)
        if not path.exists():
            logger.info("Instruction file %s not found; nothing to sync.", path)
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    if args.pull_from_gcs:
        bucket = os.environ.get("GCS_BUCKET_NAME", DEFAULT_GCS_BUCKET)
        return pull_instruction_from_gcs_direct(bucket_name=bucket, blob_key=DEFAULT_GCS_KEY)

    default_local = Path(__file__).resolve().parents[4] / "Temp" / "auto_heal_instruction.json"
    if default_local.exists():
        return json.loads(default_local.read_text(encoding="utf-8"))
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="GitHub Issue-Driven Auto-Heal Syncer & Lifecycle CLI")
    parser.add_argument("--pull-from-gcs", action="store_true", help="Pull latest_instruction.json from GCS")
    parser.add_argument("--instruction-file", type=str, help="Path to local auto_heal_instruction.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview issue sync without mutating GitHub")
    parser.add_argument("--list-actionable", action="store_true", help="Output JSON of actionable auto-heal issues")
    parser.add_argument("--record-attempt", type=int, metavar="ISSUE_NUM", help="Increment attempt counter on issue")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS, help="Max auto-heal attempts")
    parser.add_argument("--escalate", type=int, metavar="ISSUE_NUM", help="Escalate issue to auto-heal:needs-human")
    parser.add_argument("--reason", type=str, default="自動修復不能な変更を検知しました。", help="Escalation reason")
    parser.add_argument("--mark-criteria-done", type=int, metavar="ISSUE_NUM", help="Check off acceptance criteria")
    args = parser.parse_args(argv)

    gh = SubprocessGhClient()

    if args.list_actionable:
        print(json.dumps(list_actionable_issues(gh), ensure_ascii=False))
        return 0
    if args.record_attempt:
        print(json.dumps(record_heal_attempt(args.record_attempt, gh, max_attempts=args.max_attempts), ensure_ascii=False))
        return 0
    if args.escalate:
        print(json.dumps(escalate_issue_to_human(args.escalate, args.reason, gh), ensure_ascii=False))
        return 0
    if args.mark_criteria_done:
        print(json.dumps(mark_issue_criteria_done(args.mark_criteria_done, gh), ensure_ascii=False))
        return 0

    instruction = _load_instruction_for_cli(args)
    if instruction is None:
        logger.info("No auto-heal instruction available; exiting cleanly.")
        return 0

    result = sync_instruction_to_issues(instruction, gh, dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

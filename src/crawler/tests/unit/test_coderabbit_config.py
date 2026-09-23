"""
CodeRabbit 設定および未解決レビューコメント判定ロジックの単体テスト。
Issue #215: feat: CodeRabbit 自動コードレビュー導入と未解決レビューコメントのマージブロック強制
Issue #311: feat: CodeRabbit 自動レビューを初回PRオープン時のみに制限
Issue #345: feat: CodeRabbit レビュー対象から docs / *.md を除外
Issue #363: feat: CodeRabbit に path_instructions を追加しパス別レビュー観点を強化
"""
import os
import yaml


def get_repo_root():
    """リポジトリルートディレクトリを探索して返す"""
    cur = os.path.abspath(os.path.dirname(__file__))
    for _ in range(6):
        if os.path.exists(os.path.join(cur, "src")) and (
            os.path.exists(os.path.join(cur, ".git")) or os.path.exists(os.path.join(cur, ".coderabbit.yaml")) or os.path.exists(os.path.join(cur, "Taskfile.yml"))
        ):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    # フォールバック
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))


def _load_coderabbit_config():
    """リポジトリルートの .coderabbit.yaml を読み込み辞書で返す"""
    repo_root = get_repo_root()
    config_path = os.path.join(repo_root, ".coderabbit.yaml")
    assert os.path.exists(config_path), f".coderabbit.yaml が存在しません: {config_path}"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert isinstance(config, dict), ".coderabbit.yaml の内容が辞書形式ではありません"
    return config


def test_coderabbit_yaml_exists_and_valid():
    """リポジトリルートに .coderabbit.yaml が存在し、YAMLとして正常にパースできることを検証"""
    config = _load_coderabbit_config()

    # 必須パラメータの検証
    assert config.get("language") == "ja-JP", "language は ja-JP に設定されている必要があります"

    reviews = config.get("reviews", {})
    assert reviews.get("profile") == "chill", "reviews.profile は chill に設定されている必要があります"
    assert reviews.get("request_changes_workflow") is True, "reviews.request_changes_workflow は true に設定されている必要があります"

    auto_review = reviews.get("auto_review", {})
    assert auto_review.get("enabled") is True, "reviews.auto_review.enabled は true に設定されている必要があります"
    # Issue #311: 後続pushでの再レビュー連鎖を防ぐため、増分自動レビューは無効
    assert auto_review.get("auto_incremental_review") is False, (
        "reviews.auto_review.auto_incremental_review は false（初回PRオープンのみ）である必要があります"
    )

    base_branches = auto_review.get("base_branches", [])
    assert "master" in base_branches, "auto_review.base_branches に master が含まれている必要があります"
    # Issue #376: production 宛てリリースPRでの重複AIレビュー・誤指摘防止のため除外
    assert "production" not in base_branches, (
        "Issue #376: auto_review.base_branches から production が除外されている必要があります"
    )
    # Issue #383: release: PR や自動化 PR に対する完全抑止設定
    ignore_keywords = auto_review.get("ignore_title_keywords", [])
    assert "release:" in ignore_keywords, "ignore_title_keywords に release: が含まれている必要があります"
    ignore_users = auto_review.get("ignore_usernames", [])
    assert "github-actions[bot]" in ignore_users, "ignore_usernames に github-actions[bot] が含まれている必要があります"


    tone = config.get("tone_instructions", "")
    assert len(tone) > 0, "tone_instructions が設定されている必要があります"
    # Issue #363: 長期保守・スケーラビリティ観点を tone に両方含める
    assert "スケーラビリティ" in tone, "tone_instructions にスケーラビリティの観点が含まれている必要があります"
    assert "長期保守" in tone, "tone_instructions に長期保守の観点が含まれている必要があります"


def test_coderabbit_excludes_docs_and_markdown():
    """Issue #345: docs/ および *.md が path_filters で除外され、markdownlint が無効であること"""
    config = _load_coderabbit_config()
    reviews = config.get("reviews", {})
    path_filters = reviews.get("path_filters", [])

    assert "!docs/**" in path_filters, "path_filters に !docs/** が含まれている必要があります"
    assert "!**/*.md" in path_filters, "path_filters に !**/*.md が含まれている必要があります"

    tools = reviews.get("tools", {})
    markdownlint = tools.get("markdownlint", {})
    assert markdownlint.get("enabled") is False, (
        "Markdown 非対象化に合わせ tools.markdownlint.enabled は false である必要があります"
    )


def test_coderabbit_path_instructions_cover_critical_areas():
    """Issue #363: path_instructions がパーサー・テスト・スクリプト向けに定義されていること"""
    config = _load_coderabbit_config()
    reviews = config.get("reviews", {})
    path_instructions = reviews.get("path_instructions", [])

    assert isinstance(path_instructions, list), "path_instructions はリストである必要があります"
    assert len(path_instructions) >= 3, "path_instructions は少なくとも3件必要です"

    by_path = {
        entry.get("path"): entry.get("instructions", "")
        for entry in path_instructions
        if isinstance(entry, dict)
    }
    required_guidance = {
        "src/crawler/package/parser/**": ("Base", "フィールド名", "セレクター"),
        "src/crawler/tests/**": ("受入基準", "アサーション", "ミューテーション"),
        "src/crawler/scripts/**": ("タイムアウト", "0件", "ハードコード"),
    }
    missing = set(required_guidance) - set(by_path)
    assert not missing, f"path_instructions に必須パスが不足しています: {missing}"

    for path, keywords in required_guidance.items():
        instructions = by_path[path]
        assert isinstance(instructions, str) and len(instructions.strip()) > 0, (
            f"path_instructions の instructions が空です: {path}"
        )
        for keyword in keywords:
            assert keyword in instructions, (
                f"path_instructions[{path}] に '{keyword}' の観点が含まれていません"
            )


def test_review_thread_evaluation_logic():
    """未解決レビュースレッド判定ロジックの検証"""
    def evaluate_threads(threads):
        """
        GraphQL reviewThreads ノードのリストを受け取り、
        未解決の会話が存在するかどうかを評価する。
        """
        unresolved = [t for t in threads if not t.get("isResolved", False)]
        return {
            "can_merge": len(unresolved) == 0,
            "unresolved_count": len(unresolved),
            "unresolved_threads": unresolved,
        }

    # 1. 全て解決済みのケース
    all_resolved = [
        {"id": "t1", "isResolved": True, "path": "src/api.py", "line": 10},
        {"id": "t2", "isResolved": True, "path": "src/parser.py", "line": 50},
    ]
    res1 = evaluate_threads(all_resolved)
    assert res1["can_merge"] is True
    assert res1["unresolved_count"] == 0

    # 2. 未解決の指摘が残っているケース
    has_unresolved = [
        {"id": "t1", "isResolved": True, "path": "src/api.py", "line": 10},
        {"id": "t2", "isResolved": False, "path": "src/parser.py", "line": 50},
    ]
    res2 = evaluate_threads(has_unresolved)
    assert res2["can_merge"] is False
    assert res2["unresolved_count"] == 1
    assert res2["unresolved_threads"][0]["id"] == "t2"

    # 3. コメントが0件のケース
    res3 = evaluate_threads([])
    assert res3["can_merge"] is True
    assert res3["unresolved_count"] == 0

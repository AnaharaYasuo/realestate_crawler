# 要件定義: クローラーDB監視DNS堅牢化 & ML再学習インポート修復 (Issue #892)

## 1. 背景と課題
- ローカル環境または高並行実行時（`CRAWLER_PARALLEL` で多数ジョブが同時にHTTP通信を実施）、Docker Embedded DNS (127.0.0.11) に一時的な名前解決タイムアウトが発生することがある。
- `run_all_crawlers.py` 内の `DbLivenessMonitor` は定期的に `db:3306` の TCP 疎通を確認するが、ホスト名 `db` の名前解決が DNS 一時タイムアウト (`[Errno -3] Temporary failure in name resolution`) により失敗すると、DB 自体は正常稼働しているにもかかわらず連続 3 回失敗で Fast-Fail 緊急停止が誤発動し、全 103 ジョブ中 12 ジョブ程度でクロール全体が中断してしまう。
- `package/ml/train.py` はコマンドラインから直接 `python /app/src/crawler/package/ml/train.py` で実行された場合、冒頭で `setup_env` による `PYTHONPATH` 解決が行われていないため `ModuleNotFoundError: No module named 'package'` を引き起こし、即死スキップされる。
- ローカル本番実行における過負荷を抑止するため、安全な並行度設定を担保する。

## 2. 要件仕様
1. **DB疎通監視のDNS耐性強化**:
   - `resolve_db_endpoint()` または `DbLivenessMonitor` において、接続先ホスト名（`db` 等）を初回解決時に IP アドレスへキャッシュ・固定し、プローブ時は名前解決を行わず IP 直結で疎通監視を行う。
   - 万が一名前解決に失敗した場合も、直前の有効な IP キャッシュを保持してフォールバックし、DNS の一時的揺らぎによる Fast-Fail 誤発動を物理的に防止する。
2. **ML 再学習エントリのインポート堅牢化**:
   - `package/ml/train.py` 冒頭に `setup_env` 読み込み処理を追加し、カレントディレクトリに関わらず `package` 以下のモジュールを確実にインポート可能とする。
3. **ローカル並行度の安全化**:
   - ローカル Docker 環境におけるデフォルト `CRAWLER_PARALLEL` を過負荷とならない安全な値（5）に調整可能とし、リソース枯渇を防ぐ。

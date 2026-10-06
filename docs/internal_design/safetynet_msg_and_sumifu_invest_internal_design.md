# 内部設計: Safety-Net通知文言改善および住友不動産投資用戸建てセレクター修復

## 1. モジュール変更詳細
### 1.1 `src/crawler/scripts/ensure_resources_stopped.py`
- `check_and_stop_proxysql_instance`:
  - Line 802 付近:
    ```python
    info_msg = (
        f":information_source: *【Safety-Net】クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました*\n"
        f"・プロジェクト: `{project_id}`\n"
        f"・稼働ジョブ: {job_desc}\n"
        f"・ProxySQL: `{instance_name}` (RUNNING)"
    )
    ```
- `check_and_stop_proxysql_mig`:
  - Line 1044 付近:
    ```python
    info_msg = (
        f":information_source: *【Safety-Net】クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました*\n"
        f"・プロジェクト: `{project_id}`\n"
        f"・稼働ジョブ: {job_desc}\n"
        f"・MIGサイズ: `{current_target_size}` 台"
    )
    ```

### 1.2 `config/selectors/sumifu.yaml`
- `investment` 定義の直後に、同じ構造を持つ `invest_kodate` および `invest_apartment` を追記する。
- これにより、`SelectorLoader.load('sumifu', 'invest_kodate')` および `SelectorLoader.load('sumifu', 'invest_apartment')` が直接キーヒットし、KeyError を防止する。

### 1.3 `src/crawler/package/parser/sumifuParser.py`
- `SumifuInvestmentKodateParser`:
  - `property_type = 'invest_kodate'` を明示（基底クラス `SumifuInvestmentParserBase` では `'investment'` になっていたため、`invest_kodate` を設定することで種別固有のロードおよびハンドリングが可能）。
- `SumifuInvestmentApartmentParser`:
  - `property_type = 'invest_apartment'` を明示。

## 2. テスト設計
1. `src/crawler/tests/test_ensure_resources_stopped.py`:
   - `assert "正常実行中のためProxySQLの起動を継続しました" in mock_slack.call_args[0][0]`
2. `src/crawler/tests/unit/test_crawler_safety_net_hourly_664.py`:
   - `assert "クローラー/MLパイプライン正常実行中のためProxySQLの起動を継続しました" in mock_slack.call_args[0][0]`
3. `src/crawler/tests/unit/test_sumifu_invest_selectors.py`:
   - `SelectorLoader.load('sumifu', 'invest_kodate')` および `invest_apartment` が例外なくロード可能であること。
   - `SumifuInvestmentKodateParser("")` が正常にインスタンス化され、`property_type` が正しく設定されていること。

# 新規サイトクローラー・パーサー実装ハンドブック (New Site Implementation Guide)

新規不動産サイトのクローラーおよびパーサーを開発する際、**既存の全22社以上と同等の高水準（Getter構造、堅牢な正規化、動的二段階検証、パース処理時間制限、ミューテーションテスト通過）で一発作成するための標準手順書**である。

---

## 1. 開発ライフサイクル全体像

```
[Step 1] サイト構造事前調査 (site_survey_checklist.md に沿って仕様確認)
   ↓
[Step 2] 仕様ドキュメント作成 (docs/2_crawlers/sites/<site>.md)
   ↓
[Step 3] テストコード先行作成 (TDD: test_parser_abstract_methods.py への追加 & 単体テスト)
   ↓
[Step 4] パーサークラス実装 (Baseクラス継承・Getterメソッド・specsキャッシュ)
   ↓
[Step 5] クローラー設定登録 (シードURL・ルート定義・ページネーション)
   ↓
[Step 6] 共通品質検証 (/regression-test: 3件スモーク➔20件拡張生HTML検証 ＆ ミューテーション)
```

---

## 2. クラス階層と継承ルール

すべてのパーサーは、`src/crawler/package/parser/baseParser.py` で定義されている **種別ごとの Base クラス** を必ず継承しなければならない。

### 継承対応表

| 対象物件種別 | 継承すべき Base クラス | 主な責務・抽出項目 |
| :--- | :--- | :--- |
| **中古マンション** | `MansionParserBase` | 物件名、価格、所在地、交通、専有面積、間取り、築年月、階数、構造、総戸数、管理費、修繕積立金、バルコニー |
| **戸建て** | `KodateParserBase` | 物件名、価格、所在地、交通、土地面積、建物面積、間取り、築年月、階数、構造、建ぺい率、容積率、接道 |
| **土地** | `TochiParserBase` | 物件名、価格、所在地、交通、土地面積、建ぺい率、容積率、地目、権利、用途地域、接道、幅員、間口、現況、引渡 |
| **投資用物件** | `InvestmentParserBase` | 物件名、価格、所在地、想定利回り、満室時年収、構造、築年月、総戸数、敷地面積、延床面積、現況 |

```python
# 実装例: src/crawler/package/parser/exampleParser.py
from src.crawler.package.parser.baseParser import MansionParserBase, KodateParserBase, TochiParserBase

class ExampleMansionParser(MansionParserBase):
    """Example社のマンションパーサー"""
    ...
```

---

## 3. Getter メソッド化 ＆ `specs` キャッシュ規約

### ① `specs` のワンタイム解析とキャッシュ
詳細ページのテーブル（`table` / `dl`）は、初回呼び出し時に `response._cached_specs` へ辞書としてキャッシュする。Getter ごとに DOM を再パースしてはならない（NFR-001 性能基準）。

```python
def _get_specs(self, response: BeautifulSoup) -> dict[str, str]:
    if hasattr(response, "_cached_specs"):
        return response._cached_specs

    specs = {}
    # table.detail-table tr を走査して th: td を抽出
    for row in response.select("table.property-spec tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            key = th.get_text(strip=True)
            val = td.get_text(" ", strip=True)
            specs[key] = val

    response._cached_specs = specs
    return specs
```

### ② 文字列表記（`_str`）と数値型（変換後）の二段階設計
パース探索ロジックの二重化を防ぐため、**文字列を確定させる `get_<field>_str()`** を先に実装し、**型変換を行う `get_<field>()` はそれを呼び出して `converter` を通す**。

```python
def get_tochi_menseki_str(self, response: BeautifulSoup) -> str:
    specs = self._get_specs(response)
    for key in ["土地面積", "敷地面積", "区画面積"]:
        if key in specs and specs[key]:
            return specs[key]
    return ""

def get_tochi_menseki(self, response: BeautifulSoup) -> Decimal | None:
    s = self.get_tochi_menseki_str(response)
    return converter.parse_menseki(s) if s else None
```

---

## 4. 厳格な抽出とフォールバックの禁止

- **必須項目が取得できない場合の対処**:
  - 物件名、価格、所在地、面積、間取り等の重要項目が DOM から欠落している場合、`"-"` や `"未設定"` などの安易なデフォルト値（フォールバック）を埋めてはならない。
  - 抽出失敗時は例外（`ParserException`）を発生させ、エラーページとして保存（`docs/error_pages/`）する。
- **掲載終了の検知**:
  - ページ内に「掲載終了」「成約済」の文言がある場合は、`is_listing_ended(response) -> bool` で検知し、正常終了として扱う（Slack エラーアラートの抑止）。

---

## 5. 新規サイト作成時の品質保証（必須パス基準）

新規パーサーを作成した際は、以下の 4 大ゲートをすべてパスしなければならない。

1. **抽象メソッド実装テスト (`test_parser_abstract_methods.py`)**:
   - 定義した新パーサークラスをテスト対象リストに追加し、`@abstractmethod` の未実装漏れが 0 件であることを確認。
2. **生HTML動的二段階検証**:
   - ローカルの静的モックだけでなく、公開中のアクティブ生HTMLを直接取得して検証する。
   - **第1段階（スモーク）**: 最新 3 件を取得し、必須フィールドが全件パースできること。
   - **第2段階（拡張）**: 追加 17 件（計 20 件）を取得し、表記揺れやエッジケースでのクラッシュがないこと。
3. **処理時間アサーション**:
   - 静的パース（`aiohttp`）: **1物件あたり 1,000ms（1秒）以内**。
   - 動的パース（`Playwright`）: **1物件あたり 5,000ms（5秒）以内**。
4. **ミューテーションテスト通過**:
   - `python src/crawler/scripts/run_mutation_testing.py --pr-mode --threshold=80`
   - Level 1 (Data Mutation): 故意のデータ欠落検知率 **100%**。
   - Level 2 (Code Mutation): 変異コードのテストキル率 **80% 以上**。

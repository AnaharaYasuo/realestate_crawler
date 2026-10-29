# データモデル設計ルール (src/crawler/package/models/AGENTS.md)

本ディレクトリ（`src/crawler/package/models/`）配下のモデルクラスを定義・変更する際は、以下の不変条件を厳守すること。

## 1. 種別別リファレンス基底モデルの継承義務
すべての物件モデルクラスは、`PropertyBaseModel` を直接継承するのではなく、[`base.py`](base.py) に定義された以下の4つの種別別リファレンス基底モデルのいずれかを継承しなければならない：
- **区分マンション**: `MansionBaseModel`
- **戸建て**: `KodateBaseModel`
- **土地**: `TochiBaseModel`
- **収益・投資用物件（一棟マンション・一棟アパート・投資用戸建等）**: `InvestmentBaseModel`

## 2. 共通フィールド名およびデータ型の完全統一（Schema Type Invariants）
[`docs/3_data_models/field_naming_standards.md`](../../../../docs/3_data_models/field_naming_standards.md) に従い、全社モデル間で同一の意味を持つ項目は同一フィールド名・同一 Django/Peewee フィールド型を使用すること。基底モデルで定義済みの共通フィールドをサブクラスで異なる型（例: `IntegerField` / `DecimalField` と `TextField` の混在）で再定義することを厳禁とする：
- `price`: `IntegerField`
- `kenpei`（建ぺい率）: `IntegerField(null=True, blank=True)` または数値整合型（文字列 `TextField` での再定義禁止）
- `youseki`（容積率）: `IntegerField(null=True, blank=True)` または数値整合型（文字列 `TextField` での再定義禁止）
- `tatemono_menseki` / `tochi_menseki` / `senyu_menseki`: `DecimalField`
- `rimawari`（利回り）: `DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)`

## 3. 新規サイト追加時の統合レジストリ連携
新規モデルを追加した場合は、必ず [`src/crawler/package/site_registry.py`](../site_registry.py)（および自動配線検証ゲート `test_architecture_harness.py`）を通じて ML 学習ローダー（`ml/constants.py`）とディスパッチャへ漏れなく登録すること。

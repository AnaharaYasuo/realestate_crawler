# 全サイト全モデル欠損データ（traffic等）包括的復旧 外部設計書 (Issue #913)

## 1. 概要
本設計書は、全物件モデルに対する欠損交通データ（traffic）の包括的復旧バッチのCLI仕様、合成規則、対象モデル抽出条件を定義する。

## 2. CLI インターフェース仕様
```bash
# ドライラン（件数調査のみ、DB変更なし）
python src/crawler/scripts/maintenance/restore_missing_traffic_data.py

# 実更新モード（本番環境またはCI/CD環境のみ実行可能）
python src/crawler/scripts/maintenance/restore_missing_traffic_data.py --execute
```

## 3. 合成仕様（Traffic Synthesis Specification）
1. **鉄道ルート (Route 1〜5)**:
   - フォーマット: `{railway} {station} 徒歩{minutes}分`
   - 数値の分数（`railwayWalkMinute`）が存在する場合は `徒歩{n}分`。
   - 文字列の分数（`railwayWalkMinuteStr`）のみ存在する場合はその文字列を付加。
   - 沿線・駅の双方が空の場合はスキップ。
2. **バス停ルート (Route 1〜5)**:
   - フォーマット: `バス停 {busStation} 徒歩{minutes}分`
   - バス停名が空の場合はスキップ。
3. **区切り文字**:
   - 複数ルートが存在する場合は ` / ` で結合。
   - 重複要素は排除。

## 4. 対象モデル選定基準
- Django の `apps.get_models()` によりロードされたモデルのうち、
  1. フィールドに `traffic` が定義されていること
  2. フィールドに `station1`〜`5` または `railway1`〜`5` が1つ以上定義されていること
  3. 抽象モデルではないこと

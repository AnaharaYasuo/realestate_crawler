# 物件評価名寄せ（重複判定）および親子関係整合性ポリシー

## 1. 概要
同一物件が複数の不動産仲介会社やポータルサイトから重複して流通・クローリングされた場合、`PropertyEvaluation` モデルの `duplicate_of`（自己参照ForeignKey）を用いて名寄せ管理を行う。
本ドキュメントは、親子関係の決定順序（登録最古優先）、循環参照（Cycles）の絶対防止、および多段チェーン（Multi-hop Chains）の平坦化（Flattening）に関する設計仕様を定義する。

## 2. 親子関係決定原則（登録日時・ID最古優先原則）

### 原則
* **「登録順（`PropertyEvaluation.id` が小さい方）を常に親（オリジナル）」** とする。
* 後から登録された重複物件（IDが大きい方）を子（`duplicate_of = 親`）として紐付ける。
* これにより、`child.duplicate_of.id < child.id` が常に成立する。

### 数学的非循環保証
* すべての参照において `parent.id < child.id` が厳格に満たされるため、`A.duplicate_of = B` かつ `B.duplicate_of = A`（$B.id < A.id$ かつ $A.id < B.id$）となる循環参照は数学的に発生し得ない。
* 自己参照（$A.id == A.id$）も `exclude(id=new_eval.id)` および ID 不等号検査により完全に排除される。

## 3. 多段チェーン防止（ルート親直結 / Flattening）
* 類似度 0.85 以上と判定された候補レコード（`cand`）が、既に別のレコードの子（`cand.duplicate_of IS NOT NULL`）である場合、親を再帰的に遡って最上位の「ルート親（Root Parent）」を取得する。
* 子は中間ノードではなく、常にルート親に直接リンク（`new_eval.duplicate_of = root_parent`）する。
* これにより、$A \rightarrow B \rightarrow C$ のような多段チェーンを防止し、常に深さ1のフラットな親子構造を維持する。

## 4. アルゴリズム仕様 (`package/utils/deduplication.py`)

1. **`get_root_parent(eval_rec: PropertyEvaluation) -> PropertyEvaluation`**:
   * `eval_rec.duplicate_of` を再帰的に辿り、最上位の親レコードを返却する。
   * 安全のため `visited_ids` セットを保持し、万一過去データに循環が存在しても無限ループを防止して最小IDのレコードを返す。
2. **`find_duplicate_property(new_eval: PropertyEvaluation, new_prop=None) -> Optional[PropertyEvaluation]`**:
   * 同一種別の候補レコードを探索（自己は除外）。
   * 類似度 $\ge 0.85$ の候補を発見した場合、`root = get_root_parent(cand)` を取得。
   * `new_eval.id` が存在し、かつ `root.id >= new_eval.id` の場合は、`new_eval` の方が古いため `new_eval` は子になり得ない（スキップまたは親側を更新）。
   * `root.id < new_eval.id`（または `new_eval.id` が未採番 `None`）の場合のみ、`root` を親として返却する。

## 5. 既存データの是正
* 過去の並行推論等によって混入した既存DB内の循環参照（12件）および多段チェーン（448件）は、クレンジングバッチ（`scripts/maintenance/resolve_duplicate_evaluations.py`）によりルート親（最小ID）へ一括フラット化・解消する。

# 仕様書: Issue #1315 二段階スクリーニングにおけるAI定性レポート生成関数の引数補完と生成レポート再利用の実装

## 1. 目的
`send_recommendations.py` の二段階スクリーニング（Stage 2: AI定性評価）において、未評価候補に対する `generate_professional_and_danchou_report` 呼び出しに必須引数が正しく渡されず `TypeError` が発生していた問題を解消する。
また、Stage 2 で生成されたレポート結果をインメモリキャッシュ（`report_cache`）に保持し、最終配信時の `_build_recommendation_msg` へ渡すことで、重複生成・API消費を完全に防止する。

## 2. 実装詳細
1. **物件基本情報の共通抽出関数 `_extract_property_display_info(prop, eval_rec)` の用意**:
   - `asking_price_man`, `pred_price`, `ptype_jp`, `address`, `access` を一元的に抽出。
2. **Stage 2 での安全なレポート生成とキャッシュ**:
   - `generate_professional_and_danchou_report(eval_rec=eval_rec, prop=prop, ptype_jp=ptype_jp, asking_price_man=asking_price_man, pred_price=pred_price, address=address, access=access)` を呼び出し。
   - 生成結果を `report_cache[eval_rec.property_url] = report_data` に保存。
3. **最終配信メッセージ構築時の再利用**:
   - `_build_recommendation_msg(eval_rec, prop, reason, p_name, report_data=report_cache.get(eval_rec.property_url))` により、生成済みレポートを直接利用。

## 3. テスト計画
- `test_two_stage_recommendations.py` に、Stage 2 の呼び出しで `generate_professional_and_danchou_report` に正しい引数が渡されることのモック検証を追加。

# クローラー自動修復・バリデーション境界是正 内部設計書 (Issue #940)

## 1. モジュール改修仕様

### 1.1 `src/crawler/package/utils/data_validator.py`
1. **遅延インポート化**:
   - モジュール先頭の `from package.models.evaluation import PropertyEvaluation` を削除し、`tag_property_integrity` 関数内に移動。
2. **間取りハイフン・未定許容**:
   ```python
   if has_madori_field:
       madori_val = getattr(item, "madori", None)
       if _blank(madori_val) and str(madori_val or "").strip() not in ("-", "―", "ー", "未定", "相談"):
           reasons.append(ERR_MISSING_MADORI)
   ```
3. **低価格許容キーワード拡充**:
   - `specific_keywords` に `"ヘルス・ケア"`, `"ヘルスケア"`, `"リゾート"`, `"その他用地"`, `"倉庫用地"`, `"別荘地"`, `"分譲地"`, `"再建築不可"`, `"借地権"` を追加。
4. **投資物件の面積チェック緩和**:
   - `area <= 5.0` の場合、`is_invest` かつ利回り（`grossYield > 0`）または賃料（`rent > 0`）があれば面積異常エラーを抑制。

### 1.2 `src/crawler/package/parser/tokyuParser.py`
- `TokyuKodateParser._parsePropertyDetailPage`:
  ```python
  specs = self._scrape_specs(response)
  item.madori = self._parseMadori(response, specs)
  item.tatemonoMensekiStr = self._parseTatemonoMensekiStr(response, specs)
  item.tatemonoMenseki = self._parseTatemonoMenseki(response, specs)
  item.tochiMensekiStr = self._parseTochiMensekiStr(response, specs)
  item.tochiMenseki = self._parseTochiMenseki(response, specs)
### 1.3 `src/crawler/package/parser/mitsuiParser.py`
- `MitsuiParser._parseTrafficLines`:
  - 従来の `_getValueByLabel` および `_get_specs` に加え、三井新UIのCSSセレクター（`.property-traffic`, `.traffic-detail`, `.access-detail` 等）およびテーブル要素全走査フォールバックを追加。


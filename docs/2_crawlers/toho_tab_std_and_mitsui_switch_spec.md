# Toho `div.tab_std` Spec Extraction & Mitsui `PropertyTypeSwitch` URL Guard Bypass (#1750)

## 1. 背景・課題
- `www.toho-house.co.jp` の物件詳細ページは `<dl><dt><dd>` ではなく `<div class="tab_std">` 配下の `div.hyo_t`（項目名）/ `div.hyo_txt`（値）でスペックを保持しているため、`TohoBaseParser._get_specs` で `address` 等が空になり `StrictExtractionFailed` が発生していた。
- `www.rehouse.co.jp` において `_maybe_switch_parser` による `PropertyTypeSwitch` が成功しても、切替先パーサー（`MitsuiMansionParser` / `MitsuiTochiParser` / `MitsuiKodateParser`）の URL パスガードが `_switched_from_property_type` を考慮せず `SkipPropertyException` を送出していた。

## 2. 仕様
- `TohoBaseParser._get_specs` は `<dl>` に加えて `div.tab_std` (`div.hyo_t` / `div.hyo_txt`) からもスペック辞書を抽出する。
- `MitsuiMansionParser` / `MitsuiTochiParser` / `MitsuiKodateParser` は `getattr(item, "_switched_from_property_type", None)` が設定されている場合、URL パスガードをバイパスして切替後種別でパース・登録する。

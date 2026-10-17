# 東急リバブル投資用戸建て conditions-use=other からの判別抽出 内部設計書 (Issue #965)

## 1. 概要
`src/crawler/package/api/tokyu_investment.py` および `src/crawler/package/parser/tokyuParser.py` における内部実装仕様を定義する。

## 2. モジュール別変更仕様

### 2.1 `src/crawler/package/api/tokyu_investment.py`
`ParseTokyuInvestKodateStartAsync` の開始URLリストを更新する。
```python
class ParseTokyuInvestKodateStartAsync(ParseTokyuInvestStartAsyncBase):
    urlList = ["https://www.livable.co.jp/fudosan-toushi/tatemono-bukken-all/conditions-use=other/"]
```

### 2.2 `src/crawler/package/parser/tokyuParser.py`
`TokyuInvestmentKodateParser._parse_nextjs_property_item(self, item)` を改修し、判別アルゴリズムを実装する。

#### 判別定数定義
```python
EXCLUDED_INVEST_KODATE_LABELS = {
    'ホテル', '旅館', '車庫・立体駐車場', '車庫', '立体駐車場',
    '店舗', '事務所', '倉庫', '工場', '寮・社宅', '医療施設',
    'マンション一棟売', 'アパート一棟売', 'ビル一棟', 'リゾートマンション・別荘'
}
```

#### 判別ステップ
1. **URLチェック**:
   - `item.get('detailUrl')` が存在しない、または `_is_non_property_href` に該当する場合は `None`。
2. **ラベル判定**:
   - `item.get('labelList')` 内のすべての辞書要素から `listText` および `detailText` を取得。
   - `/` で分割した各単語を `label_parts` 集合に追加。
   - `EXCLUDED_INVEST_KODATE_LABELS` との積集合が存在する場合 ➔ スキップ (`return None`)。
   - `その他(土地・建物)` が含まれていない場合 ➔ スキップ (`return None`)。
3. **スペック判定 (`propertyDetail`)**:
   - リスト内要素を走査：
     - 戸数: `re.search(r'(\d+)戸', text)` で戸数を抽出。数値が2以上の場合はスキップ (`return None`)。
     - 階数: `re.search(r'地上(\d+)階建', text)` で地上階数を抽出。階数が4以上の場合はスキップ (`return None`)。
4. **ListItem返却**:
   - 価格を取得し、`ListItem(url=full_url, price=price)` を返却。

### 2.3 詳細ページ二次ガード (`_parsePropertyDetailPage`)
- 既存の `TokyuInvestmentKodateParser._parsePropertyDetailPage` のガード：
  - 物件名・タイトル等の除外キーワードチェック（マンション、区分、一室、ビル、店舗、アパート、ホテル等）。
  - 土地面積欠損ガード（戸建て投資として成立しないためスキップ）。

## 3. テスト設計
`src/crawler/tests/unit/test_tokyu_invest_kodate_other_filter.py` を新設：
1. **除外ラベルテスト**: ホテル、旅館、ビル一棟、マンション一棟売、車庫等のラベルが付与されたアイテムが `None` となること。
2. **複数戸除外テスト**: 戸数 `6戸` や `14戸` のアパート物件が `None` となること。
3. **高層階除外テスト**: `地上4階建`、`地上7階建` 等のビル物件が `None` となること。
4. **戸建て採択テスト**: `その他(土地・建物)` かつ 戸数 `'-'` / `1戸`、`地上2階建` / `地上3階建` の物件が正常に `ListItem` として抽出されること。

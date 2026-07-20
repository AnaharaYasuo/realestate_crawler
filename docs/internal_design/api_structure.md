# クローラー API 構造ドキュメント

このプロジェクトのクローラーは、単一のプロセスが全てを実行するのではなく、各階層が次の階層のAPI（クローラー）を呼び出す**連鎖的な（再帰的な）分散アーキテクチャ**を採用しています。

## 1. 概要

エントリーポイント（`Start`）がキックされると、そこから詳細ページの取得まで、APIが次のAPIをHTTPリクエスト経由で呼び出すことで処理が進行します。
これにより、各階層の処理をCloud Functions等のサーバーレス環境に分散させることが容易な構造になっています。

## 2. 処理フロー (Mermaid)

以下は `Sumifu` (住友不動産販売) のマンション検索を例にした処理フローです。

```mermaid
graph TD
    User((User / Scheduler)) -->|Call| Main[Main Entry Point]
    Main -->|POST /api/sumifu/mansion/start| StartAPI[Start API<br>ParseSumifuMansionStartAsync]
    
    subgraph "Recursive API Chain"
        StartAPI -->|1. Parse Top Page| RegionList{Region List}
        RegionList -->|POST /api/sumifu/mansion/region| RegionAPI[Region API<br>ParseSumifuMansionRegionFuncAsync]
        
        RegionAPI -->|2. Parse Region Page| AreaList{Area List}
        AreaList -->|POST /api/sumifu/mansion/area| AreaAPI[Area API<br>ParseSumifuMansionAreaFuncAsync]
        
        AreaAPI -->|3. Parse Area Page| PropertyList{Property List}
        PropertyList -->|POST /api/sumifu/mansion/list| ListAPI[List API<br>ParseSumifuMansionListFuncAsync]
        
        ListAPI -->|4. Parse List Page| DetailURLList{Detail URLs}
        DetailURLList -->|POST /api/sumifu/mansion/detail| DetailAPI[Detail API<br>ParseSumifuMansionDetailFuncAsync]
        
        DetailAPI -->|5. Parse Detail Page| DB[(Database / File)]
    end

    note_right_ApiCall[HTTP Post Request]
    RegionAPI -.->|Environment Check| LocalOrCloud{IS_CLOUD?}
    LocalOrCloud -- Yes --> CloudFunc[Cloud Functions]
    LocalOrCloud -- No --> LocalHost[Localhost:8000]
```

## 3. 実装パラメータ

非同期通信および並列実行に関する主要な設定値です（`package/api/api.py` にて定義）。

| パラメータ名 | 設定値 | 説明 |
| :--- | :--- | :--- |
| `FIRE_AND_FORGET_TIMEOUT` | 3.0 秒 | 次の API をトリガーする際のタイムアウト。接続確立で成功。 |
| `DEFAULT_PARARELL_LIMIT` | 2 | 通常の API 呼び出しにおける並列数制限。 |
| `DETAIL_PARARELL_LIMIT` | 6 | 物件詳細 (`DetailFunc`) 取得時の並列数制限。 |
| `TCP_CONNECTOR_LIMIT` | 100 | TCP コネクタの最大同時接続数。 |

## 4. 環境切り替え

システムは実行環境を自動判定し、API 呼び出し先を切り替えます。
- **ローカル環境**: `localhost:8000` へリクエストを送ります。
- **クラウド環境**: `os.getenv('IS_CLOUD')` が真の場合、Cloud Functions 等のクラウドエンドポイントへリクエストを送ります。

## 5. 投資用物件の取得戦略

投資用物件は**アパート（Apartment）**と**戸建て（Kodate）**の2種類を別々に取得する必要があります。各サイトの構造に応じて、以下の戦略を使い分けます。

### 5.1 基本戦略

#### 戦略A: 検索条件による絞り込み（優先）

物件一覧を表示する際に、検索条件で物件種別を指定して絞り込みます。

**利点**:
- 不要な物件データの取得を回避
- 処理効率が高い
- サーバー負荷が低い

**実装方法**:
- URLパラメータで物件種別を指定（例: `?type=apartment`, `?type=kodate`）
- 開始URLを物件種別ごとに分ける
- API呼び出し時に物件種別パラメータを渡す

#### 戦略B: 一覧からのフィルタリング（フォールバック）

検索条件で絞り込みができない場合、一覧ページから目的の種別のみをピックアップします。

**実装方法**:
1. 一覧ページの全物件を取得
2. 各物件の種別を判定:
   - **URLパターン**: `/apartment/`, `/kodate/` などのパス
   - **物件種別ラベル**: 一覧上の「アパート」「戸建て」表示
   - **メタデータ**: data属性やclass名
3. 目的の種別のみ詳細ページへ進む

### 5.2 サイト別実装

| サイト | 戦略 | 判定方法 | 備考 |
|:---|:---|:---|:---|
| **Sumifu**<br>(住友不動産販売) | 戦略B<br>(フィルタリング) | 詳細ページURL構造<br>ページ内の物件種別情報 | 一覧ページでは種別混在<br>詳細ページで動的モデル切替 |
| **Nomura**<br>(ノムコム・プロ) | 戦略A<br>(検索条件) | URLパラメータ | 可能な限り検索条件で絞込<br>不可の場合は戦略Bへ |
| **Mitsui**<br>(三井のリハウス) | 戦略A<br>(検索条件) | URLパラメータ | 物件種別ごとの開始URL |
| **Tokyu**<br>(東急リバブル) | 戦略B<br>(フィルタリング) | 一覧上のラベル | 一覧ページで種別混在 |
| **Misawa**<br>(ミサワホーム不動産) | 戦略B<br>(フィルタリング) | URLパターン | 詳細URLから種別判定 |

### 5.3 動的モデル切り替え実装

投資用物件パーサーでは、`_parsePropertyDetailPage` メソッド内で物件種別を判定し、適切なモデルに切り替えます。

**実装例（Sumifu）**:

```python
def _parsePropertyDetailPage(self, item, response: BeautifulSoup):
    # デフォルトはKodate
    target_model = SumifuInvestmentKodate
    type_str = "Kodate"
    
    # URL または ページ内容から種別判定
    url = getattr(item, 'pageUrl', '')
    if self._is_apartment(url, response):
        target_model = SumifuInvestmentApartment
        type_str = "Apartment"
    
    # モデルが異なる場合は切り替え
    if not isinstance(item, target_model):
        new_item = target_model()
        new_item.pageUrl = url
        item = new_item
    
    # 物件種別を明示的に設定
    item.propertyType = type_str
    
    # 以降、通常のパース処理
    ...
```

### 5.4 エラーハンドリング

**物件種別判定失敗時**:
- 詳細ログを出力（URL、判定に使用した情報）
- デフォルトモデル（通常はKodate）で処理を継続
- `propertyType` フィールドに "Unknown" を設定

**検証時の確認項目**:
- DB保存後、`propertyType` フィールドで種別分布を確認
- 両方の種別（Apartment/Kodate）のデータが取得できていること
- 件数の偏りがないか確認

### 5.5 並列処理の考慮

投資用物件は2種類のモデルに分かれるため、以下の点に注意:

1. **並列数制限**: 両方の種別を合わせて `DETAIL_PARARELL_LIMIT` 以内に収める
2. **DB接続**: 同時書き込みによる競合を避ける
3. **メモリ管理**: 2種類のモデルインスタンスが同時に存在することを考慮

## 6. 通信エンジン

`aiohttp` を使用した非同期 HTTP 通信を採用しています。ブラウザレンダリング（Playwright 等）を介さないため、リソース消費が極めて少なく、高速なクロールが可能です。

## 7. 価格推定 API (Price Estimation API)

機械学習モデル（物件種別ごとに個別学習されたアンサンブルモデル）を用いて、一次予測（画像なし理論価格）および二次予測（画像スコア込み精密理論価格）の推定価格（万円）を返却するAPIです。

物件種別ごとにエンドポイントおよびリクエストパラメータが分かれており、詳細仕様は [OpenAPI仕様書（Swagger）](docs/api/openapi.yaml) に定義されています。

### 7.1 エンドポイント一覧
- **マンション価格推定**: `POST /api/evaluation/predict/mansion`
- **戸建価格推定**: `POST /api/evaluation/predict/kodate`
- **一棟アパート（投資用）価格推定**: `POST /api/evaluation/predict/apartment`
- **土地価格推定**: `POST /api/evaluation/predict/tochi`

### 7.2 リクエストパラメータ概要

各エンドポイントの `property_data` に送信する基本パラメータは以下の通り分類されます。

#### 共通パラメータ
- `price` (必須): 販売価格（円）
- `address` (必須): 物件の住所（市区町村地価・所得・ハザードマスタ引き当てキー）
- `station1` (任意): 最寄り駅名（駅乗降客数マスタ引き当てキー）
- `chikunengetsuStr` (任意): 築年月 (例: "平成15年10月", "2010-04-01")
- `railwayWalkMinute1` (任意): 徒歩分数 (分)
- `kouzou` (任意): 建物構造 (例: "RC", "木造")
- `yousekiStr` (任意): 指定容積率 (例: "200%")
- `kenpeiStr` (任意): 指定建ぺい率 (例: "60%")
- `tochikenri` (任意): 土地権利形態 (例: "所有権", "借地権") - 権利割引率 `rights_ratio` の判定キー
- `biko` (任意): 備考（再建築不可や市街化調整区域などの判定用）

#### 各物件種別の固有パラメータ
- **mansion**:
  - `senyuMenseki` (必須): 専有面積 (㎡)
  - `kanrihi` (任意): 月額管理費 (円)
  - `syuzenTsumitate` (任意): 月額修繕積立金 (円)
- **kodate**:
  - `tatemonoMenseki` (必須): 建物面積 (㎡)
  - `tochiMenseki` (必須): 土地有効面積 (㎡)
  - `maguchi` (任意): 接道間口 (m)
  - `roadWidth` (任意): 前面道路幅員 (m)
  - `setsudou` (任意): 接道状況テキスト
- **apartment**:
  - `tatemonoMenseki` (必須): 建物延床面積 (㎡)
  - `tochiMenseki` (必須): 土地面積 (㎡)
  - `maguchi` (任意): 接道間口 (m)
  - `roadWidth` (任意): 前面道路幅員 (m)
  - `setsudou` (任意): 接道状況テキスト
  - `grossYield` (必須): 表面利回り (%) - 収益還元想定に使用
  - `annualRent` (必須): 年間想定賃料 (円) - 収益還元想定に使用
- **tochi**:
  - `tochiMenseki` (必須): 土地面積 (㎡)
  - `maguchi` (任意): 接道間口 (m)
  - `roadWidth` (任意): 前面道路幅員 (m)
  - `setsudou` (任意): 接道状況テキスト

> [!NOTE]
> **地域ポテンシャル情報の自動補完**
> 「固定資産税評価額」「相続税評価額（路線価）」「周辺地価」「自治体人口・所得統計（納税額）」「駅乗降客数」「ハザードマップリスク」などの地域統計メタ特徴量は、クライアントから送信された住所 (`address`) および最寄り駅 (`station1`) をもとに、API内部で自動引き当て・補完されるため、クライアントが手動で調べる必要はありません。

### 7.3 レスポンスパラメータ (JSON)

| フィールド名 | 型 | 説明 |
| :--- | :--- | :--- |
| `success` | Boolean | 処理成否 |
| `property_type` | String | 指定された物件種別 (`mansion`, `kodate`, `apartment`, `tochi`) |
| `first_stage_predicted_price` | Integer | 一次推定理論価格（万円）。画像なしの特徴量による理論価格。 |
| `second_stage_predicted_price` | Integer | 二次推定精密理論価格（万円）。画像スコアを統合した精密理論価格。 |
| `message` | String | メッセージ |

# 物件詳細URL価格推定API 内部設計書

## 1. モジュール構成と責務

| モジュール / ファイル | 責務 |
|---|---|
| `package.models.candidate.CandidatePropertyUrl` | 未対応物件URLのクローリング候補を永続化するDjangoモデル |
| `package.utils.url_router.UrlRouter` | URL正規表現から `(site, property_type, parser_cls)` を解決 |
| `package.utils.property_type_detector.PropertyTypeDetector` | URL・タイトル・HTML構造・スペック辞書から物件種別を総合判定する再利用可能モジュール |
| `package.utils.url_security.UrlSecurityValidator` | SSRF防御（IP解決・プライベートIP除外）、HTTP疎通確認、不動産キーワード判定 |
| `package.utils.singleflight.SingleflightGroup` | 同一キー（URL）に対する多重非同期リクエストの合流・待機制御 |
| `package.utils.rate_limiter.SlidingWindowRateLimiter` | インメモリ・スライディングウィンドウ型レートリミッター |
| `routes.evaluation_routes.predict_by_url` | APIエンドポイントハンドラー（認証、制限、検証、推論オーケストレーション） |

---

## 2. データベースモデル設計 (`CandidatePropertyUrl`)

```python
from django.db import models

class CandidatePropertyUrl(models.Model):
    """未対応サイトの物件クローリング候補URLモデル"""
    url = models.CharField(max_length=500, unique=True, db_index=True, verbose_name="物件URL")
    domain = models.CharField(max_length=100, db_index=True, verbose_name="ドメイン")
    title = models.CharField(max_length=300, blank=True, default="", verbose_name="ページタイトル")
    matched_keywords = models.JSONField(default=list, verbose_name="検知された不動産キーワード")
    request_count = models.IntegerField(default=1, verbose_name="リクエスト要求回数")
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "未着手"),
            ("developing", "開発中"),
            ("rejected", "対象外"),
            ("implemented", "実装完了")
        ],
        verbose_name="開発ステータス"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="初回要求日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="最終更新日時")

    class Meta:
        db_table = "candidate_property_url"
        verbose_name = "クローリング候補URL"
        verbose_name_plural = "クローリング候補URL一覧"
```

---

## 3. URLルーター設計 (`UrlRouter`)

URL文字列の正規表現パターンマッチングにより、対応サイト・物件種別・パーサークラスを特定する。

```python
URL_ROUTES = [
    # 三井のリハウス (Mitsui)
    (r"rehouse\.co\.jp/buy/mansion/bkdetail/", "mitsui", "mansion", "MitsuiMansionParser"),
    (r"rehouse\.co\.jp/buy/kodate/bkdetail/", "mitsui", "kodate", "MitsuiKodateParser"),
    (r"rehouse\.co\.jp/buy/tochi/bkdetail/", "mitsui", "tochi", "MitsuiTochiParser"),
    (r"rehouse\.co\.jp/buy/tohshi/.*bkdetail/", "mitsui", "apartment", "MitsuiInvestApartmentParser"),
    
    # 東急リバブル (Tokyu)
    (r"livable\.co\.jp/kounyu/chuko-mansion/.*\/C[A-Z0-9]+", "tokyu", "mansion", "TokyuMansionParser"),
    (r"livable\.co\.jp/kounyu/kodate/.*\/C[A-Z0-9]+", "tokyu", "kodate", "TokyuKodateParser"),
    (r"livable\.co\.jp/kounyu/tochi/.*\/C[A-Z0-9]+", "tokyu", "tochi", "TokyuTochiParser"),
    (r"livable\.co\.jp/toushi/.*\/C[A-Z0-9]+", "tokyu", "apartment", "TokyuInvestApartmentParser"),

    # 住友不動産ステップ (Sumifu)
    (r"stepon\.co\.jp/mansion/detail/", "sumifu", "mansion", "SumifuMansionParser"),
    (r"stepon\.co\.jp/kodate/detail/", "sumifu", "kodate", "SumifuKodateParser"),
    (r"stepon\.co\.jp/tochi/detail/", "sumifu", "tochi", "SumifuTochiParser"),
    (r"stepon\.co\.jp/pro/.*detail/", "sumifu", "apartment", "SumifuInvestApartmentParser"),

    # アットホーム (Athome)
    (r"athome\.co\.jp/mansion/chuko/\d+/", "athome", "mansion", "AthomeMansionParser"),
    (r"athome\.co\.jp/kodate/chuko/\d+/", "athome", "kodate", "AthomeKodateParser"),
    (r"athome\.co\.jp/tochi/\d+/", "athome", "tochi", "AthomeTochiParser"),

    # LIFULL HOME'S (Homes)
    (r"homes\.co\.jp/mansion/b-\d+/", "homes", "mansion", "HomesMansionParser"),
    (r"homes\.co\.jp/kodate/b-\d+/", "homes", "kodate", "HomesKodateParser"),
    (r"homes\.co\.jp/tochi/b-\d+/", "homes", "tochi", "HomesTochiParser"),

    # ミサワホーム (Misawa)
    (r"realestate\.misawa\.co\.jp/search/sale/detail/.*bukken_type=9", "misawa", "mansion", "MisawaMansionParser"),
    (r"realestate\.misawa\.co\.jp/search/sale/detail/.*bukken_type=10", "misawa", "kodate", "MisawaKodateParser"),

    # 三井住友トラスト (Smtrc)
    (r"smtrc\.jp/buy/detail/", "smtrc", "mansion", "SmtrcMansionParser"),

    # 野村不動産ノムコム (Nomura)
    (r"nomu\.com/mansion/id/[A-Z0-9]+/", "nomura", "mansion", "NomuraMansionParser"),
    (r"nomu\.com/house/id/[A-Z0-9]+/", "nomura", "kodate", "NomuraKodateParser"),
    (r"nomu\.com/land/id/[A-Z0-9]+/", "nomura", "tochi", "NomuraTochiParser"),
]
```

---

## 4. Singleflight（リクエスト合流制御）設計

同一キー（URL）に対する多重リクエストを合流させ、先行処理の完了を後続処理が待機する非同期制御。

```python
class SingleflightGroup:
    def __init__(self):
        self._calls = {}
        self._lock = asyncio.Lock()

    async def do(self, key: str, fn, *args, **kwargs):
        async with self._lock:
            if key in self._calls:
                call = self._calls[key]
                # 先行処理実行中のため待機
                return await call.wait()
            call = _Call()
            self._calls[key] = call

        try:
            result = await fn(*args, **kwargs)
            call.set_result(result)
            return result
        except Exception as e:
            call.set_error(e)
            raise e
        finally:
            async with self._lock:
                self._calls.pop(key, None)
```

---

## 5. SSRF防御 ＆ 到達性・物件判定設計 (`UrlSecurityValidator`)

### 5.1 SSRF防御
1. スキーム検証: `parsed.scheme in ('http', 'https')`
2. ポート検証: `parsed.port in (None, 80, 443)`
3. DNS名前解決: `socket.getaddrinfo(hostname, None)`
4. IPアドレス検証 (`ipaddress.ip_address(ip)`):
   - `ip.is_private`: `True` ➔ 拒否
   - `ip.is_loopback`: `True` ➔ 拒否
   - `ip.is_link_local`: `True` ➔ 拒否 (`169.254.169.254` メタデータ遮断)
   - `ip.is_reserved` / `ip.is_multicast`: `True` ➔ 拒否

### 5.2 到達性・物件コンテンツ判定
1. aiohttp HEAD / GET (Timeout: 3秒, Max Redirects: 3)
2. Content-Length ヘッダ検証 (上限 2MB)
3. HTML先頭100KBを取得しテキスト抽出
4. 不動産キーワード照合:
   ```python
   PROPERTY_KEYWORDS = [
       "価格", "販売価格", "専有面積", "建物面積", "土地面積",
       "間取り", "所在地", "築年月", "徒歩", "駅", "構造"
   ]
   ```
   - 3つ以上一致した場合に「物件ページ」と認定。

---

## 6. レートリミッター設計 (`SlidingWindowRateLimiter`)

スライディングウィンドウ方式でIPアドレスおよびAPIキーごとのリクエスト数をメモリ内で追跡。

```python
class SlidingWindowRateLimiter:
    def __init__(self, limit_per_minute: int = 60, burst_per_second: int = 5):
        self.limit_per_minute = limit_per_minute
        self.burst_per_second = burst_per_second
        self.requests = collections.defaultdict(list)
        self.lock = threading.Lock()

    def is_allowed(self, identifier: str) -> tuple[bool, int]:
        now = time.time()
        with self.lock:
            timestamps = self.requests[identifier]
            # 1分以前の古いログをパージ
            timestamps = [t for t in timestamps if now - t < 60]
            self.requests[identifier] = timestamps

            # 1秒あたりのバーストチェック
            recent_1s = sum(1 for t in timestamps if now - t < 1)
            if recent_1s >= self.burst_per_second:
                return False, 1

            # 1分あたりの上限チェック
            if len(timestamps) >= self.limit_per_minute:
                retry_after = int(60 - (now - timestamps[0])) + 1
                return False, max(retry_after, 1)

            timestamps.append(now)
            return True, 0
```

---

## 7. ロックアウトマネージャー設計 (`LockoutManager`)

悪質な接続元（SSRF試行、429違反継続、認証エラー連続など）を一定時間（デフォルト900秒）自動的にブロックする。

```python
class LockoutManager:
    def __init__(self, lockout_seconds: int = 900, strike_threshold: int = 3):
        self.lockout_seconds = lockout_seconds
        self.strike_threshold = strike_threshold
        self._strikes = collections.defaultdict(list)  # { ip: [timestamp, ...] }
        self._banned = {}  # { ip: unban_timestamp }
        self._lock = threading.Lock()

    def is_locked_out(self, ip: str) -> tuple[bool, int]:
        """ロックアウト中か判定。Trueの場合、残り秒数を返却"""
        now = time.time()
        with self._lock:
            if ip in self._banned:
                unban_time = self._banned[ip]
                if now < unban_time:
                    return True, int(unban_time - now) + 1
                else:
                    del self._banned[ip]
                    self._strikes.pop(ip, None)
            return False, 0

    def record_strike(self, ip: str, instant_ban: bool = False) -> tuple[bool, int]:
        """違反を記録し、閾値超過または重大違反時にロックアウト"""
        now = time.time()
        with self._lock:
            if instant_ban:
                self._banned[ip] = now + self.lockout_seconds
                return True, self.lockout_seconds

            strikes = [t for t in self._strikes[ip] if now - t < 300]  # 5分以内のストライク
            strikes.append(now)
            self._strikes[ip] = strikes

            if len(strikes) >= self.strike_threshold:
                self._banned[ip] = now + self.lockout_seconds
                return True, self.lockout_seconds
            return False, 0
```

---

## 8. URL正規化・クエリパラメータ突合モジュール設計 (`UrlMatcher`)

`yarl` ライブラリを採用し、URL正規化、同一性判定、Django ORM検索クエリ生成を一元化。

```python
from yarl import URL
from django.db.models import Q

class UrlMatcher:
    @staticmethod
    def normalize(url: str) -> str:
        """クエリパラメータ・フラグメントを除去し、正規化ベースURLを生成"""
        if not url:
            return ""
        try:
            u = URL(url).with_query(None).with_fragment(None)
            return str(u)
        except Exception:
            return url.split("?")[0].split("#")[0]

    @staticmethod
    def is_same_url(url1: str, url2: str) -> bool:
        """クエリパラメータ・末尾スラッシュの有無を無視して同一物件URLかを判定"""
        if not url1 or not url2:
            return False
        n1 = UrlMatcher.normalize(url1).rstrip("/")
        n2 = UrlMatcher.normalize(url2).rstrip("/")
        return n1 == n2

    @staticmethod
    def build_db_filter(field_name: str, url: str) -> Q:
        """
        DB内レコード（クエリ付き/無し/末尾スラッシュ有無）に双方向適合するQオブジェクトを生成
        """
        norm = UrlMatcher.normalize(url)
        norm_no_slash = norm.rstrip("/")
        norm_with_slash = norm_no_slash + "/"
        return (
            Q(**{field_name: norm_with_slash}) |
            Q(**{f"{field_name}__startswith": norm_with_slash + "?"}) |
            Q(**{field_name: norm_no_slash}) |
            Q(**{f"{field_name}__startswith": norm_no_slash + "?"})
        )
```

---

## 9. パーサー未対応エラーログ設計

パーサー未対応物件のログフォーマット:
```python
logging.error(
    f"[PARSER_UNAVAILABLE] No parser implemented for site domain '{parsed_domain}' "
    f"(URL: {clean_url}, Title: '{page_title}', Keywords: {matched_kws}). "
    f"Target registered to CandidatePropertyUrl backlog (count={req_count})."
)
```

パーサークラス読込失敗時のログフォーマット:
```python
logging.error(
    f"[PARSER_NOT_FOUND] Parser class '{parser_cls_name}' could not be loaded for URL: {url}: {e}",
    exc_info=True
)
```

---

## 10. 動的物件種別判別設計 (`PropertyTypeDetector`)

多様な入力シグナル（スペック辞書、タイトル、HTMLテキスト、URL）から物件種別を安全・確実に判定する。各所から単体・組合せで呼び出し可能。

```python
class PropertyTypeDetector:
    # 投資用絶対判定キーワード（最優先ガードレール）
    INVESTMENT_STRONG_SIGNALS = [
        "表面利回り", "実質利回り", "想定利回り", "現況利回り", "満室利回り", "満室時利回り",
        "利回り", "オーナーチェンジ", "サブリース", "想定年収", "満室想定", "年間予定賃料", "賃貸中"
    ]

    # 判定優先度付きキーワードマップ
    # ※「一棟マンション」等の複合語を「マンション」より先に判定するため順序を厳格化
    APARTMENT_KEYWORDS = [
        "一棟アパート", "一棟売りアパート", "一棟マンション", "一棟売りマンション",
        "一棟ビル", "一棟売りビル", "収益物件", "アパート", "収益アパート", "投資用アパート", "一棟売り", "一棟"
    ]
    MANSION_KEYWORDS = [
        "区分マンション", "中古マンション", "新築マンション", "マンション", "区分所有", "ライオンズマンション", "パークホームズ"
    ]
    KODATE_KEYWORDS = [
        "一戸建て", "一戸建", "新築戸建", "中古戸建", "戸建", "テラスハウス"
    ]
    TOCHI_KEYWORDS = [
        "売り土地", "売土地", "売地", "土地", "建築条件付土地"
    ]

    @classmethod
    def detect(
        cls,
        url: Optional[str] = None,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None,
        default: Optional[str] = None,
        use_ai: bool = False
    ) -> Optional[str]:
        """
        1. 決定論的利回りガード (Yield Guard)
        2. スペック表 -> タイトル -> HTMLテキスト -> URL の優先順位でルール判定
        3. ルール判定不能時かつ use_ai=True の場合、Gemini Flash による AI フォールバック実行
        戻り値: 'apartment' | 'mansion' | 'kodate' | 'tochi' | default
        """
        ...

    @classmethod
    def detect_with_ai(
        cls,
        title: Optional[str] = None,
        html_text: Optional[str] = None,
        specs: Optional[Dict[str, Any]] = None,
        default: str = "mansion"
    ) -> str:
        """
        Gemini 1.5 Flash を用いた高精度分類フォールバック。
        AI出力は事後サニタイザー (_sanitize_output) により利回り・物理制約を再検証。
        """
        ...

    @classmethod
    def detect_from_object(cls, property_obj: Any) -> str:
        """
        dict または Django Model インスタンスから物件種別を判定。
        （利回り、土地面積0のRC造是正ロジックを統合したSSOTメソッド）
        """
        ...

    @classmethod
    def detect_investment_type(cls, text: str, default: str = "Apartment") -> str:
        """
        投資物件の表題・テキスト等から Apartment / Mansion / Building を判定。
        各社投資パーサーの共通メソッド。
        """
        ...
```

### 連携ポイント
1. **`UrlRouter.ROUTES`**:
   - `toushi.homes.co.jp` を追加（デフォルト: `apartment` ➔ `HomesInvestmentApartmentParser` / `HomesInvestmentApartment`）。
2. **`UrlRouter.resolve(url, title=None, html_text=None, specs=None)`**:
   - URLによる解決に加え、タイトルやスペック表が渡された場合に動的に種別特定・検証を実行可能。
3. **`evaluation_routes.py`**:
   - URLセキュリティ判定で取得したタイトル・コンテンツ情報から `PropertyTypeDetector.detect` を呼び出し、種別を確定。
4. **`predict.py` (ML推論パイプライン)**:
   - `_detect_property_type` を `PropertyTypeDetector.detect_from_object` に一本化。
5. **各社投資パーサー**:
   - `PropertyTypeDetector.detect_investment_type` でサブ種別判定を一元化。

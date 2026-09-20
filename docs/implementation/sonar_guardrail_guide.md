# SonarCloud ローカルガードレール＆コーディング規約ガイド

SonarCloud CIチェックでの失敗および手戻りを撲滅するための、IDE設定、事前ローカル検証、および安全なコーディングパターンの総合ガイドです。

---

## 1. 3層防御アーキテクチャ

| 層 | タイミング | 仕組み | 所要時間 |
|---|---|---|---|
| **Layer 1: IDE** | コーディング中 | VSCode + SonarLint 拡張機能 | 0秒（波線ハイライト） |
| **Layer 2: Local Guard** | Push / コミット前 | `check_local_sonar.py` + `.githooks/pre-push` | ~0.2秒 |
| **Layer 3: コーディング規約** | 設計・実装時 | S3776 / S8786 アンチパターン撲滅規約 | 事前予防 |

---

## 2. Layer 1: VSCode + SonarLint 接続設定（0秒検知）

エディタ上でコードを書いた瞬間に SonarCloud と同一の波線警告を表示させます。

### セットアップ手順
1. VSCode 拡張機能 **`SonarLint`** (`SonarSource.sonarlint-vscode`) をインストール。
2. SonarCloud の [Security / My Account / Security](https://sonarcloud.io/account/security/) で User Token を発行。
3. VSCode で `Ctrl+Shift+P` (Mac: `Cmd+Shift+P`) ➔ `SonarLint: Connect to SonarCloud` を実行。
4. コネクション設定:
   - Connection ID: `sonarcloud`
   - Token: 発行した User Token を入力
   - Organization: `anaharayasuo`
5. `.vscode/settings.json` に既存の設定（`AnaharaYasuo_realestate_crawler`）と自動バインドされ、Pythonコード編集時にリアルタイム解析が有効になります。

---

## 3. Layer 2: ローカル事前検証 CLI & Git フック

### CLI の手動実行
```bash
# 変更差分ファイルのみを高速チェック（推奨: 0.2秒）
task sonar-check

# 全ファイルを一括スキャン
task sonar-check-all

# 直接スクリプトを実行する場合
python src/crawler/scripts/debug_tools/check_local_sonar.py --diff
```

### Git pre-push フックによる自動ブロック
- `git push` 実行時、`.githooks/pre-push` が自動で `check_local_sonar.py --diff` を呼び出します。
- S3776（複雑度 > 15）または S8786（危険正規表現）が検出された場合、プッシュは拒否（Exit Code 1）されます。
- **緊急時のバイパス**:
  - `SKIP_SONAR_CHECK=1 git push origin feature/xxx`
  - または `git push --no-verify`

---

## 4. Layer 3: コーディング規約（型化）

### ① `python:S3776` (Cognitive Complexity <= 15) の撃退法

Cognitive Complexity は「コードを読む際の人間の脳の負荷」を計測します。ネストが深くなるほど指数関数的にスコアが増加します。

#### パターン A: 早期リターン（Guard Clause）
ネストした `if` を解消し、フラットなガード節に書き換えます。

```python
# ❌ Bad: Complexity = 1 + 2 + 3 = 6
def process_data(data):
    if data:
        for item in data.items:
            if item.is_active:
                save(item)

#  Good: Complexity = 1 + 1 + 1 = 3
def process_data(data):
    if not data:
        return
    for item in data.items:
        if not item.is_active:
            continue
        save(item)
```

#### パターン B: 1抽出1関数（責務分割）
パーサーの `_get_specs` や `parse` 内で全属性を抽出せず、属性ごとの専用ヘルパーに分割します。

```python
# ❌ Bad: 1つの関数に全属性の抽出ifが並び Complexity 30+ に跳ね上がる
def _get_specs(self, soup):
    specs = {}
    price_tag = soup.find(...)
    if price_tag:
        ...
    area_tag = soup.find(...)
    if area_tag:
        ...
    # (30行以上の if-elif-try が続く)

#  Good: 小さな抽出メソッドへ切り出す
def _get_specs(self, soup):
    return {
        "price": self._parse_price(soup),
        "area": self._parse_area(soup),
        "madori": self._parse_madori(soup),
    }
```

#### パターン C: 辞書ディスパッチ（多段 if-elif の排除）
```python
# ❌ Bad: if-elif の連続
if prop_type == "mansion":
    return parse_mansion()
elif prop_type == "kodate":
    return parse_kodate()
elif prop_type == "tochi":
    return parse_tochi()

#  Good: マッピング辞書
DISPATCHER = {
    "mansion": parse_mansion,
    "kodate": parse_kodate,
    "tochi": parse_tochi,
}
handler = DISPATCHER.get(prop_type)
return handler() if handler else None
```

---

### ② `python:S8786` (Regex Backtracking / ReDoS) の撃退法

正規表現エンジンが一致しない文字列を走査する際、指数関数的なバックトラッキングが発生するパターンを排除します。

#### パターン A: `.*` / `.+` を文字クラスで限定
```python
# ❌ Bad: S8786 警告 (バックトラッキング爆発)
re.search(r"価格.*?(\d+)万円", text)
re.search(r"<div>(.*)</div>", html)

#  Good: 除外文字で範囲を限定
re.search(r"価格[^\d]*(\d+)万円", text)
re.search(r"<div>([^<]*)</div>", html)
```

#### パターン B: 正規表現より文字列メソッドを優先
```python
# ❌ Bad: 単純な切り出しに正規表現を使用
match = re.search(r"築年月[：:]\s*(.+)", text)
if match:
    val = match.group(1).strip()

#  Good: partition / split / replace
if "築年月" in text:
    val = text.split("築年月")[-1].lstrip("：: ").split("\n")[0].strip()
```

---

### ③ Quality Gate (New Code Coverage >= 80%) の達成法

- 修正した関数・メソッドに対して、**正常系だけでなく例外系・境界値のテストケースを同時に追加**する。
- 例: `if not item: return None` を書いたなら、`assert parser.parse(None) is None` のテストを書く。

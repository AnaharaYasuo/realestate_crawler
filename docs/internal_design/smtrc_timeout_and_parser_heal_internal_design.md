# smtrcクローラータイムアウト延長・所在階パースおよびバリデータ誤検知解消 内部設計書

## 1. 詳細仕様

### 1.1 `src/crawler/package/api/smtrc.py`
変更対象クラスとメソッド：
```python
class ParseSmtrcMansionStartAsync(ParseMiddlePageAsyncBase):
    ...
    def _getTimeOutSecond(self):
        return 2400

class ParseSmtrcKodateStartAsync(ParseMiddlePageAsyncBase):
    ...
    def _getTimeOutSecond(self):
        return 2400

class ParseSmtrcTochiStartAsync(ParseMiddlePageAsyncBase):
    ...
    def _getTimeOutSecond(self):
        return 2400

class ParseSmtrcInvestmentStartAsync(ParseMiddlePageAsyncBase):
    ...
    def _getTimeOutSecond(self):
        return 2400
```

### 1.2 `src/crawler/package/parser/smtrcParser.py`
`SmtrcMansionParser._parsePropertyDetailPage` の行245周辺：
```python
item.kaisuStr = (
    specs.get("所在階", "")
    or specs.get("所在階/階建", "")
    or specs.get("所在階／階建", "")
    or specs.get("階数", "")
)
self._parse_floor_spec(item, item.kaisuStr)
```

### 1.3 `src/crawler/package/utils/data_validator.py`
`PropertyDataValidator._check_mansion_specs` の行123-125周辺：
```python
floor = (
    getattr(item, "shozaikai", None)
    or getattr(item, "kaisu", None)
    or getattr(item, "floorType_kai", None)
    or getattr(item, "kaisuStr", None)
)
if not floor or str(floor).strip() in ["", "-", "None"]:
    reasons.append(ERR_MISSING_FLOOR)
```

## 2. 単体テスト仕様 (`tests/unit/test_smtrc_timeout_and_parser.py`)
1. **タイムアウト検証テスト (`test_smtrc_api_timeouts`)**:
   - `ParseSmtrcMansionStartAsync()._getTimeOutSecond() == 2400`
   - `ParseSmtrcKodateStartAsync()._getTimeOutSecond() == 2400`
   - `ParseSmtrcTochiStartAsync()._getTimeOutSecond() == 2400`
   - `ParseSmtrcInvestmentStartAsync()._getTimeOutSecond() == 2400`
2. **パーサー所在階パーステスト (`test_smtrc_mansion_parser_floor_formats`)**:
   - `所在階/階建`: `3階 / 地上10階建` ➔ `kaisuStr == "3階 / 地上10階建"`, `floorType_kai == 3`, `floorType_chijo == 10`
   - `所在階／階建`: `5階／地上14階建` ➔ `kaisuStr == "5階／地上14階建"`, `floorType_kai == 5`, `floorType_chijo == 14`
3. **バリデータ判定テスト (`test_validator_floor_fallbacks`)**:
   - `SmtrcMansion` インスタンスに `floorType_kai=3`, `kaisuStr="3階"` のみ設定時、`ERR_MISSING_FLOOR` が発生しないこと。
   - `floorType_kai=None`, `kaisuStr=""`, `shozaikai=None`, `kaisu=None` の場合、`ERR_MISSING_FLOOR` が正しく検知されること。

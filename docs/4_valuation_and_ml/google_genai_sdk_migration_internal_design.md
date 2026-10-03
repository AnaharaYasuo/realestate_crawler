# Google GenAI SDK 移行内部設計 (Issue #502)

## 1. モジュール別詳細変更

### 1.1 `src/crawler/package/utils/property_type_detector.py`
- インポート変更:
  ```python
  try:
      from google import genai
  except ImportError:
      genai = None
  ```
- クライアント呼出:
  ```python
  client = genai.Client(api_key=api_key)
  resp = client.models.generate_content(
      model="gemini-1.5-flash",
      contents=prompt,
  )
  raw_ans = (getattr(resp, "text", "") or "").strip().lower()
  ```

### 1.2 `src/crawler/package/utils/image_handler.py`
- インポート変更:
  ```python
  from google import genai
  from google.genai import types
  ```
- クライアント呼出:
  ```python
  client = genai.Client(
      api_key=api_key,
      http_options=types.HttpOptions(timeout=30.0)
  )
  # contents にプロンプトおよび PIL.Image を渡す
  response = client.models.generate_content(
      model='gemini-2.5-flash',
      contents=[prompt] + images_to_send,
  )
  ```

### 1.3 `src/crawler/package/ml/unified_property_extractor.py`
- インポート変更:
  ```python
  try:
      from google import genai
  except ImportError:
      genai = None
  ```
- クライアント生成および生成処理:
  ```python
  client = genai.Client(api_key=api_key)
  response = client.models.generate_content(
      model=self.model_name,
      contents=content_payload
  )
  ```

### 1.4 `src/crawler/scripts/ops/run_daily_prediction_diagnostics.py`
- インポート変更:
  ```python
  try:
      from google import genai
  except ImportError:
      genai = None
  ```
- クライアント生成および生成処理:
  ```python
  client = genai.Client(api_key=api_key)
  response = client.models.generate_content(
      model="gemini-1.5-flash",
      contents=prompt
  )
  ```

### 1.5 ユニットテストのモック改修
- `src/crawler/tests/test_image_handler.py`:
  - `monkeypatch.setattr("google.genai.Client", ...)`
- `src/crawler/tests/unit/test_ml_diagnostics.py`:
  - `monkeypatch.setattr("google.genai.Client", ...)`

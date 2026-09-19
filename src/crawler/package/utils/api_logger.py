# -*- coding: utf-8 -*-
import time
import logging
from typing import Any, Dict
from flask import Flask, request, g

logger = logging.getLogger(__name__)

SENSITIVE_KEY_SUBSTRINGS = (
    "password", "secret", "token", "api_key", "apikey", "authorization",
    "cookie", "credential", "auth"
)


def mask_sensitive_data(data: Any) -> Any:
    """
    リクエスト/レスポンス内の認証情報・機密データを再帰的にマスキングします。
    """
    if data is None:
        return None

    if isinstance(data, dict):
        masked_dict: Dict[str, Any] = {}
        for k, v in data.items():
            k_lower = str(k).lower().replace("-", "_")
            if any(sub in k_lower for sub in SENSITIVE_KEY_SUBSTRINGS):
                masked_dict[k] = "***"
            elif isinstance(v, (dict, list)):
                masked_dict[k] = mask_sensitive_data(v)
            else:
                masked_dict[k] = v
        return masked_dict

    if isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]

    return data


def get_logged_body_preview(body: Any, max_len: int = 2000) -> Any:
    """
    長大なレスポンスやバイナリデータをクランプしてプレビュー文字列を返します。
    """
    if body is None:
        return None

    if isinstance(body, (dict, list)):
        body_str = str(mask_sensitive_data(body))
        if len(body_str) > max_len:
            return body_str[:max_len] + f"... (truncated, total {len(body_str)} chars)"
        return body

    if isinstance(body, (str, bytes)):
        text = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
        if len(text) > max_len:
            return text[:max_len] + f"... (truncated, total {len(text)} chars)"
        return text

    return str(body)[:max_len]


def _is_skip_path(path: str) -> bool:
    """ヘルスチェック・Swagger等の定常・静的アクセスパス判定"""
    return path in ('/', '/health', '/api/health') or path.startswith(('/docs', '/static'))


def _extract_request_body() -> Any:
    """リクエストボディの抽出とマスキング"""
    if request.is_json:
        return mask_sensitive_data(request.get_json(silent=True))
    if request.form:
        return mask_sensitive_data(request.form.to_dict())
    if request.data:
        return get_logged_body_preview(request.get_data(as_text=True), max_len=2000)
    return None


def _extract_response_body(response) -> Any:
    """レスポンスボディの抽出とマスキング・クランプ"""
    content_type = response.headers.get('Content-Type', '')
    if 'application/json' in content_type:
        try:
            return mask_sensitive_data(response.get_json())
        except Exception:
            return get_logged_body_preview(response.get_data(as_text=True), max_len=2000)
    if 'text/' in content_type:
        return get_logged_body_preview(response.get_data(as_text=True), max_len=1000)
    return None


def _get_response_log_level(status_code: int) -> int:
    """ステータスコードに応じたログレベル判定"""
    if status_code >= 500:
        return logging.ERROR
    if status_code >= 400:
        return logging.WARNING
    return logging.INFO


def log_api_request():
    """リクエスト受信時のログ出力フック"""
    g.request_start_time = time.time()
    if _is_skip_path(request.path):
        return None

    try:
        req_params = request.args.to_dict() if request.args else None
        req_body = _extract_request_body()
        logging.info(
            f"[API Request] {request.method} {request.path} | "
            f"Params: {req_params} | Body: {req_body}"
        )
    except Exception as e:
        logging.warning(f"Failed to log API request payload: {e}")

    return None


def log_api_response(response):
    """レスポンス返却時のログ出力フック"""
    if _is_skip_path(request.path):
        return response

    try:
        start_t = getattr(g, 'request_start_time', None)
        duration_ms = round((time.time() - start_t) * 1000, 2) if start_t else None
        resp_body = _extract_response_body(response)
        log_level = _get_response_log_level(response.status_code)

        logging.log(
            log_level,
            f"[API Response] {request.method} {request.path} | "
            f"Status: {response.status_code} | Duration: {duration_ms}ms | Body: {resp_body}"
        )
    except Exception as e:
        logging.warning(f"Failed to log API response payload: {e}")

    return response


def setup_api_logging(app: Flask) -> None:
    """
    Flask アプリケーションに対してリクエスト・レスポンスの送受信ペイロードログフックを登録します。
    """
    app.before_request(log_api_request)
    app.after_request(log_api_response)


# -*- coding: utf-8 -*-
import time
import logging
from typing import Any, Dict, List, Union
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


def get_logged_body_preview(body: Union[str, bytes, Dict, List, Any], max_len: int = 2000) -> Any:
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


def setup_api_logging(app: Flask) -> None:
    """
    Flask アプリケーションに対してリクエスト・レスポンスの送受信ペイロードログフックを登録します。
    """

    @app.before_request
    def log_api_request():
        g.request_start_time = time.time()

        # ヘルスチェック・Swagger等の定常・静的アクセスはスキップ
        if request.path in ('/', '/health', '/api/health') or request.path.startswith(('/docs', '/static')):
            return None

        try:
            req_params = request.args.to_dict() if request.args else None
            req_body = None
            if request.is_json:
                req_body = mask_sensitive_data(request.get_json(silent=True))
            elif request.form:
                req_body = mask_sensitive_data(request.form.to_dict())
            elif request.data:
                req_body = get_logged_body_preview(request.get_data(as_text=True), max_len=2000)

            logging.info(
                f"[API Request] {request.method} {request.path} | "
                f"Params: {req_params} | Body: {req_body}"
            )
        except Exception as e:
            logging.warning(f"Failed to log API request payload: {e}")

        return None

    @app.after_request
    def log_api_response(response):
        # ヘルスチェック・Swagger等の定常・静的アクセスはスキップ
        if request.path in ('/', '/health', '/api/health') or request.path.startswith(('/docs', '/static')):
            return response

        try:
            start_t = getattr(g, 'request_start_time', None)
            duration_ms = round((time.time() - start_t) * 1000, 2) if start_t else None

            resp_body = None
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                try:
                    resp_body = mask_sensitive_data(response.get_json())
                except Exception:
                    resp_body = get_logged_body_preview(response.get_data(as_text=True), max_len=2000)
            elif 'text/' in content_type:
                resp_body = get_logged_body_preview(response.get_data(as_text=True), max_len=1000)

            status_code = response.status_code
            if status_code >= 500:
                log_level = logging.ERROR
            elif status_code >= 400:
                log_level = logging.WARNING
            else:
                log_level = logging.INFO

            logging.log(
                log_level,
                f"[API Response] {request.method} {request.path} | "
                f"Status: {status_code} | Duration: {duration_ms}ms | Body: {resp_body}"
            )
        except Exception as e:
            logging.warning(f"Failed to log API response payload: {e}")

        return response

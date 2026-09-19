# -*- coding: utf-8 -*-
import os
import logging
from flask import Blueprint, Response, request

swagger_bp = Blueprint('swagger', __name__)

SWAGGER_UI_HTML = """<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>Realestate Price Estimation API - Swagger UI</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-32x32.png" sizes="32x32" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-16x16.png" sizes="16x16" />
  <style>
    body { margin: 0; padding: 0; background: #fafafa; font-family: sans-serif; }
    .swagger-ui .topbar { display: none; }
    .swagger-ui .info { margin: 20px 0; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function() {
      window.ui = SwaggerUIBundle({
        url: '/api/openapi.yaml',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout"
      });
    };
  </script>
</body>
</html>"""

def _get_openapi_path():
    # 動的にプロジェクトルートを算出し、docs/api/openapi.yaml を特定
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base_dir, "docs", "api", "openapi.yaml")

@swagger_bp.route('/docs', methods=['GET', 'OPTIONS'])
def swagger_ui():
    """Swagger UI を表示"""
    if request.method == 'OPTIONS':
        return Response("", status=200)
    return Response(SWAGGER_UI_HTML, mimetype='text/html')

@swagger_bp.route('/api/openapi.yaml', methods=['GET', 'OPTIONS'])
def openapi_yaml():
    """OpenAPI 3.0 仕様書 (YAML) を返却"""
    if request.method == 'OPTIONS':
        return Response("", status=200)

    yaml_path = _get_openapi_path()
    if not os.path.exists(yaml_path):
        logging.error(f"OpenAPI YAML not found at: {yaml_path}")
        return Response("OpenAPI specification file not found", status=404, mimetype='text/plain')

    with open(yaml_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return Response(content, mimetype='text/yaml')

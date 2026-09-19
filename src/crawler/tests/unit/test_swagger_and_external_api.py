# -*- coding: utf-8 -*-
import json
import pytest
from unittest.mock import patch
from main import app

@pytest.fixture(autouse=True)
def mock_predictions():
    with patch('routes.evaluation_routes.predict_first_stage_local', return_value=45000000), \
         patch('routes.evaluation_routes.predict_second_stage_local', return_value=46500000):
        yield

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_swagger_ui_html(client):
    """GET /docs returns Swagger UI HTML"""
    response = client.get('/docs')
    assert response.status_code == 200
    assert b"swagger-ui" in response.data
    assert b"/api/openapi.yaml" in response.data

def test_openapi_yaml_endpoint(client):
    """GET /api/openapi.yaml returns valid OpenAPI YAML"""
    response = client.get('/api/openapi.yaml')
    assert response.status_code == 200
    assert b"openapi: 3.0.0" in response.data
    assert b"Realestate Price Estimation API" in response.data

def test_cors_options_preflight(client):
    """OPTIONS request to predict endpoint returns CORS headers"""
    response = client.open(
        '/api/evaluation/predict/mansion',
        method='OPTIONS',
        headers={
            'Origin': 'https://frontend-app.example.com',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type, X-API-KEY'
        }
    )
    assert response.status_code in (200, 204)
    assert response.headers.get('Access-Control-Allow-Origin') == '*'
    allow_methods = response.headers.get('Access-Control-Allow-Methods', '')
    assert 'POST' in allow_methods
    assert 'OPTIONS' in allow_methods

def test_cors_headers_on_post_response(client):
    """POST request response includes CORS headers for cross-origin callers"""
    payload = {
        "property_data": {
            "price": 35000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "senyuMenseki": 55.5
        }
    }
    response = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json',
        headers={'Origin': 'https://frontend-app.example.com'}
    )
    assert response.status_code == 200
    assert response.headers.get('Access-Control-Allow-Origin') == '*'

def test_api_key_auth_when_configured(client, monkeypatch):
    """When ESTIMATION_API_KEY is configured, requests without valid key are rejected"""
    monkeypatch.setenv("ESTIMATION_API_KEY", "valid-secret-key-123")

    payload = {
        "property_data": {
            "price": 35000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "senyuMenseki": 55.5
        }
    }

    # 1. No API key -> 401
    resp_no_key = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert resp_no_key.status_code == 401
    data_no_key = resp_no_key.get_json()
    assert data_no_key["success"] is False

    # 2. Invalid API key -> 401
    resp_bad_key = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json',
        headers={'X-API-KEY': 'wrong-key'}
    )
    assert resp_bad_key.status_code == 401

    # 3. Valid API key -> 200
    resp_valid = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json',
        headers={'X-API-KEY': 'valid-secret-key-123'}
    )
    assert resp_valid.status_code == 200
    data_valid = resp_valid.get_json()
    assert data_valid["success"] is True

def test_api_key_auth_when_not_configured(client, monkeypatch):
    """When ESTIMATION_API_KEY is empty/unset, requests pass freely (local/dev mode)"""
    monkeypatch.delenv("ESTIMATION_API_KEY", raising=False)

    payload = {
        "property_data": {
            "price": 35000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "senyuMenseki": 55.5
        }
    }
    response = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True

def test_cloud_environment_enforces_api_key_configuration(client, monkeypatch):
    """In cloud (IS_CLOUD=true), missing ESTIMATION_API_KEY causes 500 configuration error"""
    monkeypatch.setenv("IS_CLOUD", "true")
    monkeypatch.delenv("ESTIMATION_API_KEY", raising=False)

    payload = {
        "property_data": {
            "price": 35000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "senyuMenseki": 55.5
        }
    }
    resp = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert resp.status_code == 500
    assert resp.get_json()["success"] is False


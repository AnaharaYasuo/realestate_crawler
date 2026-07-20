# -*- coding: utf-8 -*-
import json
import pytest
from main import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_predict_mansion_success(client):
    payload = {
        "property_data": {
            "price": 35000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "senyuMenseki": 55.5,
            "chikunengetsuStr": "平成15年10月",
            "railwayWalkMinute1": 7,
            "kouzou": "RC"
        },
        "interior_score": 4.0,
        "layout_score": 3.5
    }
    response = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["property_type"] == "mansion"
    assert data["first_stage_predicted_price"] > 0
    assert data["second_stage_predicted_price"] > 0

def test_predict_kodate_success(client):
    payload = {
        "property_data": {
            "price": 55000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "tatemonoMenseki": 95.0,
            "tochiMenseki": 120.0,
            "chikunengetsuStr": "平成20年5月",
            "railwayWalkMinute1": 12,
            "kouzou": "木造"
        }
    }
    response = client.post(
        '/api/evaluation/predict/kodate',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["property_type"] == "kodate"
    assert data["first_stage_predicted_price"] > 0

def test_predict_apartment_success(client):
    payload = {
        "property_data": {
            "price": 120000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "tatemonoMenseki": 220.0,
            "tochiMenseki": 180.0,
            "chikunengetsuStr": "平成18年3月",
            "railwayWalkMinute1": 10,
            "kouzou": "軽量鉄骨造",
            "grossYield": 6.8,
            "annualRent": 8160000
        }
    }
    response = client.post(
        '/api/evaluation/predict/apartment',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["property_type"] == "apartment"
    assert data["first_stage_predicted_price"] > 0

def test_predict_tochi_success(client):
    payload = {
        "property_data": {
            "price": 30000000,
            "address": "東京都世田谷区桜丘1-1",
            "station1": "経堂",
            "tochiMenseki": 100.0,
            "railwayWalkMinute1": 9
        }
    }
    response = client.post(
        '/api/evaluation/predict/tochi',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["property_type"] == "tochi"
    assert data["first_stage_predicted_price"] > 0

def test_predict_missing_body(client):
    response = client.post(
        '/api/evaluation/predict/mansion',
        data=None,
        content_type='application/json'
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False

def test_predict_missing_property_data(client):
    payload = {
        "interior_score": 4.0
    }
    response = client.post(
        '/api/evaluation/predict/mansion',
        data=json.dumps(payload),
        content_type='application/json'
    )
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False

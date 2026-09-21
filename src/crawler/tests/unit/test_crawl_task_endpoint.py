# -*- coding: utf-8 -*-
"""
Cloud Run クロールタスク受信エンドポイント (/api/crawl/task) の単体テスト
"""
import pytest
import json
from unittest.mock import patch
from main import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_crawl_task_missing_params(client):
    response = client.post("/api/crawl/task", json={})
    assert response.status_code == 400
    data = json.loads(response.data)
    assert "error" in data


def test_crawl_task_unknown_job(client):
    response = client.post("/api/crawl/task", json={
        "company": "non_existent_company",
        "property_type": "mansion"
    })
    assert response.status_code == 404


@patch("main.execute_crawl_task")
def test_crawl_task_success(mock_execute, client):
    mock_execute.return_value = (True, 5, 12)
    response = client.post("/api/crawl/task", json={
        "company": "mitsui",
        "property_type": "mansion",
        "execution_date": "2026-09-19"
    })
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert data["scraped_count"] == 5


@patch("main.execute_crawl_task")
def test_crawl_task_failed(mock_execute, client):
    mock_execute.return_value = (False, 0, 0)
    response = client.post("/api/crawl/task", json={
        "company": "mitsui",
        "property_type": "mansion",
        "execution_date": "2026-09-19"
    })
    assert response.status_code == 500
    data = json.loads(response.data)
    assert data["status"] == "failed"
    assert data["error"] == "Crawl execution failed"

# -*- coding: utf-8 -*-
"""Cloud Tasks クロールジョブディスパッチャー."""
import json
import logging
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


def build_task_payload(company: str, property_type: str, execution_date: str) -> Dict[str, Any]:
    """Cloud Tasks 用の HTTP リクエストペイロードを構築"""
    return {
        "company": company.lower(),
        "property_type": property_type.lower(),
        "execution_date": execution_date
    }


def generate_crawl_tasks(
    jobs: List[Tuple[str, str]],
    execution_date: str
) -> List[Dict[str, Any]]:
    """ジョブリストからタスクペイロード一覧を生成"""
    return [
        build_task_payload(company, ptype, execution_date)
        for company, ptype in jobs
    ]


def dispatch_task_to_cloud_tasks(
    client: Any,
    queue_path: str,
    target_url: str,
    payload: Dict[str, Any],
    service_account_email: str
) -> str:
    """単一タスクを Cloud Tasks キューにエンキュー"""
    body = json.dumps(payload).encode("utf-8")
    task = {
        "http_request": {
            "http_method": 2,  # POST
            "url": target_url,
            "headers": {"Content-Type": "application/json"},
            "body": body,
            "oidc_token": {
                "service_account_email": service_account_email,
            }
        }
    }
    response = client.create_task(request={"parent": queue_path, "task": task})
    return response.name

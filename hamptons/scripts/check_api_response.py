#!/usr/bin/env python3
"""Check CrossChex API response structure."""

import frappe
import requests
import uuid
import json
from datetime import datetime


def check_response():
    settings = frappe.get_single("Crosschex Settings")
    config = settings.api_configurations[1]  # HAMPTONS 3 (HOD)

    config_doc = frappe.get_doc("CrossChex API Configuration", config.name)
    token = config_doc.get_password("token")
    api_url = config.api_url + ("/" if not config.api_url.endswith("/") else "")

    begin_time = datetime(2026, 1, 25, 0, 0, 0)
    end_time = datetime(2026, 1, 25, 23, 59, 59)

    payload = {
        "header": {
            "nameSpace": "attendance.record",
            "nameAction": "getrecord",
            "version": "1.0",
            "requestId": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        },
        "authorize": {"type": "token", "token": token},
        "payload": {
            "begin_time": begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "order": "asc",
            "page": 1,
            "per_page": 3,
        },
    }

    response = requests.post(
        api_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30
    )
    data = response.json()
    records = data.get("payload", {}).get("list", [])

    print(f"Config: {config.configuration_name}")
    print(f"Records: {len(records)}")
    if records:
        print(f"Sample record:\n{json.dumps(records[0], indent=2, default=str)}")
        print(f"\nField names: {list(records[0].keys())}")

    return records


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()
    check_response()
    frappe.db.close()

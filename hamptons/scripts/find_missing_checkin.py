#!/usr/bin/env python3
"""
Script to find missing checkins for a specific employee and date.
"""

import frappe
import requests
import uuid
from datetime import datetime


def find_employee_punches(employee_id, date_str):
    """
    Search all CrossChex devices for punches for a specific employee on a specific date.

    Args:
        employee_id: Employee attendance_device_id (e.g., "1037")
        date_str: Date in YYYY-MM-DD format
    """
    settings = frappe.get_single("Crosschex Settings")

    print(f"\n{'='*70}")
    print(f"Searching for Employee {employee_id} punches on {date_str}")
    print(f"{'='*70}")

    # Parse date
    date = datetime.strptime(date_str, "%Y-%m-%d")
    begin_time = datetime(date.year, date.month, date.day, 0, 0, 0)
    end_time = datetime(date.year, date.month, date.day, 23, 59, 59)

    all_punches = []

    for config in settings.api_configurations:
        print(f"\n--- Device: {config.configuration_name} ---")

        try:
            config_doc = frappe.get_doc("CrossChex API Configuration", config.name)
            token = config_doc.get_password('token')

            if not token:
                print("  No token available, skipping...")
                continue

            api_url = config.api_url
            if not api_url.endswith('/'):
                api_url += '/'

            request_id = str(uuid.uuid4())
            payload = {
                "header": {
                    "nameSpace": "attendance.record",
                    "nameAction": "getrecord",
                    "version": "1.0",
                    "requestId": request_id,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
                },
                "authorize": {"type": "token", "token": token},
                "payload": {
                    "begin_time": begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "end_time": end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                    "order": "asc",
                    "page": 1,
                    "per_page": 1000
                }
            }

            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            data = response.json()
            records = data.get('payload', {}).get('list', [])

            print(f"  Total records on this device: {len(records)}")

            # Find records for the employee
            for r in records:
                # CrossChex API uses nested employee.workno structure
                emp_data = r.get('employee', {})
                emp_id = str(emp_data.get('workno', '')) if isinstance(emp_data, dict) else ''
                if emp_id == str(employee_id):
                    punch_info = {
                        'device': config.configuration_name,
                        'checktime': r.get('checktime'),
                        'check_type': r.get('check_type', r.get('checktype')),
                        'uuid': r.get('uuid'),
                        'raw': r
                    }
                    all_punches.append(punch_info)
                    print(f"  FOUND! Time: {r.get('checktime')} | Type: {r.get('check_type')} | UUID: {r.get('uuid')}")

        except Exception as e:
            print(f"  Error: {str(e)}")

    # Summary
    print(f"\n{'='*70}")
    print(f"SUMMARY: Found {len(all_punches)} punches for employee {employee_id}")
    print(f"{'='*70}")

    if all_punches:
        for p in all_punches:
            print(f"  Device: {p['device']}")
            print(f"  Time: {p['checktime']}")
            print(f"  Type: {p['check_type']}")
            print(f"  UUID: {p['uuid']}")
            print()

    # Check what's in HRMS
    print(f"\n{'='*70}")
    print(f"HRMS Employee Checkins for {employee_id} on {date_str}")
    print(f"{'='*70}")

    checkins = frappe.db.sql("""
        SELECT name, time, log_type, custom_crosschex_uuid, device_id
        FROM `tabEmployee Checkin`
        WHERE employee = %s
        AND DATE(time) = %s
        ORDER BY time
    """, (employee_id, date_str), as_dict=1)

    print(f"Found {len(checkins)} checkins in HRMS:")
    for c in checkins:
        print(f"  {c['name']} | {c['time']} | {c['log_type']} | UUID: {c['custom_crosschex_uuid']} | Device: {c['device_id']}")

    # Show missing punches
    if all_punches:
        hrms_uuids = set(c['custom_crosschex_uuid'] for c in checkins if c['custom_crosschex_uuid'])
        missing = [p for p in all_punches if p['uuid'] not in hrms_uuids]

        if missing:
            print(f"\n{'='*70}")
            print(f"MISSING PUNCHES (in CrossChex but not in HRMS):")
            print(f"{'='*70}")
            for p in missing:
                print(f"  Device: {p['device']} | Time: {p['checktime']} | UUID: {p['uuid']}")

    return all_punches, checkins


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()

    # Search for employee 1037 on 2026-01-25
    find_employee_punches("1037", "2026-01-25")

    frappe.db.close()

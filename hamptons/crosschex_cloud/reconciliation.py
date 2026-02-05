# Copyright (c) 2025, Hamptons and contributors
# For license information, please see license.txt

"""
CrossChex Cloud Reconciliation Module

This module provides a permanent fix for missed synchronizations between
CrossChex Cloud and HRMS. It runs as a scheduled job to:
1. Fetch all punches from CrossChex Cloud for recent days
2. Compare with existing HRMS Employee Checkins
3. Import any missing records

This ensures no punch data is ever lost due to webhook failures,
network issues, or sync timing problems.
"""

import frappe
from frappe.utils import now_datetime, get_datetime, add_days, getdate
from datetime import datetime, timedelta
from dateutil import parser, tz
import requests
import uuid as uuid_lib
import json


def reconcile_missing_checkins(days_back=2, dry_run=False):
    """
    Reconcile missing checkins between CrossChex Cloud and HRMS.

    This function:
    1. Fetches all records from CrossChex Cloud for the past N days
    2. Compares with existing Employee Checkins in HRMS (by UUID)
    3. Imports any missing records

    Args:
        days_back: Number of days to check (default 2 for safety)
        dry_run: If True, only report missing records without importing

    Returns:
        dict with reconciliation results
    """
    if not frappe.db.exists("DocType", "Crosschex Settings"):
        frappe.logger().warning("CrossChex Reconciliation: Settings not found")
        return {"error": "Crosschex Settings not found"}

    settings = frappe.get_single("Crosschex Settings")

    if not settings.enable_realtime_sync:
        frappe.logger().info("CrossChex Reconciliation: Sync disabled, skipping")
        return {"skipped": True, "reason": "Sync disabled"}

    if not settings.api_configurations or len(settings.api_configurations) == 0:
        frappe.logger().info("CrossChex Reconciliation: No API configurations")
        return {"error": "No API configurations"}

    # Calculate date range
    end_time = datetime.utcnow()
    begin_time = end_time - timedelta(days=days_back)

    results = {
        "devices_checked": 0,
        "total_records_fetched": 0,
        "missing_records": 0,
        "records_imported": 0,
        "errors": [],
        "details": []
    }

    for config in settings.api_configurations:
        try:
            device_result = reconcile_device(
                config=config,
                begin_time=begin_time,
                end_time=end_time,
                dry_run=dry_run
            )

            results["devices_checked"] += 1
            results["total_records_fetched"] += device_result.get("records_fetched", 0)
            results["missing_records"] += device_result.get("missing", 0)
            results["records_imported"] += device_result.get("imported", 0)
            results["details"].append({
                "device": config.configuration_name,
                "result": device_result
            })

        except Exception as e:
            error_msg = f"Error reconciling {config.configuration_name}: {str(e)}"
            results["errors"].append(error_msg)
            frappe.log_error(message=error_msg, title="CrossChex Reconciliation Error")

    # Log summary
    frappe.logger().info(
        f"CrossChex Reconciliation Complete: "
        f"Checked {results['devices_checked']} devices, "
        f"Fetched {results['total_records_fetched']} records, "
        f"Found {results['missing_records']} missing, "
        f"Imported {results['records_imported']}"
    )

    return results


def reconcile_device(config, begin_time, end_time, dry_run=False):
    """
    Reconcile a single device's records.

    Args:
        config: CrossChex API Configuration child table row
        begin_time: Start of date range (datetime)
        end_time: End of date range (datetime)
        dry_run: If True, don't actually import

    Returns:
        dict with device reconciliation results
    """
    # Get token
    config_doc = frappe.get_doc("CrossChex API Configuration", config.name)
    token = config_doc.get_password('token')

    if not token:
        return {"error": "No token available", "records_fetched": 0, "missing": 0, "imported": 0}

    api_url = config.api_url
    if not api_url.endswith('/'):
        api_url += '/'

    # Fetch all records from CrossChex Cloud with pagination
    all_records = []
    page = 1
    per_page = 1000

    begin_time_str = begin_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    end_time_str = end_time.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    while True:
        request_id = str(uuid_lib.uuid4())
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
                "begin_time": begin_time_str,
                "end_time": end_time_str,
                "order": "asc",
                "page": page,
                "per_page": per_page
            }
        }

        try:
            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=60
            )

            if response.status_code != 200:
                break

            data = response.json()
            records = data.get('payload', {}).get('list', [])
            all_records.extend(records)

            # Check if more pages
            total = data.get('payload', {}).get('total', 0)
            if len(all_records) >= total or len(records) < per_page:
                break

            page += 1

            # Safety limit
            if page > 20:
                frappe.logger().warning(
                    f"CrossChex Reconciliation: Reached page limit for {config.configuration_name}"
                )
                break

        except Exception as e:
            frappe.log_error(
                message=f"Error fetching page {page}: {str(e)}",
                title=f"CrossChex Reconciliation - {config.configuration_name}"
            )
            break

    if not all_records:
        return {"records_fetched": 0, "missing": 0, "imported": 0}

    # Extract all UUIDs from CrossChex records
    crosschex_uuids = {}
    for r in all_records:
        uuid = r.get('uuid')
        if uuid:
            crosschex_uuids[uuid] = r

    # Get existing checkin UUIDs from HRMS
    existing_uuids = frappe.db.sql("""
        SELECT custom_crosschex_uuid
        FROM `tabEmployee Checkin`
        WHERE custom_crosschex_uuid IS NOT NULL
        AND custom_crosschex_uuid != ''
        AND custom_crosschex_uuid IN %(uuids)s
    """, {"uuids": list(crosschex_uuids.keys())}, as_dict=True)

    existing_uuid_set = set(r['custom_crosschex_uuid'] for r in existing_uuids)

    # Find missing records
    missing_uuids = set(crosschex_uuids.keys()) - existing_uuid_set
    missing_records = [crosschex_uuids[uuid] for uuid in missing_uuids]

    imported_count = 0
    errors = []

    if not dry_run and missing_records:
        for record in missing_records:
            try:
                success = import_single_record(record, config.configuration_name)
                if success:
                    imported_count += 1
            except Exception as e:
                errors.append(str(e))
                frappe.log_error(
                    message=f"Error importing record: {json.dumps(record)}\nError: {str(e)}",
                    title="CrossChex Reconciliation - Import Error"
                )

        frappe.db.commit()

    return {
        "records_fetched": len(all_records),
        "missing": len(missing_records),
        "imported": imported_count,
        "errors": errors if errors else None,
        "missing_details": [
            {
                "uuid": r.get('uuid'),
                "employee": r.get('employee', {}).get('workno'),
                "time": r.get('checktime')
            }
            for r in missing_records[:10]  # Limit details to first 10
        ] if missing_records else None
    }


def import_single_record(record, device_name="Unknown"):
    """
    Import a single CrossChex record as an Employee Checkin.

    Args:
        record: CrossChex record dict
        device_name: Device name for logging

    Returns:
        True if imported successfully, False otherwise
    """
    # Extract employee ID from nested structure
    emp_data = record.get('employee', {})
    employee_device_id = emp_data.get('workno', '') if isinstance(emp_data, dict) else ''

    if not employee_device_id:
        frappe.logger().warning(
            f"CrossChex Reconciliation: No workno in record {record.get('uuid')}"
        )
        return False

    # Find employee by attendance_device_id
    try:
        device_id_int = int(employee_device_id)
    except ValueError:
        frappe.logger().warning(
            f"CrossChex Reconciliation: Invalid workno '{employee_device_id}'"
        )
        return False

    employee = frappe.db.get_value(
        "Employee",
        {"attendance_device_id": device_id_int, "status": "Active"},
        ["name", "employee_name", "department", "designation"],
        as_dict=True
    )

    if not employee:
        frappe.logger().warning(
            f"CrossChex Reconciliation: No employee found for device_id {device_id_int}"
        )
        return False

    # Parse checktime - convert UTC to Dubai time
    checktime_str = record.get('checktime')
    if not checktime_str:
        return False

    try:
        dt_utc = parser.isoparse(checktime_str)
        dubai_tz = tz.gettz('Asia/Dubai')
        dt_dubai = dt_utc.astimezone(dubai_tz)
        checkin_time = dt_dubai.replace(tzinfo=None)
    except Exception as e:
        frappe.logger().warning(
            f"CrossChex Reconciliation: Error parsing time '{checktime_str}': {e}"
        )
        return False

    # Get shift assignment
    checkin_date = checkin_time.date()
    shift = frappe.db.get_value(
        "Shift Assignment",
        {
            "employee": employee['name'],
            "docstatus": 1,
            "start_date": ("<=", checkin_date)
        },
        "shift_type",
        order_by="start_date desc"
    )

    # Determine log type using alternating logic (first punch = IN, then alternate)
    # This is more reliable than trusting the device's checktype value
    from hamptons.crosschex_cloud.api.attendance import determine_log_type
    log_type = determine_log_type(employee['name'], checkin_time)

    # Create Employee Checkin
    checkin_doc = frappe.new_doc("Employee Checkin")
    checkin_doc.employee = employee['name']
    checkin_doc.log_type = log_type
    checkin_doc.device_id = record.get('device', {}).get('name', device_name)
    checkin_doc.time = checkin_time
    checkin_doc.naming_series = 'CKIN/.YY./.MM./.#####'
    checkin_doc.skip_auto_attendance = 1
    checkin_doc.custom_crosschex_uuid = record.get('uuid')

    if shift:
        checkin_doc.shift = shift

    checkin_doc.employee_name = employee.get('employee_name', '')
    checkin_doc.department = employee.get('department', '')
    checkin_doc.designation = employee.get('designation', '')

    checkin_doc.insert(ignore_permissions=True)

    frappe.logger().info(
        f"CrossChex Reconciliation: Imported {checkin_doc.name} for {employee['name']} "
        f"at {checkin_time} (UUID: {record.get('uuid')})"
    )

    return True


def scheduled_reconciliation_job():
    """
    Scheduled job to reconcile missing checkins.
    Runs as part of the scheduler to catch any missed records.
    """
    try:
        results = reconcile_missing_checkins(days_back=2, dry_run=False)

        if results.get("records_imported", 0) > 0:
            frappe.logger().info(
                f"CrossChex Reconciliation Job: Imported {results['records_imported']} missing records"
            )

            # Trigger attendance consolidation for affected employees
            trigger_consolidation_for_imported_records(results)

    except Exception as e:
        frappe.log_error(
            message=f"Scheduled reconciliation failed: {str(e)}",
            title="CrossChex Reconciliation Job Error"
        )


def trigger_consolidation_for_imported_records(results):
    """
    After importing missing records, trigger attendance consolidation
    for affected employees and dates.
    """
    try:
        from hamptons.overrides.employee_checkin import consolidate_attendance_for_date

        # Get unique employee/date combinations from imported records
        affected = set()
        for device_detail in results.get("details", []):
            missing_details = device_detail.get("result", {}).get("missing_details", [])
            for detail in missing_details or []:
                if detail.get("employee") and detail.get("time"):
                    try:
                        device_id = int(detail["employee"])
                        employee = frappe.db.get_value(
                            "Employee",
                            {"attendance_device_id": device_id, "status": "Active"},
                            "name"
                        )
                        if employee:
                            dt = parser.isoparse(detail["time"])
                            dubai_tz = tz.gettz('Asia/Dubai')
                            dt_dubai = dt.astimezone(dubai_tz)
                            date = dt_dubai.date()
                            affected.add((employee, date))
                    except Exception:
                        pass

        # Trigger consolidation for each affected employee/date
        for employee, date in affected:
            try:
                frappe.enqueue(
                    consolidate_attendance_for_date,
                    queue='default',
                    employee=employee,
                    date=date
                )
            except Exception as e:
                frappe.logger().warning(
                    f"CrossChex Reconciliation: Failed to trigger consolidation "
                    f"for {employee} on {date}: {e}"
                )

    except Exception as e:
        frappe.log_error(
            message=f"Error triggering consolidation: {str(e)}",
            title="CrossChex Reconciliation - Consolidation Error"
        )

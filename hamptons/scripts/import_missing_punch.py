#!/usr/bin/env python3
"""
Script to manually import a missing punch from CrossChex Cloud.
"""

import frappe
from datetime import datetime
from dateutil import parser, tz


def import_missing_punch(employee_device_id, checktime_utc, uuid, device_name="Hamptons-Head Office"):
    """
    Import a missing punch that wasn't synced from CrossChex Cloud.

    Args:
        employee_device_id: The employee's attendance_device_id (e.g., "1037")
        checktime_utc: The punch time in UTC (ISO format)
        uuid: The CrossChex UUID for the punch
        device_name: Device name
    """
    print(f"\n{'='*70}")
    print(f"IMPORTING MISSING PUNCH")
    print(f"{'='*70}")

    # Check if UUID already exists
    existing = frappe.db.exists("Employee Checkin", {"custom_crosschex_uuid": uuid})
    if existing:
        print(f"ERROR: Checkin with UUID {uuid} already exists: {existing}")
        return None

    # Find employee by attendance_device_id
    try:
        device_id_int = int(employee_device_id)
    except ValueError:
        print(f"ERROR: Invalid employee_device_id: {employee_device_id}")
        return None

    employee = frappe.db.get_value(
        "Employee",
        {"attendance_device_id": device_id_int, "status": "Active"},
        ["name", "employee_name", "department", "designation"],
        as_dict=True
    )

    if not employee:
        print(f"ERROR: No active employee found with attendance_device_id {device_id_int}")
        return None

    print(f"Employee: {employee['name']} - {employee['employee_name']}")

    # Parse and convert UTC time to Dubai time
    dt_utc = parser.isoparse(checktime_utc)
    dubai_tz = tz.gettz('Asia/Dubai')
    dt_dubai = dt_utc.astimezone(dubai_tz)
    checkin_time = dt_dubai.replace(tzinfo=None)

    print(f"UTC Time: {checktime_utc}")
    print(f"Dubai Time: {checkin_time}")
    print(f"UUID: {uuid}")

    # Find shift assignment for this employee on this date
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
    print(f"Shift: {shift or 'Not assigned'}")

    # Create the checkin
    checkin_doc = frappe.new_doc("Employee Checkin")
    checkin_doc.employee = employee['name']
    checkin_doc.log_type = "OUT"  # Second punch of the day is typically OUT
    checkin_doc.device_id = device_name
    checkin_doc.time = checkin_time
    checkin_doc.naming_series = 'CKIN/.YY./.MM./.#####'
    checkin_doc.skip_auto_attendance = 1
    checkin_doc.custom_crosschex_uuid = uuid

    if shift:
        checkin_doc.shift = shift

    checkin_doc.employee_name = employee.get('employee_name', '')
    checkin_doc.department = employee.get('department', '')
    checkin_doc.designation = employee.get('designation', '')

    checkin_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    print(f"\n✅ Successfully created checkin: {checkin_doc.name}")
    print(f"   Time: {checkin_doc.time}")
    print(f"   Log Type: {checkin_doc.log_type}")
    print(f"   UUID: {checkin_doc.custom_crosschex_uuid}")

    return checkin_doc.name


def check_and_trigger_consolidation(employee_id, date_str):
    """
    After importing, trigger attendance consolidation for the employee/date.
    """
    print(f"\n{'='*70}")
    print(f"TRIGGERING ATTENDANCE CONSOLIDATION")
    print(f"{'='*70}")

    from datetime import datetime as dt
    date = dt.strptime(date_str, "%Y-%m-%d").date()

    # Import the consolidation function
    from hamptons.overrides.employee_checkin import consolidate_attendance_for_date

    # Run consolidation synchronously for immediate feedback
    result = consolidate_attendance_for_date(employee_id, date)

    print(f"Consolidation completed for {employee_id} on {date_str}")
    return result


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()

    # Import the missing punch for employee 1037
    # From CrossChex API: Time 2026-01-25T13:40:08+00:00 (UTC), UUID a6bc...8c3c

    checkin_name = import_missing_punch(
        employee_device_id="1037",
        checktime_utc="2026-01-25T13:40:08+00:00",
        uuid="a6bc53e3b0cc95a1d0d294ca367f1f3be1bc45a598d731a8af8381146a7b8c3c",
        device_name="Hamptons-Head Office"
    )

    if checkin_name:
        # Get the employee name from device ID
        employee = frappe.db.get_value(
            "Employee",
            {"attendance_device_id": 1037, "status": "Active"},
            "name"
        )
        if employee:
            check_and_trigger_consolidation(employee, "2026-01-25")

    frappe.db.close()

#!/usr/bin/env python3
"""
Script to trigger attendance consolidation for a specific employee on a specific date.
"""

import frappe
from datetime import datetime


def consolidate_for_employee(employee, date_str):
    """
    Trigger attendance consolidation for a specific employee on a specific date.

    Args:
        employee: Employee ID (e.g., "HR-EMP-01037")
        date_str: Date in YYYY-MM-DD format
    """
    print(f"\n{'='*70}")
    print(f"CONSOLIDATING ATTENDANCE FOR {employee} ON {date_str}")
    print(f"{'='*70}")

    date = datetime.strptime(date_str, "%Y-%m-%d").date()

    # Get employee details
    emp_doc = frappe.get_doc("Employee", employee)
    print(f"Employee: {emp_doc.employee_name}")

    # Get checkins for this employee on this date
    checkins = frappe.db.sql("""
        SELECT name, time, log_type, device_id
        FROM `tabEmployee Checkin`
        WHERE employee = %s
        AND DATE(time) = %s
        ORDER BY time
    """, (employee, date_str), as_dict=True)

    print(f"\nCheckins found: {len(checkins)}")
    for c in checkins:
        print(f"  {c['time']} | {c['log_type']} | {c['device_id']}")

    # Check existing Attendance Regularization
    existing_reg = frappe.db.get_value(
        "Attendance Regularization",
        {
            "employee": employee,
            "posting_date": date_str,
            "docstatus": ["<", 2]  # Not cancelled
        },
        ["name", "status", "late"],
        as_dict=True
    )

    if existing_reg:
        print(f"\nExisting Regularization: {existing_reg['name']}")
        print(f"  Status: {existing_reg['status']}")
        print(f"  Late: {existing_reg['late']}")

    # Get shift assignment
    shift_assignment = frappe.db.get_value(
        "Shift Assignment",
        {
            "employee": employee,
            "docstatus": 1,
            "start_date": ("<=", date)
        },
        ["shift_type", "start_date"],
        order_by="start_date desc",
        as_dict=True
    )

    if shift_assignment:
        print(f"\nShift: {shift_assignment['shift_type']}")

        shift = frappe.get_doc("Shift Type", shift_assignment['shift_type'])
        print(f"  Start Time: {shift.start_time}")
        print(f"  End Time: {shift.end_time}")

        # Calculate actual working hours
        if len(checkins) >= 2:
            first_in = checkins[0]['time']
            last_out = checkins[-1]['time']

            from datetime import timedelta

            # Combine date with shift times for comparison
            shift_start = datetime.combine(date, (datetime.min + shift.start_time).time())
            shift_end = datetime.combine(date, (datetime.min + shift.end_time).time())

            print(f"\nActual IN: {first_in}")
            print(f"Actual OUT: {last_out}")
            print(f"Shift Start: {shift_start}")
            print(f"Shift End: {shift_end}")

            # Check if late
            if first_in > shift_start:
                late_minutes = (first_in - shift_start).total_seconds() / 60
                print(f"\nLate by: {late_minutes:.0f} minutes")
            else:
                print(f"\nNot late - arrived on time or early")

            # Working duration
            working_duration = last_out - first_in
            print(f"Working Duration: {working_duration}")

    # Now update or create the Attendance Regularization
    print(f"\n{'='*70}")
    print(f"UPDATING ATTENDANCE REGULARIZATION")
    print(f"{'='*70}")

    from hamptons.overrides.employee_checkin import process_employee_checkins

    if len(checkins) >= 2:
        # Call the helper function to process this employee
        result = process_employee_checkins(employee, checkins, date, shift_assignment['shift_type'] if shift_assignment else None)
        print(f"\nResult: {result}")
    else:
        print(f"\nNot enough checkins to create a complete attendance record")

    return True


def process_employee_checkins(employee, checkins, date, shift_name):
    """Process checkins for a single employee and update regularization."""
    from datetime import timedelta

    if not shift_name or len(checkins) < 2:
        return {"status": "skipped", "reason": "No shift or insufficient checkins"}

    # Get shift details
    shift = frappe.get_doc("Shift Type", shift_name)

    first_in = checkins[0]['time']
    last_out = checkins[-1]['time']

    # Shift times as datetime
    shift_start = datetime.combine(date, (datetime.min + shift.start_time).time())
    shift_end = datetime.combine(date, (datetime.min + shift.end_time).time())

    # Check for existing draft regularization
    existing_reg = frappe.db.get_value(
        "Attendance Regularization",
        {
            "employee": employee,
            "posting_date": date,
            "docstatus": 0  # Draft only
        },
        "name"
    )

    if existing_reg:
        reg = frappe.get_doc("Attendance Regularization", existing_reg)
        print(f"Updating existing regularization: {reg.name}")
    else:
        # Create new regularization
        reg = frappe.new_doc("Attendance Regularization")
        reg.employee = employee
        reg.posting_date = date
        reg.shift = shift_name
        print("Creating new regularization")

    # Clear and rebuild the items
    reg.attendance_regularization_item = []

    for c in checkins:
        reg.append("attendance_regularization_item", {
            "log_type": c['log_type'],
            "check_in_time": c['time'],
            "device_id": c.get('device_id', '')
        })

    # Calculate late value
    if first_in > shift_start:
        late_seconds = (first_in - shift_start).total_seconds()
        late_hours = int(late_seconds // 3600)
        late_minutes = int((late_seconds % 3600) // 60)
        late_secs = int(late_seconds % 60)
        late_time = timedelta(hours=late_hours, minutes=late_minutes, seconds=late_secs)
        reg.late = str(late_time)
        print(f"Setting late to: {reg.late}")
    else:
        reg.late = None
        print("No late time")

    reg.save(ignore_permissions=True)
    frappe.db.commit()

    print(f"Saved regularization: {reg.name}")
    return {"status": "success", "name": reg.name}


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()

    # Consolidate for employee 1037 on 2026-01-25
    consolidate_for_employee("HR-EMP-01037", "2026-01-25")

    frappe.db.close()

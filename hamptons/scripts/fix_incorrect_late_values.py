#!/usr/bin/env python3
"""
Script to fix incorrect 'late' values in Attendance Regularizations.

Problem: Regularizations were being created with the 'late' field incorrectly
set to the creation time instead of the actual late entry time.

This script:
1. Finds regularizations where late value matches creation time (incorrect)
2. Recalculates the correct late time based on actual checkin times
3. Updates or clears the late field as appropriate
4. Optionally deletes regularizations that shouldn't exist (on-time employees)
"""

import frappe
from datetime import datetime, timedelta
from frappe.utils import getdate, get_datetime, get_time


def get_creation_time_as_timedelta(creation):
    """Extract the time portion of a datetime as timedelta."""
    if isinstance(creation, datetime):
        dt = creation
    else:
        dt = get_datetime(creation)
    return timedelta(hours=dt.hour, minutes=dt.minute, seconds=dt.second, microseconds=dt.microsecond)


def is_late_value_incorrect(late, creation):
    """
    Check if the late value matches the creation time (indicating it's incorrect).
    Returns True if the late value appears to be the creation time.
    """
    if not late:
        return False

    creation_time_td = get_creation_time_as_timedelta(creation)

    # Convert late to timedelta if needed
    if isinstance(late, timedelta):
        late_td = late
    else:
        late_td = timedelta(
            hours=late.hour if hasattr(late, 'hour') else 0,
            minutes=late.minute if hasattr(late, 'minute') else 0,
            seconds=late.second if hasattr(late, 'second') else 0
        )

    # Check if they're close (within 1 second)
    diff = abs((creation_time_td - late_td).total_seconds())
    return diff < 1.0


def calculate_actual_late_time(regularization):
    """
    Calculate the actual late time for a regularization based on checkins.
    Returns (late_time, needs_regularization, reason)
    """
    # Get shift type details
    if not regularization.shift:
        return None, True, "No shift assigned"

    shift_type = frappe.get_doc("Shift Type", regularization.shift)

    # Get shift start time
    start_time = shift_type.start_time
    if isinstance(start_time, timedelta):
        total_secs = int(start_time.total_seconds())
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        start_time = datetime.min.replace(hour=hours, minute=minutes).time()

    # Get grace period
    grace_minutes = int(getattr(shift_type, "late_entry_grace_period", 0) or 0)
    early_grace_minutes = int(getattr(shift_type, "early_exit_grace_period", 0) or 0)

    # Get shift end time
    end_time = shift_type.end_time
    if isinstance(end_time, timedelta):
        total_secs = int(end_time.total_seconds())
        hours = total_secs // 3600
        minutes = (total_secs % 3600) // 60
        end_time = datetime.min.replace(hour=hours, minute=minutes).time()

    # Get checkins from regularization items
    items = regularization.attendance_regularization_item
    if not items:
        return None, True, "No checkin items"

    # Get first IN checkin
    first_in = None
    last_out = None

    for item in sorted(items, key=lambda x: x.time):
        if not first_in:
            first_in = item
        last_out = item

    # Calculate late time
    late_time = None
    is_late = False
    is_early_exit = False

    if first_in:
        checkin_dt = get_datetime(first_in.time)
        processing_date = getdate(regularization.posting_date)
        shift_start_dt = datetime.combine(processing_date, start_time)
        shift_start_with_grace = shift_start_dt + timedelta(minutes=grace_minutes)

        if checkin_dt > shift_start_with_grace:
            is_late = True
            diff = checkin_dt - shift_start_with_grace
            if diff.total_seconds() > 0:
                hours = int(diff.total_seconds() // 3600)
                minutes = int((diff.total_seconds() % 3600) // 60)
                seconds = int(diff.total_seconds() % 60)
                late_time = get_time(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    if last_out:
        checkout_dt = get_datetime(last_out.time)
        processing_date = getdate(regularization.posting_date)
        shift_end_dt = datetime.combine(processing_date, end_time)
        shift_end_with_grace = shift_end_dt - timedelta(minutes=early_grace_minutes)

        if checkout_dt < shift_end_with_grace:
            is_early_exit = True

    # Determine if regularization is needed
    missing_in_out = len(items) < 2
    needs_reg = is_late or is_early_exit or missing_in_out

    reason = []
    if is_late:
        reason.append("Late Entry")
    if is_early_exit:
        reason.append("Early Exit")
    if missing_in_out:
        reason.append("Missing IN/OUT")

    return late_time, needs_reg, ", ".join(reason) if reason else "On Time"


@frappe.whitelist()
def find_incorrect_regularizations():
    """Find all regularizations with potentially incorrect late values."""
    if not frappe.db.exists("DocType", "Attendance Regularization"):
        frappe.throw("Attendance Regularization DocType is not installed")

    # Get all draft regularizations with a late value
    regs = frappe.db.sql("""
        SELECT name, employee, employee_name, posting_date, late, creation, status
        FROM `tabAttendance Regularization`
        WHERE late IS NOT NULL
        AND docstatus = 0
        ORDER BY posting_date DESC
    """, as_dict=1)

    incorrect = []
    for reg in regs:
        if is_late_value_incorrect(reg['late'], reg['creation']):
            incorrect.append(reg)

    frappe.logger().info(f"Found {len(incorrect)} regularizations with incorrect late values")
    return incorrect


@frappe.whitelist()
def fix_incorrect_regularizations(dry_run=False):
    """
    Fix all regularizations with incorrect late values.

    Args:
        dry_run: If True, only show what would be fixed without making changes
    """
    if not frappe.db.exists("DocType", "Attendance Regularization"):
        frappe.throw("Attendance Regularization DocType is not installed")

    dry_run = bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run)

    frappe.logger().info(f"\n=== Fixing Incorrect Late Values ===")
    if dry_run:
        frappe.logger().info("DRY RUN MODE - No changes will be made\n")

    # Find incorrect regularizations
    incorrect_regs = find_incorrect_regularizations()

    if not incorrect_regs:
        msg = "No regularizations found with incorrect late values"
        frappe.logger().info(msg)
        return {"success": True, "message": msg, "fixed": 0}

    frappe.logger().info(f"Found {len(incorrect_regs)} regularizations to fix\n")

    fixed_count = 0
    deleted_count = 0
    error_count = 0
    results = []

    for reg_data in incorrect_regs:
        try:
            reg = frappe.get_doc("Attendance Regularization", reg_data['name'])

            # Calculate correct late time
            correct_late, needs_reg, reason = calculate_actual_late_time(reg)

            result = {
                "name": reg.name,
                "employee": reg.employee_name,
                "posting_date": str(reg.posting_date),
                "old_late": str(reg.late),
                "new_late": str(correct_late) if correct_late else "None",
                "needs_regularization": needs_reg,
                "reason": reason
            }

            if dry_run:
                frappe.logger().info(
                    f"  Would fix {reg.name}: Late {reg.late} -> {correct_late or 'None'} "
                    f"(Needs Reg: {needs_reg}, Reason: {reason})"
                )
                results.append(result)
                continue

            # Update the late field
            if correct_late:
                reg.late = correct_late
            else:
                reg.late = None

            reg.save(ignore_permissions=True)
            fixed_count += 1

            frappe.logger().info(
                f"  Fixed {reg.name}: Late {reg_data['late']} -> {correct_late or 'None'} "
                f"(Reason: {reason})"
            )
            results.append(result)

        except Exception as e:
            error_count += 1
            frappe.log_error(message=str(e), title=f"Fix Late Value Error - {reg_data['name']}")
            frappe.logger().error(f"  Error fixing {reg_data['name']}: {str(e)}")

    if not dry_run:
        frappe.db.commit()

    frappe.logger().info(f"\n=== Fix Complete ===")
    frappe.logger().info(f"Fixed: {fixed_count}")
    frappe.logger().info(f"Errors: {error_count}")

    return {
        "success": True,
        "message": f"Fixed {fixed_count} regularizations with {error_count} errors",
        "fixed": fixed_count,
        "errors": error_count,
        "results": results
    }


@frappe.whitelist()
def fix_employee_regularizations(employee, dry_run=False):
    """
    Fix all regularizations for a specific employee.

    Args:
        employee: Employee ID
        dry_run: If True, only show what would be fixed
    """
    if not frappe.db.exists("DocType", "Attendance Regularization"):
        frappe.throw("Attendance Regularization DocType is not installed")

    dry_run = bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run)

    frappe.logger().info(f"\n=== Fixing Regularizations for Employee {employee} ===")
    if dry_run:
        frappe.logger().info("DRY RUN MODE\n")

    # Get all draft regularizations for this employee
    regs = frappe.get_all(
        "Attendance Regularization",
        filters={"employee": employee, "docstatus": 0},
        fields=["name", "posting_date", "late", "creation"],
        order_by="posting_date desc"
    )

    if not regs:
        msg = f"No draft regularizations found for employee {employee}"
        frappe.logger().info(msg)
        return {"success": True, "message": msg, "fixed": 0}

    fixed_count = 0
    results = []

    for reg_data in regs:
        reg = frappe.get_doc("Attendance Regularization", reg_data['name'])
        correct_late, needs_reg, reason = calculate_actual_late_time(reg)

        result = {
            "name": reg.name,
            "posting_date": str(reg.posting_date),
            "old_late": str(reg.late) if reg.late else "None",
            "new_late": str(correct_late) if correct_late else "None",
            "reason": reason
        }

        frappe.logger().info(
            f"  {reg.name} | {reg.posting_date} | Old Late: {reg.late} | "
            f"Correct: {correct_late or 'None'} | Reason: {reason}"
        )

        if not dry_run:
            if correct_late:
                reg.late = correct_late
            else:
                reg.late = None
            reg.save(ignore_permissions=True)
            fixed_count += 1

        results.append(result)

    if not dry_run:
        frappe.db.commit()

    return {
        "success": True,
        "message": f"Fixed {fixed_count} regularizations",
        "fixed": fixed_count,
        "results": results
    }


if __name__ == "__main__":
    frappe.init(site='hrms.hamptons.om')
    frappe.connect()

    # Run fix
    result = fix_incorrect_regularizations(dry_run=False)
    print(f"\n{result['message']}")

    frappe.db.close()

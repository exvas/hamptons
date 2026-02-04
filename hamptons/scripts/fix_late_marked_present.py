#!/usr/bin/env python3
"""
Script to fix incorrect "Present" attendance records where employees were actually late.

Problem: The scheduler was marking employees as "Present" even when they arrived late
(beyond the grace period). This should have created a Regularization instead.

This script:
1. Finds all Present attendance where employee was late (checkin > shift start + grace)
2. Cancels those incorrect attendance records
3. Re-runs consolidation to create proper regularizations
"""

import frappe
from datetime import datetime, timedelta
from frappe.utils import getdate, get_datetime


def find_late_employees_marked_present(days_back=30, employee=None):
    """
    Find all "Present" attendance records where the employee was actually late.

    Args:
        days_back: Number of days to look back
        employee: Optional employee ID to filter

    Returns:
        List of attendance records that need fixing
    """
    employee_filter = f"AND att.employee = '{employee}'" if employee else ""

    # Find Present attendance where first checkin was after shift start + grace
    results = frappe.db.sql(f"""
        SELECT
            att.name as attendance,
            att.employee,
            att.employee_name,
            att.attendance_date,
            att.status,
            MIN(ec.time) as first_checkin,
            st.name as shift_name,
            st.start_time as shift_start,
            st.late_entry_grace_period as grace_minutes
        FROM `tabAttendance` att
        INNER JOIN `tabEmployee Checkin` ec
            ON ec.employee = att.employee
            AND DATE(ec.time) = att.attendance_date
        INNER JOIN `tabShift Assignment` sa
            ON sa.employee = att.employee
            AND sa.docstatus = 1
            AND sa.start_date <= att.attendance_date
            AND (sa.end_date IS NULL OR sa.end_date >= att.attendance_date)
        INNER JOIN `tabShift Type` st ON st.name = sa.shift_type
        WHERE att.status = 'Present'
        AND att.docstatus = 1
        AND att.attendance_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        AND NOT EXISTS (
            SELECT 1 FROM `tabAttendance Regularization` ar
            WHERE ar.employee = att.employee
            AND ar.posting_date = att.attendance_date
        )
        {employee_filter}
        GROUP BY att.name
        ORDER BY att.attendance_date DESC
    """, (days_back,), as_dict=1)

    # Filter to only those who were actually late
    late_records = []
    for record in results:
        first_checkin = get_datetime(record['first_checkin'])
        shift_start = record['shift_start']
        grace_minutes = int(record['grace_minutes'] or 0)

        # Convert shift_start to datetime
        if isinstance(shift_start, timedelta):
            total_secs = int(shift_start.total_seconds())
            hours = total_secs // 3600
            minutes = (total_secs % 3600) // 60
            shift_start_dt = datetime.combine(first_checkin.date(), datetime.min.time().replace(hour=hours, minute=minutes))
        else:
            shift_start_dt = datetime.combine(first_checkin.date(), shift_start)

        shift_start_with_grace = shift_start_dt + timedelta(minutes=grace_minutes)

        # Check if employee was late
        if first_checkin > shift_start_with_grace:
            late_by = first_checkin - shift_start_with_grace
            late_minutes = int(late_by.total_seconds() / 60)
            record['late_by_minutes'] = late_minutes
            record['late_by_str'] = f"{late_minutes // 60}h {late_minutes % 60}m" if late_minutes >= 60 else f"{late_minutes}m"
            late_records.append(record)

    return late_records


@frappe.whitelist()
def fix_late_marked_present(days_back=30, employee=None, dry_run=False):
    """
    Fix incorrect "Present" attendance for employees who were actually late.

    Args:
        days_back: Number of days to look back
        employee: Optional employee ID to fix only that employee
        dry_run: If True, only show what would be fixed
    """
    from hamptons.overrides.employee_checkin import consolidate_attendance_for_date

    if not frappe.db.exists("DocType", "Attendance Regularization"):
        frappe.throw("Attendance Regularization DocType is not installed")

    days_back = int(days_back)
    dry_run = bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run)

    frappe.logger().info(f"\n=== Fixing Late Employees Marked as Present ===")
    if dry_run:
        frappe.logger().info("DRY RUN MODE - No changes will be made\n")

    # Find late employees marked as Present
    late_records = find_late_employees_marked_present(days_back, employee)

    if not late_records:
        msg = f"No incorrect 'Present' attendance found for late employees in the last {days_back} days"
        frappe.logger().info(msg)
        return {"success": True, "message": msg, "fixed": 0}

    frappe.logger().info(f"Found {len(late_records)} incorrect records:\n")

    for record in late_records:
        frappe.logger().info(
            f"  {record['attendance']} | {record['employee_name']} | {record['attendance_date']} | "
            f"Checkin: {record['first_checkin']} | Late by: {record['late_by_str']}"
        )

    if dry_run:
        return {
            "success": True,
            "message": f"DRY RUN: Would fix {len(late_records)} records",
            "would_fix": len(late_records),
            "records": late_records
        }

    # Cancel incorrect attendance and re-run consolidation
    frappe.logger().info(f"\nCancelling {len(late_records)} incorrect attendance records...\n")

    cancelled_count = 0
    error_count = 0
    dates_to_reprocess = set()

    for record in late_records:
        try:
            att = frappe.get_doc("Attendance", record['attendance'])
            att.cancel()
            cancelled_count += 1
            dates_to_reprocess.add(record['attendance_date'])
            frappe.logger().info(f"  ✓ Cancelled {record['attendance']} for {record['employee_name']}")
        except Exception as e:
            error_count += 1
            frappe.log_error(message=str(e), title=f"Cancel Attendance Error - {record['attendance']}")
            frappe.logger().error(f"  ✗ Error cancelling {record['attendance']}: {str(e)}")

    frappe.db.commit()

    # Re-process affected dates
    frappe.logger().info(f"\nRe-processing {len(dates_to_reprocess)} affected dates...\n")

    processed_count = 0
    reprocess_errors = 0

    for date in sorted(dates_to_reprocess, reverse=True):
        try:
            stats = consolidate_attendance_for_date(getdate(date))
            processed_count += 1
            frappe.logger().info(
                f"  ✓ Processed {date}: Present={stats.get('present', 0)}, "
                f"Reg={stats.get('regularizations', 0)}"
            )
            frappe.db.commit()
        except Exception as e:
            reprocess_errors += 1
            frappe.log_error(message=str(e), title=f"Re-process Date Error - {date}")
            frappe.logger().error(f"  ✗ Error processing {date}: {str(e)}")

    frappe.logger().info(f"\n=== Fix Complete ===")
    frappe.logger().info(f"Cancelled: {cancelled_count} attendance records")
    frappe.logger().info(f"Cancel Errors: {error_count}")
    frappe.logger().info(f"Re-processed: {processed_count} dates")
    frappe.logger().info(f"Re-process Errors: {reprocess_errors}")

    return {
        "success": True,
        "message": f"Cancelled {cancelled_count} incorrect attendance and re-processed {processed_count} dates",
        "cancelled": cancelled_count,
        "cancel_errors": error_count,
        "dates_processed": processed_count,
        "reprocess_errors": reprocess_errors
    }


if __name__ == "__main__":
    frappe.init(site='hrms.hamptons.om')
    frappe.connect()

    # First do a dry run
    print("\n=== DRY RUN ===")
    dry_result = fix_late_marked_present(days_back=60, dry_run=True)
    print(f"\n{dry_result['message']}")

    if dry_result.get('would_fix', 0) > 0:
        confirm = input("\nProceed with fix? (yes/no): ")
        if confirm.lower() == 'yes':
            result = fix_late_marked_present(days_back=60, dry_run=False)
            print(f"\n{result['message']}")

    frappe.db.close()

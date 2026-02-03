#!/usr/bin/env python3
"""
Script to fix incorrect "Absent" attendance records for employees who have checkins.

This happens when:
1. Scheduler ran at 8 PM but device was offline (no checkins)
2. Scheduler marked employees as "Absent" and submitted
3. Next day, device came online and synced checkins from previous day
4. But can't create regularizations because submitted Attendance exists

Solution:
1. Find submitted "Absent" attendance where checkins exist for that employee/date
2. Cancel those attendance records
3. Re-run consolidation to create proper regularizations or Present attendance
"""

import frappe
from frappe.utils import getdate


@frappe.whitelist()
def find_incorrect_absents(days_back=30):
    """
    Find "Absent" attendance records where checkins actually exist.

    Returns list of affected attendance records.
    """
    frappe.logger().info(f"Scanning for incorrect 'Absent' records in the last {days_back} days...")

    incorrect_absents = frappe.db.sql("""
        SELECT
            att.name,
            att.employee,
            att.employee_name,
            att.attendance_date,
            att.status,
            att.docstatus,
            COUNT(DISTINCT ec.name) as checkin_count
        FROM `tabAttendance` att
        INNER JOIN `tabEmployee Checkin` ec
            ON ec.employee = att.employee
            AND DATE(ec.time) = att.attendance_date
        WHERE att.status = 'Absent'
        AND att.docstatus = 1
        AND att.attendance_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        GROUP BY att.name
        ORDER BY att.attendance_date DESC, att.employee_name
    """, days_back, as_dict=1)

    frappe.logger().info(f"Found {len(incorrect_absents)} incorrect 'Absent' records with checkins")

    return incorrect_absents


@frappe.whitelist()
def fix_incorrect_absents(days_back=30, dry_run=False):
    """
    Cancel incorrect "Absent" attendance and re-process those dates.

    Args:
        days_back: Number of days to look back
        dry_run: If True, only show what would be fixed without making changes
    """
    from hamptons.overrides.employee_checkin import consolidate_attendance_for_date

    if not frappe.db.exists("DocType", "Attendance Regularization"):
        frappe.throw("Attendance Regularization DocType is not installed on this site")

    days_back = int(days_back)
    dry_run = bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run)

    frappe.logger().info(f"\n=== Fixing Incorrect 'Absent' Records ===")
    frappe.logger().info(f"Scanning last {days_back} days...")
    if dry_run:
        frappe.logger().info("DRY RUN MODE - No changes will be made\n")

    # Find incorrect absents
    incorrect_absents = find_incorrect_absents(days_back)

    if not incorrect_absents:
        msg = f"No incorrect 'Absent' records found in the last {days_back} days"
        frappe.logger().info(msg)
        return {"success": True, "message": msg, "fixed_count": 0}

    frappe.logger().info(f"\nFound {len(incorrect_absents)} incorrect records:\n")
    for rec in incorrect_absents[:10]:  # Show first 10
        frappe.logger().info(
            f"  {rec['name']} | {rec['employee_name']} | {rec['attendance_date']} | "
            f"Checkins: {rec['checkin_count']}"
        )

    if dry_run:
        return {
            "success": True,
            "message": f"DRY RUN: Would fix {len(incorrect_absents)} records",
            "would_fix": len(incorrect_absents),
            "records": incorrect_absents
        }

    # Cancel incorrect attendance records
    frappe.logger().info(f"\nCancelling {len(incorrect_absents)} incorrect attendance records...\n")
    cancelled_count = 0
    error_count = 0

    for rec in incorrect_absents:
        try:
            att = frappe.get_doc("Attendance", rec['name'])
            att.cancel()
            cancelled_count += 1
            frappe.logger().info(f"  ✓ Cancelled {rec['name']} for {rec['employee_name']}")
        except Exception as e:
            error_count += 1
            frappe.log_error(message=str(e), title=f"Cancel Attendance Error - {rec['name']}")
            frappe.logger().error(f"  ✗ Error cancelling {rec['name']}: {str(e)}")

    frappe.db.commit()

    # Re-process affected dates
    frappe.logger().info(f"\nRe-processing affected dates...\n")
    affected_dates = list(set([rec['attendance_date'] for rec in incorrect_absents]))
    affected_dates.sort(reverse=True)

    processed_count = 0
    reprocess_errors = 0

    for date in affected_dates:
        try:
            stats = consolidate_attendance_for_date(date)
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
        "message": f"Fixed {cancelled_count} incorrect absents and re-processed {processed_count} dates",
        "cancelled": cancelled_count,
        "cancel_errors": error_count,
        "dates_processed": processed_count,
        "reprocess_errors": reprocess_errors,
        "affected_dates": [str(d) for d in affected_dates]
    }


if __name__ == "__main__":
    # For direct execution
    frappe.init(site='hrms.hamptons.om')
    frappe.connect()

    # First do a dry run
    print("\n=== DRY RUN ===")
    dry_result = fix_incorrect_absents(days_back=30, dry_run=True)
    print(f"\n{dry_result['message']}")

    if dry_result.get('would_fix', 0) > 0:
        confirm = input("\nProceed with fix? (yes/no): ")
        if confirm.lower() == 'yes':
            result = fix_incorrect_absents(days_back=30, dry_run=False)
            print(f"\n{result['message']}")

    frappe.db.close()

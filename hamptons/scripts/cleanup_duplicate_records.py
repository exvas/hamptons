#!/usr/bin/env python3
"""
Script to clean up records where both a Present Attendance AND a pending
Regularization exist for the same employee/date.

This situation shouldn't occur - if attendance is Present, no regularization
should be pending. This script deletes the incorrect draft regularizations.
"""

import frappe


@frappe.whitelist()
def find_duplicate_records():
    """
    Find all cases where both a Present/submitted Attendance AND a draft
    Regularization exist for the same employee/date.
    """
    duplicates = frappe.db.sql("""
        SELECT
            ar.name as regularization,
            ar.employee,
            ar.employee_name,
            ar.posting_date,
            ar.status as reg_status,
            ar.late,
            att.name as attendance,
            att.status as att_status
        FROM `tabAttendance Regularization` ar
        INNER JOIN `tabAttendance` att
            ON att.employee = ar.employee
            AND att.attendance_date = ar.posting_date
            AND att.docstatus = 1
            AND att.status = 'Present'
        WHERE ar.docstatus = 0
        ORDER BY ar.posting_date DESC, ar.employee_name
    """, as_dict=1)

    frappe.logger().info(f"Found {len(duplicates)} duplicate records (Present attendance + draft regularization)")
    return duplicates


@frappe.whitelist()
def cleanup_duplicate_records(dry_run=False):
    """
    Delete draft regularizations where a Present attendance already exists.

    Args:
        dry_run: If True, only show what would be deleted
    """
    dry_run = bool(int(dry_run)) if isinstance(dry_run, str) else bool(dry_run)

    frappe.logger().info("\n=== Cleaning Up Duplicate Records ===")
    if dry_run:
        frappe.logger().info("DRY RUN MODE - No changes will be made\n")

    duplicates = find_duplicate_records()

    if not duplicates:
        msg = "No duplicate records found"
        frappe.logger().info(msg)
        return {"success": True, "message": msg, "deleted": 0}

    frappe.logger().info(f"Found {len(duplicates)} regularizations to delete:\n")

    deleted_count = 0
    error_count = 0

    for dup in duplicates:
        frappe.logger().info(
            f"  {dup['regularization']} | {dup['employee_name']} | {dup['posting_date']} | "
            f"Late: {dup['late']} | ATT: {dup['attendance']} (Present)"
        )

        if dry_run:
            continue

        try:
            frappe.delete_doc("Attendance Regularization", dup['regularization'], force=True)
            deleted_count += 1
        except Exception as e:
            error_count += 1
            frappe.log_error(
                message=str(e),
                title=f"Delete Regularization Error - {dup['regularization']}"
            )
            frappe.logger().error(f"    Error deleting: {str(e)}")

    if not dry_run:
        frappe.db.commit()

    frappe.logger().info(f"\n=== Cleanup Complete ===")
    frappe.logger().info(f"Deleted: {deleted_count}")
    frappe.logger().info(f"Errors: {error_count}")

    return {
        "success": True,
        "message": f"Deleted {deleted_count} duplicate regularizations with {error_count} errors",
        "deleted": deleted_count,
        "errors": error_count
    }


if __name__ == "__main__":
    frappe.init(site='hrms.hamptons.om')
    frappe.connect()

    result = cleanup_duplicate_records(dry_run=False)
    print(f"\n{result['message']}")

    frappe.db.close()

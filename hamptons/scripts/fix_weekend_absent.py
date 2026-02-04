#!/usr/bin/env python3
"""
Script to delete incorrect Absent attendance records on weekends (holidays/weekly offs).

This fixes the historical data where Absent was incorrectly marked on Fridays and Saturdays.
"""

import frappe
from frappe.utils import getdate


def fix_weekend_absent_records(dry_run=True):
    """
    Delete Absent attendance records that were incorrectly created on weekends/holidays.

    Args:
        dry_run: If True, only report what would be deleted without actually deleting
    """
    print("=" * 70)
    print(f"FIXING INCORRECT ABSENT RECORDS ON WEEKENDS {'(DRY RUN)' if dry_run else ''}")
    print("=" * 70)

    # Find all Absent attendance records on dates that are holidays/weekly offs
    # We'll check each employee's holiday list
    incorrect_records = frappe.db.sql("""
        SELECT
            a.name,
            a.employee,
            e.employee_name,
            a.attendance_date,
            DAYNAME(a.attendance_date) as day_name,
            e.holiday_list
        FROM `tabAttendance` a
        JOIN `tabEmployee` e ON a.employee = e.name
        WHERE a.status = 'Absent'
        AND a.docstatus = 1
        AND EXISTS (
            SELECT 1 FROM `tabHoliday` h
            WHERE h.parent = e.holiday_list
            AND h.holiday_date = a.attendance_date
        )
        ORDER BY a.attendance_date, a.employee
    """, as_dict=True)

    print(f"\nFound {len(incorrect_records)} Absent records on holidays/weekly offs")

    if not incorrect_records:
        print("No incorrect records to fix!")
        return {"deleted": 0, "errors": 0}

    # Group by date for summary
    by_date = {}
    for r in incorrect_records:
        date_key = str(r['attendance_date'])
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append(r)

    print(f"\nBreakdown by date:")
    for date, records in sorted(by_date.items())[:20]:  # Show first 20 dates
        day_name = records[0]['day_name']
        print(f"  {date} ({day_name}): {len(records)} records")

    if len(by_date) > 20:
        print(f"  ... and {len(by_date) - 20} more dates")

    if dry_run:
        print(f"\n[DRY RUN] Would cancel and delete {len(incorrect_records)} Absent records")
        print("\nSample records that would be deleted:")
        for r in incorrect_records[:10]:
            print(f"  {r['name']} | {r['employee']} - {r['employee_name']} | {r['attendance_date']} ({r['day_name']})")
        return {"would_delete": len(incorrect_records), "errors": 0}

    # Actually delete the records
    deleted = 0
    errors = 0

    print(f"\nDeleting {len(incorrect_records)} incorrect Absent records...")

    for r in incorrect_records:
        try:
            # Cancel the attendance first (required before deletion)
            att = frappe.get_doc("Attendance", r['name'])
            att.cancel()

            # Delete the cancelled attendance
            frappe.delete_doc("Attendance", r['name'], force=True)
            deleted += 1

            if deleted % 100 == 0:
                print(f"  Deleted {deleted}/{len(incorrect_records)}...")
                frappe.db.commit()

        except Exception as e:
            errors += 1
            frappe.log_error(
                message=f"Error deleting {r['name']}: {str(e)}",
                title="Fix Weekend Absent - Delete Error"
            )

    frappe.db.commit()

    print(f"\n{'=' * 70}")
    print(f"COMPLETED: Deleted {deleted} records, {errors} errors")
    print(f"{'=' * 70}")

    return {"deleted": deleted, "errors": errors}


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()

    # Run in dry_run mode first to see what would be deleted
    fix_weekend_absent_records(dry_run=True)

    frappe.db.close()

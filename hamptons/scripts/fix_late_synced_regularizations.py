#!/usr/bin/env python3
"""
Script to fix Attendance Regularizations for dates with late-synced checkins.

Usage:
    bench --site hrms.hamptons.om execute hamptons.scripts.fix_late_synced_regularizations.fix_all_affected_dates
"""

import frappe
from datetime import timedelta
from frappe.utils import getdate


def find_affected_dates(days_back=30):
    """
    Find dates where checkins were synced late and might be missing from regularizations.
    Returns list of dates that need re-processing.
    """
    frappe.logger().info(f"Scanning for late-synced checkins in the last {days_back} days...")

    # Find dates where checkins have punch date != sync date
    affected = frappe.db.sql("""
        SELECT DISTINCT DATE(ec.time) as punch_date
        FROM `tabEmployee Checkin` ec
        WHERE DATE(ec.time) != DATE(ec.creation)
        AND DATE(ec.time) >= DATE_SUB(CURDATE(), INTERVAL %s DAY)
        ORDER BY punch_date DESC
    """, days_back, as_dict=1)

    dates = [r['punch_date'] for r in affected]
    frappe.logger().info(f"Found {len(dates)} dates with late-synced checkins: {dates}")

    return dates


def fix_date(processing_date):
    """
    Re-run consolidation for a specific date to fix missing regularizations.
    """
    from hamptons.overrides.employee_checkin import consolidate_attendance_for_date

    frappe.logger().info(f"Re-processing attendance for {processing_date}...")

    try:
        stats = consolidate_attendance_for_date(processing_date)
        frappe.logger().info(
            f"Fixed {processing_date}: Present={stats.get('present', 0)}, "
            f"Regularizations={stats.get('regularizations', 0)}, "
            f"Absent={stats.get('absent', 0)}, Leave={stats.get('leave', 0)}"
        )
        return stats
    except Exception as e:
        frappe.log_error(message=str(e), title=f"Fix Date Error - {processing_date}")
        frappe.logger().error(f"Error fixing {processing_date}: {str(e)}")
        return None


@frappe.whitelist()
def fix_all_affected_dates(days_back=30):
    """
    Find and fix all dates with late-synced checkins.

    Args:
        days_back: Number of days to look back (default 30)
    """
    if not frappe.db.exists("DocType", "Attendance Regularization"):
        frappe.throw("Attendance Regularization DocType is not installed on this site")

    # Convert to int if passed as string from web
    days_back = int(days_back)

    frappe.logger().info(f"\n=== Starting Late-Sync Regularization Fix ===")
    frappe.logger().info(f"Scanning last {days_back} days...\n")

    # Find affected dates
    affected_dates = find_affected_dates(days_back)

    if not affected_dates:
        msg = f"No dates found with late-synced checkins in the last {days_back} days"
        frappe.logger().info(msg)
        return {"success": True, "message": msg, "dates_fixed": 0}

    frappe.logger().info(f"\nProcessing {len(affected_dates)} affected dates...\n")

    # Fix each date
    fixed_count = 0
    error_count = 0
    summary = []

    for date in affected_dates:
        stats = fix_date(date)
        if stats:
            fixed_count += 1
            summary.append({"date": str(date), **stats})
        else:
            error_count += 1

        # Commit after each date to avoid long transactions
        frappe.db.commit()

    frappe.logger().info(f"\n=== Fix Complete ===")
    frappe.logger().info(f"Dates fixed: {fixed_count}")
    frappe.logger().info(f"Errors: {error_count}")

    return {
        "success": True,
        "message": f"Fixed {fixed_count} dates with {error_count} errors",
        "dates_fixed": fixed_count,
        "errors": error_count,
        "summary": summary
    }


@frappe.whitelist()
def fix_specific_date(date_str):
    """
    Fix regularizations for a specific date.

    Args:
        date_str: Date string in YYYY-MM-DD format
    """
    if not frappe.db.exists("DocType", "Attendance Regularization"):
        frappe.throw("Attendance Regularization DocType is not installed on this site")

    processing_date = getdate(date_str)
    frappe.logger().info(f"\n=== Fixing Regularization for {processing_date} ===\n")

    stats = fix_date(processing_date)
    frappe.db.commit()

    if stats:
        return {
            "success": True,
            "message": f"Fixed {processing_date}",
            "stats": stats
        }
    else:
        return {
            "success": False,
            "message": f"Error fixing {processing_date}. Check Error Log for details."
        }


if __name__ == "__main__":
    # For direct execution
    frappe.init(site='hrms.hamptons.om')
    frappe.connect()

    result = fix_all_affected_dates(days_back=30)
    print(f"\n{result['message']}")
    print(f"\nSummary:")
    for item in result.get('summary', []):
        print(f"  {item['date']}: Present={item.get('present', 0)}, Reg={item.get('regularizations', 0)}")

    frappe.db.close()

#!/usr/bin/env python3
"""
Script to check for attendance records on weekends.
"""

import frappe
from datetime import datetime


def check_weekend_attendance():
    """Check for attendance records on weekends (Friday/Saturday for Oman)."""
    print("=" * 70)
    print("CHECKING WEEKEND ATTENDANCE RECORDS")
    print("=" * 70)

    # Get attendance records on weekends
    weekend_absent = frappe.db.sql("""
        SELECT
            COUNT(*) as count,
            status
        FROM `tabAttendance`
        WHERE docstatus = 1
        AND attendance_date >= '2026-01-01'
        AND DAYOFWEEK(attendance_date) IN (6, 7)
        GROUP BY status
    """, as_dict=True)

    print("\nAttendance on Weekends (Friday=6, Saturday=7):")
    for row in weekend_absent:
        print(f"  {row['status']}: {row['count']}")

    # Check specific employee 1037
    print("\n" + "=" * 70)
    print("Employee 1037 attendance on weekends:")
    emp_weekend = frappe.db.sql("""
        SELECT
            attendance_date,
            status,
            DAYNAME(attendance_date) as day_name
        FROM `tabAttendance`
        WHERE employee = '1037'
        AND docstatus = 1
        AND attendance_date >= '2026-01-01'
        AND DAYOFWEEK(attendance_date) IN (6, 7)
        ORDER BY attendance_date
    """, as_dict=True)

    for row in emp_weekend:
        print(f"  {row['attendance_date']} ({row['day_name']}): {row['status']}")

    # Check if there are checkins on weekends
    print("\n" + "=" * 70)
    print("Checkins on weekends (sample):")
    weekend_checkins = frappe.db.sql("""
        SELECT
            DATE(time) as checkin_date,
            employee,
            DAYNAME(DATE(time)) as day_name,
            COUNT(*) as cnt
        FROM `tabEmployee Checkin`
        WHERE DATE(time) >= '2026-01-01'
        AND DAYOFWEEK(DATE(time)) IN (6, 7)
        GROUP BY DATE(time), employee
        LIMIT 10
    """, as_dict=True)

    for row in weekend_checkins:
        print(f"  {row['checkin_date']} ({row['day_name']}) | Emp {row['employee']}: {row['cnt']} checkins")

    # Check the holiday list for weekends
    print("\n" + "=" * 70)
    print("Sample holidays marked as weekly_off:")
    holidays = frappe.db.sql("""
        SELECT holiday_date, description, weekly_off, parent
        FROM `tabHoliday`
        WHERE holiday_date BETWEEN '2026-01-01' AND '2026-02-28'
        AND weekly_off = 1
        LIMIT 10
    """, as_dict=True)

    for h in holidays:
        day_name = h['holiday_date'].strftime('%A')
        print(f"  {h['holiday_date']} ({day_name}) | {h['description']} | {h['parent']}")


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()
    check_weekend_attendance()
    frappe.db.close()

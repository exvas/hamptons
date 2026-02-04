#!/usr/bin/env python3
"""
Comprehensive investigation of Employee Checkin, Attendance, and Attendance Regularization records.
Checks for data consistency and anomalies.
"""

import frappe
from datetime import datetime, timedelta
from frappe.utils import getdate, today, get_datetime


def investigate_all():
    """Run all investigation checks and print results."""

    print("=" * 80)
    print("COMPREHENSIVE ATTENDANCE SYSTEM INVESTIGATION")
    print("=" * 80)

    # Basic statistics
    print("\n1. BASIC STATISTICS")
    print("-" * 40)

    checkin_count = frappe.db.count("Employee Checkin")
    attendance_count = frappe.db.count("Attendance", {"docstatus": 1})
    regularization_count = frappe.db.count("Attendance Regularization")

    print(f"  Employee Checkin records: {checkin_count}")
    print(f"  Attendance records (submitted): {attendance_count}")
    print(f"  Attendance Regularization records: {regularization_count}")

    # Check 1: Orphan checkins (no attendance or regularization)
    print("\n2. ORPHAN CHECKINS (checkins with no attendance or regularization)")
    print("-" * 40)

    orphan_checkins = frappe.db.sql("""
        SELECT
            ec.employee,
            DATE(ec.time) as checkin_date,
            COUNT(*) as checkin_count,
            MIN(ec.time) as first_checkin,
            MAX(ec.time) as last_checkin
        FROM `tabEmployee Checkin` ec
        WHERE NOT EXISTS (
            SELECT 1 FROM `tabAttendance` att
            WHERE att.employee = ec.employee
            AND att.attendance_date = DATE(ec.time)
            AND att.docstatus = 1
        )
        AND NOT EXISTS (
            SELECT 1 FROM `tabAttendance Regularization` ar
            WHERE ar.employee = ec.employee
            AND ar.posting_date = DATE(ec.time)
        )
        GROUP BY ec.employee, DATE(ec.time)
        ORDER BY DATE(ec.time) DESC, ec.employee
    """, as_dict=1)

    print(f"  Found {len(orphan_checkins)} employee-dates with orphan checkins")
    if orphan_checkins:
        print("  Sample orphan checkins:")
        for oc in orphan_checkins[:10]:
            emp_name = frappe.db.get_value("Employee", oc["employee"], "employee_name")
            print(f"    {oc['employee']} | {emp_name} | {oc['checkin_date']} | {oc['checkin_count']} checkins")

    # Check 2: Absent employees with checkins
    print("\n3. ABSENT EMPLOYEES WITH CHECKINS (should not happen)")
    print("-" * 40)

    absent_with_checkins = frappe.db.sql("""
        SELECT
            att.name as attendance,
            att.employee,
            att.employee_name,
            att.attendance_date,
            COUNT(ec.name) as checkin_count
        FROM `tabAttendance` att
        INNER JOIN `tabEmployee Checkin` ec
            ON ec.employee = att.employee
            AND DATE(ec.time) = att.attendance_date
        WHERE att.status = 'Absent'
        AND att.docstatus = 1
        GROUP BY att.name
        ORDER BY att.attendance_date DESC
        LIMIT 20
    """, as_dict=1)

    print(f"  Found {len(absent_with_checkins)} Absent attendance records WITH checkins")
    for awc in absent_with_checkins[:10]:
        print(f"    {awc['attendance']} | {awc['employee_name']} | {awc['attendance_date']} | {awc['checkin_count']} checkins")

    # Check 3: Present employees with regularization pending
    print("\n4. PRESENT EMPLOYEES WITH PENDING REGULARIZATION (duplicate state)")
    print("-" * 40)

    present_with_reg = frappe.db.sql("""
        SELECT
            att.name as attendance,
            att.employee,
            att.employee_name,
            att.attendance_date,
            ar.name as regularization,
            ar.status as reg_status,
            ar.late
        FROM `tabAttendance` att
        INNER JOIN `tabAttendance Regularization` ar
            ON ar.employee = att.employee
            AND ar.posting_date = att.attendance_date
        WHERE att.status = 'Present'
        AND att.docstatus = 1
        AND ar.docstatus = 0
        ORDER BY att.attendance_date DESC
    """, as_dict=1)

    print(f"  Found {len(present_with_reg)} Present attendance with pending regularization")
    for pwr in present_with_reg[:10]:
        print(f"    {pwr['attendance']} | {pwr['employee_name']} | {pwr['attendance_date']} | Reg: {pwr['regularization']} | Late: {pwr['late']}")

    # Check 4: Late employees marked as Present (no regularization)
    print("\n5. LATE EMPLOYEES MARKED AS PRESENT (should have regularization)")
    print("-" * 40)

    late_marked_present = frappe.db.sql("""
        SELECT
            att.name as attendance,
            att.employee,
            att.employee_name,
            att.attendance_date,
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
        AND NOT EXISTS (
            SELECT 1 FROM `tabAttendance Regularization` ar
            WHERE ar.employee = att.employee
            AND ar.posting_date = att.attendance_date
        )
        GROUP BY att.name
        ORDER BY att.attendance_date DESC
        LIMIT 100
    """, as_dict=1)

    late_count = 0
    for record in late_marked_present:
        first_checkin = get_datetime(record["first_checkin"])
        shift_start = record["shift_start"]
        grace_minutes = int(record["grace_minutes"] or 0)

        # Convert shift_start to datetime
        if isinstance(shift_start, timedelta):
            total_secs = int(shift_start.total_seconds())
            hours = total_secs // 3600
            minutes = (total_secs % 3600) // 60
            shift_start_dt = datetime.combine(first_checkin.date(), datetime.min.time().replace(hour=hours, minute=minutes))
        else:
            shift_start_dt = datetime.combine(first_checkin.date(), shift_start)

        shift_start_with_grace = shift_start_dt + timedelta(minutes=grace_minutes)

        if first_checkin > shift_start_with_grace:
            late_count += 1
            if late_count <= 10:
                late_by = first_checkin - shift_start_with_grace
                late_minutes = int(late_by.total_seconds() / 60)
                print(f"    {record['attendance']} | {record['employee_name']} | {record['attendance_date']} | Late by {late_minutes} min")

    print(f"  Found {late_count} late employees incorrectly marked as Present (no regularization)")

    # Check 5: Regularizations with incorrect late values (matches creation time)
    print("\n6. REGULARIZATIONS WITH POTENTIALLY INCORRECT LATE VALUES")
    print("-" * 40)

    regs_with_late = frappe.db.sql("""
        SELECT name, employee, employee_name, posting_date, late, creation
        FROM `tabAttendance Regularization`
        WHERE late IS NOT NULL
        AND docstatus = 0
        ORDER BY posting_date DESC
    """, as_dict=1)

    incorrect_late_count = 0
    for reg in regs_with_late:
        creation = get_datetime(reg["creation"])
        late = reg["late"]

        # Convert late to seconds for comparison
        if isinstance(late, timedelta):
            late_secs = late.total_seconds()
        else:
            late_secs = late.hour * 3600 + late.minute * 60 + late.second

        creation_secs = creation.hour * 3600 + creation.minute * 60 + creation.second

        # Check if late matches creation time (within 2 seconds)
        if abs(late_secs - creation_secs) < 2:
            incorrect_late_count += 1
            if incorrect_late_count <= 10:
                print(f"    {reg['name']} | {reg['employee_name']} | {reg['posting_date']} | Late: {late} (matches creation time)")

    print(f"  Found {incorrect_late_count} regularizations with incorrect late values")

    # Check 6: Duplicate checkins (same employee, same timestamp)
    print("\n7. DUPLICATE CHECKINS")
    print("-" * 40)

    duplicate_checkins = frappe.db.sql("""
        SELECT employee, time, COUNT(*) as count
        FROM `tabEmployee Checkin`
        GROUP BY employee, time
        HAVING COUNT(*) > 1
        ORDER BY time DESC
    """, as_dict=1)

    print(f"  Found {len(duplicate_checkins)} duplicate checkin entries")
    for dc in duplicate_checkins[:10]:
        emp_name = frappe.db.get_value("Employee", dc["employee"], "employee_name")
        print(f"    {dc['employee']} | {emp_name} | {dc['time']} | {dc['count']} duplicates")

    # Check 7: Checkins with only IN or only OUT for a day
    print("\n8. LOG TYPE ANALYSIS")
    print("-" * 40)

    log_type_stats = frappe.db.sql("""
        SELECT log_type, COUNT(*) as count
        FROM `tabEmployee Checkin`
        GROUP BY log_type
    """, as_dict=1)

    for stat in log_type_stats:
        print(f"  {stat['log_type']}: {stat['count']}")

    # Check 8: Regularization status breakdown
    print("\n9. REGULARIZATION STATUS BREAKDOWN")
    print("-" * 40)

    reg_status = frappe.db.sql("""
        SELECT status, docstatus, COUNT(*) as count
        FROM `tabAttendance Regularization`
        GROUP BY status, docstatus
        ORDER BY status, docstatus
    """, as_dict=1)

    for stat in reg_status:
        docstatus_text = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(stat["docstatus"], str(stat["docstatus"]))
        print(f"  {stat['status']} ({docstatus_text}): {stat['count']}")

    # Check 9: Attendance status breakdown
    print("\n10. ATTENDANCE STATUS BREAKDOWN")
    print("-" * 40)

    att_status = frappe.db.sql("""
        SELECT status, docstatus, COUNT(*) as count
        FROM `tabAttendance`
        GROUP BY status, docstatus
        ORDER BY status, docstatus
    """, as_dict=1)

    for stat in att_status:
        docstatus_text = {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(stat["docstatus"], str(stat["docstatus"]))
        print(f"  {stat['status']} ({docstatus_text}): {stat['count']}")

    # Check 10: Recent dates analysis
    print("\n11. LAST 7 DAYS ANALYSIS")
    print("-" * 40)

    recent_stats = frappe.db.sql("""
        SELECT
            d.date,
            (SELECT COUNT(*) FROM `tabEmployee Checkin` ec WHERE DATE(ec.time) = d.date) as checkins,
            (SELECT COUNT(*) FROM `tabAttendance` att WHERE att.attendance_date = d.date AND att.docstatus = 1 AND att.status = 'Present') as present,
            (SELECT COUNT(*) FROM `tabAttendance` att WHERE att.attendance_date = d.date AND att.docstatus = 1 AND att.status = 'Absent') as absent,
            (SELECT COUNT(*) FROM `tabAttendance Regularization` ar WHERE ar.posting_date = d.date) as regularizations
        FROM (
            SELECT CURDATE() - INTERVAL n DAY as date
            FROM (SELECT 0 n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6) nums
        ) d
        ORDER BY d.date DESC
    """, as_dict=1)

    print(f"  {'Date':<12} | {'Checkins':<10} | {'Present':<10} | {'Absent':<10} | {'Regularizations':<15}")
    print("  " + "-" * 65)
    for stat in recent_stats:
        print(f"  {str(stat['date']):<12} | {stat['checkins']:<10} | {stat['present']:<10} | {stat['absent']:<10} | {stat['regularizations']:<15}")

    # Summary
    print("\n" + "=" * 80)
    print("INVESTIGATION SUMMARY")
    print("=" * 80)

    issues = []
    if orphan_checkins:
        issues.append(f"- {len(orphan_checkins)} orphan checkins (no attendance/regularization)")
    if absent_with_checkins:
        issues.append(f"- {len(absent_with_checkins)} Absent with checkins (data inconsistency)")
    if present_with_reg:
        issues.append(f"- {len(present_with_reg)} Present with pending regularization (duplicate state)")
    if late_count > 0:
        issues.append(f"- {late_count} late employees marked Present (missing regularization)")
    if incorrect_late_count > 0:
        issues.append(f"- {incorrect_late_count} regularizations with incorrect late values")
    if duplicate_checkins:
        issues.append(f"- {len(duplicate_checkins)} duplicate checkin entries")

    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("\n  No major issues found! Data appears consistent.")

    return {
        "orphan_checkins": len(orphan_checkins),
        "absent_with_checkins": len(absent_with_checkins),
        "present_with_reg": len(present_with_reg),
        "late_marked_present": late_count,
        "incorrect_late_values": incorrect_late_count,
        "duplicate_checkins": len(duplicate_checkins)
    }


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()

    results = investigate_all()

    frappe.db.close()

#!/usr/bin/env python3
"""
Script to verify all attendance system fixes are permanently in place.
Checks code logic, not just data.
"""

import frappe


def verify_all_fixes():
    """Verify all permanent fixes are in place."""

    print("=" * 80)
    print("PERMANENT FIX VERIFICATION")
    print("=" * 80)

    results = {
        "passed": [],
        "failed": []
    }

    # 1. Verify scheduler is configured for 8 PM
    print("\n1. SCHEDULER CONFIGURATION")
    print("-" * 40)
    try:
        from hamptons.hooks import scheduler_events
        cron_jobs = scheduler_events.get("cron", {})
        if "0 20 * * *" in cron_jobs:
            jobs = cron_jobs["0 20 * * *"]
            if "hamptons.overrides.employee_checkin.daily_attendance_regularization_job" in jobs:
                print("  ✅ 8 PM scheduler job configured correctly")
                results["passed"].append("Scheduler configuration")
            else:
                print("  ❌ Scheduler job function not found")
                results["failed"].append("Scheduler job function missing")
        else:
            print("  ❌ 8 PM cron schedule not found")
            results["failed"].append("8 PM cron not configured")
    except Exception as e:
        print(f"  ❌ Error checking scheduler: {e}")
        results["failed"].append(f"Scheduler check error: {e}")

    # 2. Verify late value handling in consolidation
    print("\n2. LATE VALUE HANDLING IN CONSOLIDATION")
    print("-" * 40)
    try:
        import inspect
        from hamptons.overrides.employee_checkin import consolidate_attendance_for_date
        source = inspect.getsource(consolidate_attendance_for_date)

        # Check for correct late value handling
        if 'if late_time_val:' in source and 'reg_data["late"] = late_time_val' in source:
            print("  ✅ Late value only set when there's actual late time")
            results["passed"].append("Late value conditional setting")
        else:
            print("  ❌ Late value handling may be incorrect")
            results["failed"].append("Late value handling issue")

        # Check for clearing incorrect late values
        if 'elif reg.late:' in source and 'reg.late = None' in source:
            print("  ✅ Incorrect late values are cleared")
            results["passed"].append("Late value clearing")
        else:
            print("  ⚠️ Late value clearing logic not found")
            results["failed"].append("Late value clearing missing")

    except Exception as e:
        print(f"  ❌ Error checking consolidation: {e}")
        results["failed"].append(f"Consolidation check error: {e}")

    # 3. Verify late-synced checkin handling
    print("\n3. LATE-SYNCED CHECKIN HANDLING")
    print("-" * 40)
    try:
        import inspect
        from hamptons.overrides.employee_checkin import on_employee_checkin_submit
        source = inspect.getsource(on_employee_checkin_submit)

        if 'checkin_date < sync_date' in source:
            print("  ✅ Late-synced checkin detection in place")
            results["passed"].append("Late-sync detection")
        else:
            print("  ❌ Late-synced checkin detection missing")
            results["failed"].append("Late-sync detection missing")

        if 'consolidate_attendance_for_date' in source and 'frappe.enqueue' in source:
            print("  ✅ Consolidation triggered for late-synced checkins")
            results["passed"].append("Late-sync consolidation trigger")
        else:
            print("  ❌ Consolidation trigger for late-synced checkins missing")
            results["failed"].append("Late-sync consolidation trigger missing")

    except Exception as e:
        print(f"  ❌ Error checking late-sync handling: {e}")
        results["failed"].append(f"Late-sync check error: {e}")

    # 4. Verify email notification reason handling
    print("\n4. EMAIL NOTIFICATION REASON HANDLING")
    print("-" * 40)
    try:
        import inspect
        from hamptons.overrides.attendance_regularization import (
            after_insert_attendance_regularization,
            determine_regularization_reason
        )

        source = inspect.getsource(determine_regularization_reason)

        if "Late Entry" in source and "Missing Check-in" in source and "Early Exit" in source:
            print("  ✅ Reason determination includes all cases")
            results["passed"].append("Email reason determination")
        else:
            print("  ❌ Reason determination incomplete")
            results["failed"].append("Email reason incomplete")

        insert_source = inspect.getsource(after_insert_attendance_regularization)
        if 'reason=reason' in insert_source or 'reason=' in insert_source:
            print("  ✅ Reason passed to email function")
            results["passed"].append("Email reason passing")
        else:
            print("  ❌ Reason not passed to email")
            results["failed"].append("Email reason not passed")

    except Exception as e:
        print(f"  ❌ Error checking email: {e}")
        results["failed"].append(f"Email check error: {e}")

    # 5. Verify hook configurations
    print("\n5. HOOK CONFIGURATIONS")
    print("-" * 40)
    try:
        from hamptons.hooks import doc_events

        # Check Employee Checkin hook
        ec_hooks = doc_events.get("Employee Checkin", {})
        if "after_insert" in ec_hooks:
            print("  ✅ Employee Checkin after_insert hook configured")
            results["passed"].append("Employee Checkin hook")
        else:
            print("  ❌ Employee Checkin hook missing")
            results["failed"].append("Employee Checkin hook missing")

        # Check Attendance Regularization hook
        ar_hooks = doc_events.get("Attendance Regularization", {})
        if "after_insert" in ar_hooks:
            print("  ✅ Attendance Regularization after_insert hook configured")
            results["passed"].append("Attendance Regularization hook")
        else:
            print("  ❌ Attendance Regularization hook missing")
            results["failed"].append("Attendance Regularization hook missing")

    except Exception as e:
        print(f"  ❌ Error checking hooks: {e}")
        results["failed"].append(f"Hook check error: {e}")

    # 6. Verify incorrect regularization cleanup
    print("\n6. INCORRECT REGULARIZATION CLEANUP")
    print("-" * 40)
    try:
        import inspect
        from hamptons.overrides.employee_checkin import consolidate_attendance_for_date
        source = inspect.getsource(consolidate_attendance_for_date)

        if 'incorrect_reg' in source and 'frappe.delete_doc' in source:
            print("  ✅ Incorrect draft regularizations are cleaned up")
            results["passed"].append("Incorrect regularization cleanup")
        else:
            print("  ⚠️ Automatic cleanup logic not found")
            results["failed"].append("Cleanup logic missing")

    except Exception as e:
        print(f"  ❌ Error checking cleanup: {e}")
        results["failed"].append(f"Cleanup check error: {e}")

    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)

    print(f"\n✅ Passed: {len(results['passed'])}")
    for item in results['passed']:
        print(f"   - {item}")

    if results['failed']:
        print(f"\n❌ Failed: {len(results['failed'])}")
        for item in results['failed']:
            print(f"   - {item}")
    else:
        print("\n🎉 All permanent fixes verified!")

    return results


if __name__ == "__main__":
    frappe.init(site="hrms.hamptons.om")
    frappe.connect()

    verify_all_fixes()

    frappe.db.close()

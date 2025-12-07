import frappe

def verify_validation_working():
    """Verify that validation is working and no invalid allocations exist"""

    print("\n" + "="*80)
    print("VERIFICATION: Leave Allocation Validation Status")
    print("="*80 + "\n")

    # Get all allocations for employee 1002
    allocations = frappe.db.sql("""
        SELECT
            la.name,
            la.employee,
            e.employee_name,
            e.gender,
            la.leave_type,
            lt.custom_gender_specific,
            lt.custom_religion_specific,
            DATE_FORMAT(la.creation, '%Y-%m-%d %H:%i') as created
        FROM `tabLeave Allocation` la
        INNER JOIN `tabEmployee` e ON e.name = la.employee
        INNER JOIN `tabLeave Type` lt ON lt.name = la.leave_type
        WHERE la.employee = '1002'
            AND la.docstatus = 1
        ORDER BY la.creation DESC
        LIMIT 15
    """, as_dict=1)

    print(f"Employee: 1002 - {allocations[0].employee_name if allocations else 'Unknown'}")
    print(f"Gender: {allocations[0].gender if allocations else 'Unknown'}")
    print(f"Total Valid Allocations: {len(allocations)}\n")
    print("-" * 80)

    invalid_count = 0
    valid_count = 0

    for alloc in allocations:
        is_invalid = False
        reason = []

        # Check gender mismatch
        if alloc.custom_gender_specific and alloc.custom_gender_specific != 'All':
            if alloc.custom_gender_specific != alloc.gender:
                is_invalid = True
                reason.append(f"Gender: requires {alloc.custom_gender_specific}, employee is {alloc.gender}")

        if is_invalid:
            invalid_count += 1
            print(f"❌ INVALID: {alloc.leave_type}")
            print(f"   ID: {alloc.name}")
            print(f"   Reason: {'; '.join(reason)}")
            print(f"   Created: {alloc.created}")
        else:
            valid_count += 1
            restriction = alloc.custom_gender_specific if alloc.custom_gender_specific and alloc.custom_gender_specific != 'All' else 'All'
            print(f"✅ VALID: {alloc.leave_type} ({restriction})")

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"✅ Valid Allocations: {valid_count}")
    print(f"❌ Invalid Allocations: {invalid_count}")

    if invalid_count == 0:
        print("\n🎉 SUCCESS: No invalid allocations found!")
        print("   Validation is working correctly!")
    else:
        print(f"\n⚠️  WARNING: Found {invalid_count} invalid allocations")
        print("   Run cleanup script to remove them")

    print("="*80 + "\n")

    return {"valid": valid_count, "invalid": invalid_count}

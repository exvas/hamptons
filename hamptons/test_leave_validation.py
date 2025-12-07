import frappe

def test_leave_allocation_validation():
    """Test Leave Allocation validation with different scenarios"""

    print("\n" + "="*80)
    print("TESTING LEAVE ALLOCATION VALIDATION")
    print("="*80 + "\n")

    # Test 1: Try to create invalid allocation directly
    print("Test 1: Direct allocation (Male employee with Maternity Leave)")
    print("-" * 80)

    try:
        allocation = frappe.new_doc("Leave Allocation")
        allocation.employee = "1002"
        allocation.leave_type = "Maternity Leave"
        allocation.from_date = "2025-11-22"
        allocation.to_date = "2026-11-22"
        allocation.new_leaves_allocated = 98
        allocation.save()
        print("❌ FAILED: Allocation created without validation!")
    except Exception as e:
        print(f"✅ PASSED: Validation blocked allocation")
        print(f"   Error: {str(e)[:150]}")

    print("\n" + "-" * 80 + "\n")

    # Test 2: With ignore_permissions=True
    print("Test 2: With ignore_permissions=True (like Leave Control Panel)")
    print("-" * 80)

    try:
        allocation = frappe.new_doc("Leave Allocation")
        allocation.employee = "1002"
        allocation.leave_type = "Maternity Leave"
        allocation.from_date = "2025-11-22"
        allocation.to_date = "2026-11-22"
        allocation.new_leaves_allocated = 98
        allocation.save(ignore_permissions=True)
        print("❌ FAILED: Created even with ignore_permissions!")
        allocation.delete()
        frappe.db.commit()
    except Exception as e:
        print(f"✅ PASSED: Blocked even with ignore_permissions=True")
        print(f"   Error: {str(e)[:150]}")

    print("\n" + "-" * 80 + "\n")

    # Test 3: Valid allocation
    print("Test 3: Valid allocation (Male + Paternity Leave)")
    print("-" * 80)

    try:
        allocation = frappe.new_doc("Leave Allocation")
        allocation.employee = "1002"
        allocation.leave_type = "Paternity Leave"
        allocation.from_date = "2025-11-22"
        allocation.to_date = "2026-11-22"
        allocation.new_leaves_allocated = 7
        allocation.save(ignore_permissions=True)
        print(f"✅ PASSED: Valid allocation created: {allocation.name}")
        allocation.delete()
        frappe.db.commit()
    except Exception as e:
        print(f"❌ FAILED: Valid allocation blocked!")
        print(f"   Error: {str(e)[:150]}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")

import frappe
from frappe.utils import today, add_years

def test_exact_leave_policy_assignment_flow():
    """Test EXACTLY how Leave Policy Assignment creates allocations"""

    print("\n" + "="*80)
    print("TESTING EXACT LEAVE POLICY ASSIGNMENT FLOW")
    print("="*80 + "\n")

    employee_id = "1002"
    leave_type = "Maternity Leave"

    print(f"Creating allocation for:")
    print(f"  Employee: {employee_id} (Male)")
    print(f"  Leave Type: {leave_type} (Female only)")
    print(f"  Method: Exactly like Leave Policy Assignment\n")
    print("-" * 80 + "\n")

    try:
        # Create allocation EXACTLY like Leave Policy Assignment does
        allocation = frappe.get_doc(
            dict(
                doctype="Leave Allocation",
                employee=employee_id,
                leave_type=leave_type,
                from_date=today(),
                to_date=add_years(today(), 1),
                new_leaves_allocated=98,
                carry_forward=0,
            )
        )

        print("Step 1: Created doc object")

        # Save with ignore_permissions=True (line 135 in leave_policy_assignment.py)
        allocation.save(ignore_permissions=True)

        print(f"Step 2: Saved - Allocation ID: {allocation.name}")

        # Submit (line 136 in leave_policy_assignment.py)
        allocation.submit()

        print(f"Step 3: Submitted")

        print("\n❌ VALIDATION FAILED - Allocation was created and submitted!")
        print(f"   Allocation: {allocation.name}")

        # Clean up
        allocation.cancel()
        frappe.db.commit()

    except Exception as e:
        error_msg = str(e)
        if "restricted to Female" in error_msg:
            print("✅ VALIDATION WORKING - Blocked correctly")
            print(f"   Error: {error_msg[:200]}")
            frappe.db.rollback()
        else:
            print(f"❌ UNEXPECTED ERROR: {error_msg[:200]}")
            frappe.db.rollback()

    print("\n" + "="*80 + "\n")

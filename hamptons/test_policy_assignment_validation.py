import frappe
from frappe.utils import today, add_years

def test_leave_policy_assignment_validation():
    """Test validation when using Leave Policy Assignment (simulates Leave Control Panel)"""

    print("\n" + "="*80)
    print("TESTING LEAVE POLICY ASSIGNMENT VALIDATION")
    print("(Simulating how Leave Control Panel creates allocations)")
    print("="*80 + "\n")

    employee_id = "1002"  # Male employee
    policy_name = "HR-LPOL-2025-00002"

    print(f"Testing with Employee: {employee_id}")
    print(f"Leave Policy: {policy_name}\n")
    print("-" * 80 + "\n")

    # Get employee details
    emp = frappe.get_doc("Employee", employee_id)
    print(f"Employee Name: {emp.employee_name}")
    print(f"Gender: {emp.gender}")
    print(f"Nationality: {emp.get('custom_nationality')}")
    print(f"Religion: {emp.get('custom_religion')}\n")

    # Get leave policy
    policy = frappe.get_doc("Leave Policy", policy_name)
    print(f"Leave types in policy: {len(policy.leave_policy_details)}\n")

    # Try to create allocations like Leave Policy Assignment does
    success_count = 0
    failed_count = 0
    skipped_leaves = []

    for detail in policy.leave_policy_details:
        leave_type = detail.leave_type
        annual_allocation = detail.annual_allocation

        # Get leave type details
        lt = frappe.get_doc("Leave Type", leave_type)

        # Check if it's a restricted leave type
        is_restricted = False
        restriction_reason = ""

        if hasattr(lt, "custom_gender_specific") and lt.custom_gender_specific:
            if lt.custom_gender_specific not in [None, '', 'All']:
                if lt.custom_gender_specific != emp.gender:
                    is_restricted = True
                    restriction_reason = f"Gender restriction ({lt.custom_gender_specific} only)"

        if hasattr(lt, "custom_religion_specific") and lt.custom_religion_specific:
            if lt.custom_religion_specific not in [None, '', 'All']:
                emp_religion = emp.get("custom_religion")
                if lt.custom_religion_specific == "All (Muslim)" and emp_religion != "Muslim":
                    is_restricted = True
                    restriction_reason = "Religion restriction (Muslim only)"
                elif lt.custom_religion_specific == "Non-Muslim" and emp_religion == "Muslim":
                    is_restricted = True
                    restriction_reason = "Religion restriction (Non-Muslim only)"

        print(f"Testing: {leave_type} ({annual_allocation} days)")

        try:
            # Create allocation exactly like Leave Policy Assignment does
            allocation = frappe.get_doc(dict(
                doctype="Leave Allocation",
                employee=employee_id,
                leave_type=leave_type,
                from_date=today(),
                to_date=add_years(today(), 1),
                new_leaves_allocated=annual_allocation,
                leave_policy=policy_name,
                carry_forward=0,
            ))

            # Save with ignore_permissions=True (like Leave Policy Assignment)
            allocation.save(ignore_permissions=True)

            if is_restricted:
                print(f"  ❌ ERROR: Created despite {restriction_reason}!")
                failed_count += 1
                # Clean up
                allocation.delete()
                frappe.db.commit()
            else:
                print(f"  ✅ Created successfully")
                success_count += 1
                # Clean up test allocation
                allocation.delete()
                frappe.db.commit()

        except Exception as e:
            if is_restricted:
                print(f"  ✅ CORRECTLY BLOCKED: {restriction_reason}")
                skipped_leaves.append({"leave_type": leave_type, "reason": restriction_reason})
            else:
                print(f"  ❌ ERROR: Valid allocation blocked!")
                print(f"     Error: {str(e)[:100]}")
                failed_count += 1

    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"✅ Valid allocations created: {success_count}")
    print(f"✅ Invalid allocations blocked: {len(skipped_leaves)}")
    print(f"❌ Errors: {failed_count}")

    if skipped_leaves:
        print(f"\nCorrectly skipped {len(skipped_leaves)} leaves due to restrictions:")
        for skip in skipped_leaves:
            print(f"  - {skip['leave_type']}: {skip['reason']}")

    print("\n" + "="*80)
    if failed_count == 0:
        print("✅ ALL TESTS PASSED - Validation working correctly!")
    else:
        print("❌ SOME TESTS FAILED - Review errors above")
    print("="*80 + "\n")

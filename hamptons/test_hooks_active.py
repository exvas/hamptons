import frappe

def test_hooks_active():
    """Test if validation hooks are actually registered and working"""

    print("\n" + "="*80)
    print("TESTING IF VALIDATION HOOKS ARE ACTIVE")
    print("="*80 + "\n")

    # Test 1: Check hooks registration
    print("1. Checking hooks registration...")
    print("-" * 80)

    try:
        # Get all doc_events
        all_hooks = frappe.get_hooks()
        doc_events = all_hooks.get("doc_events", {})

        if "Leave Allocation" in doc_events:
            print("✅ Leave Allocation hooks found in registry")
            la_hooks = doc_events["Leave Allocation"]
            for event_type, handler in la_hooks.items():
                if isinstance(handler, list):
                    for h in handler:
                        print(f"   {event_type}: {h}")
                else:
                    print(f"   {event_type}: {handler}")
        else:
            print("❌ Leave Allocation hooks NOT found in registry!")

    except Exception as e:
        print(f"❌ Error checking hooks: {e}")

    print("\n" + "-" * 80 + "\n")

    # Test 2: Try to import validation function
    print("2. Testing validation function import...")
    print("-" * 80)

    try:
        from hamptons.overrides.leave_allocation import validate_leave_allocation
        print("✅ Validation function imported successfully")
    except Exception as e:
        print(f"❌ Failed to import: {e}")

    print("\n" + "-" * 80 + "\n")

    # Test 3: Try to create invalid allocation
    print("3. Testing actual validation (Male + Maternity Leave)...")
    print("-" * 80)

    try:
        alloc = frappe.new_doc("Leave Allocation")
        alloc.employee = "1002"
        alloc.leave_type = "Maternity Leave"
        alloc.from_date = "2025-11-22"
        alloc.to_date = "2026-11-22"
        alloc.new_leaves_allocated = 98

        # Try to save
        alloc.save(ignore_permissions=True)

        print("❌ VALIDATION FAILED - Allocation was created!")
        print(f"   Allocation ID: {alloc.name}")

        # Clean up
        alloc.delete()
        frappe.db.commit()

    except Exception as e:
        error_msg = str(e)
        if "restricted to Female" in error_msg:
            print("✅ VALIDATION WORKING - Allocation blocked correctly")
            print(f"   Error: {error_msg[:150]}")
        else:
            print(f"❌ UNEXPECTED ERROR: {error_msg[:150]}")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")

# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Cleanup Invalid Leave Allocations
Cancels leave allocations that violate gender/nationality/religion restrictions

Run using: bench --site [site] execute hamptons.cleanup_invalid_leave_allocations.cleanup_invalid_allocations
"""

import frappe
from frappe import _


def cleanup_invalid_allocations(dry_run=False):
	"""
	Find and cancel leave allocations that violate gender/nationality/religion restrictions

	Args:
		dry_run: If True, only report issues without cancelling (default: False)

	Returns:
		Dictionary with results
	"""
	print("\n" + "="*80)
	if dry_run:
		print("DRY RUN - FINDING INVALID LEAVE ALLOCATIONS")
	else:
		print("CLEANING UP INVALID LEAVE ALLOCATIONS")
	print("="*80 + "\n")

	# Check if custom fields exist
	has_emp_custom_fields = frappe.db.has_column("Employee", "custom_nationality")

	# Find all submitted leave allocations
	if has_emp_custom_fields:
		allocations = frappe.db.sql("""
			SELECT
				la.name,
				la.employee,
				e.employee_name,
				e.gender,
				e.custom_nationality,
				e.custom_religion,
				la.leave_type,
				lt.custom_gender_specific,
				lt.custom_nationality_specific,
				lt.custom_religion_specific,
				la.new_leaves_allocated,
				la.from_date,
				la.to_date
			FROM `tabLeave Allocation` la
			INNER JOIN `tabEmployee` e ON e.name = la.employee
			INNER JOIN `tabLeave Type` lt ON lt.name = la.leave_type
			WHERE la.docstatus = 1
			ORDER BY la.employee, la.leave_type
		""", as_dict=1)
	else:
		print("⚠ Custom Employee fields not found, using basic validation\n")
		allocations = frappe.db.sql("""
			SELECT
				la.name,
				la.employee,
				e.employee_name,
				e.gender,
				NULL as custom_nationality,
				NULL as custom_religion,
				la.leave_type,
				lt.custom_gender_specific,
				lt.custom_nationality_specific,
				lt.custom_religion_specific,
				la.new_leaves_allocated,
				la.from_date,
				la.to_date
			FROM `tabLeave Allocation` la
			INNER JOIN `tabEmployee` e ON e.name = la.employee
			INNER JOIN `tabLeave Type` lt ON lt.name = la.leave_type
			WHERE la.docstatus = 1
			ORDER BY la.employee, la.leave_type
		""", as_dict=1)

	print(f"Found {len(allocations)} submitted leave allocations to check\n")
	print("-" * 80 + "\n")

	invalid_allocations = []

	for alloc in allocations:
		is_invalid = False
		reason = []

		# Check gender restriction
		if alloc.custom_gender_specific and alloc.custom_gender_specific not in [None, '', 'All']:
			if alloc.custom_gender_specific != alloc.gender:
				is_invalid = True
				reason.append(f"Gender mismatch: Employee is {alloc.gender}, Leave requires {alloc.custom_gender_specific}")

		# Check nationality restriction
		if alloc.custom_nationality_specific and alloc.custom_nationality_specific not in [None, '', 'All']:
			if alloc.custom_nationality_specific != alloc.custom_nationality:
				is_invalid = True
				reason.append(f"Nationality mismatch: Employee is {alloc.custom_nationality or 'Not set'}, Leave requires {alloc.custom_nationality_specific}")

		# Check religion restriction
		if alloc.custom_religion_specific and alloc.custom_religion_specific not in [None, '', 'All']:
			if alloc.custom_religion_specific == "All (Muslim)" and alloc.custom_religion != "Muslim":
				is_invalid = True
				reason.append(f"Religion mismatch: Employee is {alloc.custom_religion or 'Not set'}, Leave requires Muslim")
			elif alloc.custom_religion_specific == "Non-Muslim" and alloc.custom_religion == "Muslim":
				is_invalid = True
				reason.append(f"Religion mismatch: Employee is Muslim, Leave requires Non-Muslim")

		if is_invalid:
			invalid_allocations.append({
				"allocation_id": alloc.name,
				"employee": alloc.employee,
				"employee_name": alloc.employee_name,
				"leave_type": alloc.leave_type,
				"allocated_days": alloc.new_leaves_allocated,
				"reason": "; ".join(reason)
			})

	print(f"Found {len(invalid_allocations)} INVALID allocations\n")

	if not invalid_allocations:
		print("✅ No invalid allocations found!")
		print("="*80 + "\n")
		return {
			"status": "success",
			"invalid_count": 0,
			"cancelled_count": 0
		}

	# Group by employee for reporting
	by_employee = {}
	for inv in invalid_allocations:
		emp = inv["employee"]
		if emp not in by_employee:
			by_employee[emp] = {
				"employee_name": inv["employee_name"],
				"allocations": []
			}
		by_employee[emp]["allocations"].append(inv)

	# Print report
	for emp_id, data in by_employee.items():
		print(f"Employee: {emp_id} - {data['employee_name']}")
		for inv in data["allocations"]:
			print(f"  ✗ {inv['leave_type']}: {inv['allocated_days']} days")
			print(f"    Reason: {inv['reason']}")
			print(f"    Allocation ID: {inv['allocation_id']}")
		print("-" * 80)

	if dry_run:
		print("\n" + "="*80)
		print("DRY RUN COMPLETE - No changes made")
		print(f"Found {len(invalid_allocations)} allocations that should be cancelled")
		print("\nTo actually cancel these allocations, run:")
		print("bench --site [site] execute hamptons.cleanup_invalid_leave_allocations.cleanup_invalid_allocations")
		print("="*80 + "\n")
		return {
			"status": "dry_run",
			"invalid_count": len(invalid_allocations),
			"cancelled_count": 0
		}

	# Actually cancel the invalid allocations
	print("\n" + "="*80)
	print("CANCELLING INVALID ALLOCATIONS...")
	print("="*80 + "\n")

	cancelled_count = 0
	failed_count = 0

	for inv in invalid_allocations:
		try:
			doc = frappe.get_doc("Leave Allocation", inv["allocation_id"])
			doc.cancel()
			frappe.db.commit()
			print(f"✓ Cancelled: {inv['employee']} - {inv['leave_type']}")
			cancelled_count += 1
		except Exception as e:
			print(f"✗ Failed to cancel {inv['allocation_id']}: {str(e)}")
			failed_count += 1
			frappe.db.rollback()

	print("\n" + "="*80)
	print("✅ CLEANUP COMPLETE!")
	print(f"\nCancelled: {cancelled_count}")
	print(f"Failed: {failed_count}")
	print("="*80 + "\n")

	return {
		"status": "success",
		"invalid_count": len(invalid_allocations),
		"cancelled_count": cancelled_count,
		"failed_count": failed_count
	}


def reallocate_leaves_correctly(employee_id=None, policy_name="HR-LPOL-2025-00002"):
	"""
	Re-allocate leaves correctly for one or all employees

	Args:
		employee_id: Specific employee ID (None = all employees)
		policy_name: Leave policy name

	Returns:
		Dictionary with results
	"""
	from hamptons.import_opening_leave_balances import allocate_leaves_with_opening_balance, allocate_single_employee

	print("\n" + "="*80)
	print("RE-ALLOCATING LEAVES WITH PROPER VALIDATION")
	print("="*80 + "\n")

	if employee_id:
		print(f"Re-allocating for employee: {employee_id}\n")
		result = allocate_single_employee(employee_id, policy_name=policy_name)
	else:
		print("Re-allocating for ALL active employees\n")
		result = allocate_leaves_with_opening_balance(policy_name=policy_name)

	return result


def full_cleanup_and_reallocate(employee_id=None):
	"""
	Complete workflow: Clean up invalid allocations and re-allocate correctly

	Args:
		employee_id: Specific employee ID (None = all employees)

	Returns:
		Dictionary with results
	"""
	print("\n" + "="*90)
	print("FULL CLEANUP AND RE-ALLOCATION WORKFLOW")
	print("="*90 + "\n")

	# Step 1: Find and cancel invalid allocations
	print("STEP 1: Cleaning up invalid allocations...")
	cleanup_result = cleanup_invalid_allocations(dry_run=False)

	print("\n" + "="*90)
	print(f"Cleanup complete: {cleanup_result['cancelled_count']} allocations cancelled\n")

	# Step 2: Re-allocate correctly
	print("STEP 2: Re-allocating leaves with proper validation...")
	reallocate_result = reallocate_leaves_correctly(employee_id=employee_id)

	print("\n" + "="*90)
	print("✅ FULL WORKFLOW COMPLETE!")
	print("\nSummary:")
	print(f"  - Invalid allocations cancelled: {cleanup_result['cancelled_count']}")
	print(f"  - New allocations created: {reallocate_result.get('allocations_created', 0)}")
	print(f"  - Allocations skipped (eligibility): {reallocate_result.get('allocations_skipped', 0)}")
	print("="*90 + "\n")

	return {
		"cleanup": cleanup_result,
		"reallocate": reallocate_result
	}

# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Import Opening Leave Balances and Allocate Leaves
Run using: bench --site [site] execute hamptons.import_opening_leave_balances.allocate_leaves_with_opening_balance
"""

import frappe
from frappe import _
from frappe.utils import today, getdate, add_days, add_years
from datetime import datetime


# Annual Leave opening balances as of November 2025
OPENING_BALANCES = {
	"1016": 6,
	"1002": 24,
	"1037": 16,
	"1017": 11.5,
	"1056": 6,
	"1004": 0,
	"1011": 8,
	"1026": -1,
	"1034": 1.5,
	"1048": 3.5,
	"1007": 13,
	"1050": 21,
	"1013": 5,
	"1012": 2,
	"1016": 17,
	"1017": 0,
	"1019": 0,
	"1020": 30,
	"1021": 3,
	"1028": 7,
	"1029": 6,
	"1030": 1,
	"1031": 30,
	"1033": 1.5,
	"1036": 8,
	"1032": 30,
	"1040": 24,
	"1023": 0,
	"1024": 0,
	"1025": 0,
	"1026": 0,
	"1027": 18,
	"1041": 16,
	"1035": 8,
	"1049": 4,
	"1014": 13,
	"1038": 0,
	"1039": 28,
	"1001": 30,
	"1005": 8,
	"1009": 9,
	"1010": 8,
	"1042": 12,
	"1043": 22,
	"1045": 5,
	"1044": -1,
	"1046": 10,
	"1046": 8,
	"1047": 30,
	"1051": 13,
	"1053": 12.5,
	"1052": 12.5,
	"1054": 10,
	"1055": 10,
	"1057": 7.5
}


def get_leave_policy_details(policy_name="HR-LPOL-2025-00002"):
	"""
	Get all leave types and allocations from the leave policy

	Args:
		policy_name: Name of the leave policy

	Returns:
		List of leave type allocations
	"""
	if not frappe.db.exists("Leave Policy", policy_name):
		print(f"✗ Leave Policy '{policy_name}' not found")
		return []

	policy = frappe.get_doc("Leave Policy", policy_name)
	leave_allocations = []

	for detail in policy.leave_policy_details:
		leave_allocations.append({
			"leave_type": detail.leave_type,
			"annual_allocation": detail.annual_allocation
		})

	return leave_allocations


def create_leave_allocation(employee_id, leave_type, leaves_allocated, from_date, to_date,
							description="", carry_forward=False):
	"""
	Create or update leave allocation for an employee

	Args:
		employee_id: Employee ID
		leave_type: Leave Type name
		leaves_allocated: Number of leaves to allocate
		from_date: Allocation from date
		to_date: Allocation to date
		description: Description/note
		carry_forward: Whether to carry forward leaves

	Returns:
		Leave Allocation document or None
	"""
	try:
		# Check if allocation already exists
		existing = frappe.db.exists("Leave Allocation", {
			"employee": employee_id,
			"leave_type": leave_type,
			"from_date": from_date,
			"to_date": to_date,
			"docstatus": ["<", 2]  # Not cancelled
		})

		if existing:
			doc = frappe.get_doc("Leave Allocation", existing)

			# If already submitted, cancel it first
			if doc.docstatus == 1:
				doc.cancel()
				frappe.db.commit()

			# Update and resubmit
			doc.new_leaves_allocated = leaves_allocated
			doc.description = description
			doc.carry_forward = carry_forward
			doc.docstatus = 0  # Reset to draft
		else:
			# Create new allocation
			doc = frappe.new_doc("Leave Allocation")
			doc.employee = employee_id
			doc.leave_type = leave_type
			doc.from_date = from_date
			doc.to_date = to_date
			doc.new_leaves_allocated = leaves_allocated
			doc.description = description
			doc.carry_forward = carry_forward

		# Save and submit
		doc.save(ignore_permissions=True)
		doc.submit()
		frappe.db.commit()

		return doc

	except Exception as e:
		frappe.log_error(
			message=f"Error creating leave allocation for {employee_id} - {leave_type}: {str(e)}",
			title="Leave Allocation Error"
		)
		print(f"  ✗ Error: {str(e)}")
		frappe.db.rollback()
		return None


def allocate_leaves_with_opening_balance(from_date=None, to_date=None,
										policy_name="HR-LPOL-2025-00002"):
	"""
	Allocate all leave types from policy with Annual Leave opening balances

	Args:
		from_date: Allocation from date (default: today)
		to_date: Allocation to date (default: 1 year from today)
		policy_name: Leave Policy name

	Returns:
		Dictionary with results
	"""
	print("\n" + "="*80)
	print("ALLOCATING LEAVES WITH OPENING BALANCES")
	print("="*80 + "\n")

	# Set dates if not provided
	if not from_date:
		from_date = today()
	if not to_date:
		to_date = add_years(getdate(from_date), 1)

	print(f"Allocation Period: {from_date} to {to_date}")
	print(f"Leave Policy: {policy_name}")
	print("-" * 80 + "\n")

	# Get leave policy details
	leave_allocations = get_leave_policy_details(policy_name)

	if not leave_allocations:
		print("✗ No leave types found in policy")
		return {"status": "failed", "message": "No leave types in policy"}

	print(f"Found {len(leave_allocations)} leave types in policy:")
	for la in leave_allocations:
		print(f"  - {la['leave_type']}: {la['annual_allocation']} days")
	print("\n" + "-" * 80 + "\n")

	# Get all active employees
	# Check if custom fields exist
	has_custom_fields = frappe.db.has_column("Employee", "custom_nationality")

	if has_custom_fields:
		employees = frappe.get_all("Employee",
			filters={"status": "Active"},
			fields=["name", "employee_name", "gender", "custom_nationality", "custom_religion"]
		)
	else:
		print("⚠ Custom fields not found, using basic employee data")
		employees = frappe.get_all("Employee",
			filters={"status": "Active"},
			fields=["name", "employee_name", "gender"]
		)
		# Add empty custom fields
		for emp in employees:
			emp["custom_nationality"] = None
			emp["custom_religion"] = None

	if not employees:
		print("✗ No active employees found")
		return {"status": "failed", "message": "No active employees"}

	print(f"Processing {len(employees)} active employees...\n")
	print("=" * 80 + "\n")

	success_count = 0
	failed_count = 0
	skipped_count = 0

	for emp in employees:
		emp_id = emp.name
		emp_name = emp.employee_name
		gender = emp.gender
		nationality = emp.get("custom_nationality")
		religion = emp.get("custom_religion")

		print(f"Employee: {emp_id} - {emp_name}")
		print(f"  Gender: {gender}, Nationality: {nationality}, Religion: {religion}")

		emp_success = 0
		emp_failed = 0

		# Process each leave type
		for leave_data in leave_allocations:
			leave_type = leave_data["leave_type"]
			standard_allocation = leave_data["annual_allocation"]

			# Check if employee is eligible for this leave type
			leave_type_doc = frappe.get_doc("Leave Type", leave_type)

			# Gender restriction check
			if hasattr(leave_type_doc, "custom_gender_specific") and leave_type_doc.custom_gender_specific:
				if leave_type_doc.custom_gender_specific != "All" and leave_type_doc.custom_gender_specific != gender:
					print(f"  ⊘ Skipped {leave_type} - Gender restriction")
					skipped_count += 1
					continue

			# Religion restriction check
			if hasattr(leave_type_doc, "custom_religion_specific") and leave_type_doc.custom_religion_specific:
				if leave_type_doc.custom_religion_specific == "All (Muslim)" and religion != "Muslim":
					print(f"  ⊘ Skipped {leave_type} - Religion restriction")
					skipped_count += 1
					continue
				elif leave_type_doc.custom_religion_specific == "Non-Muslim" and religion == "Muslim":
					print(f"  ⊘ Skipped {leave_type} - Religion restriction")
					skipped_count += 1
					continue

			# Determine allocation amount
			if leave_type == "Annual Leave" and emp_id in OPENING_BALANCES:
				# Use opening balance for Annual Leave
				allocation = OPENING_BALANCES[emp_id]
				description = f"Opening balance as of November 2025: {allocation} days"
			else:
				# Use standard allocation from policy
				allocation = standard_allocation
				description = f"Annual allocation from {policy_name}"

			# Skip if allocation is 0 or negative
			if allocation <= 0:
				print(f"  ⊘ Skipped {leave_type} - Zero/Negative balance ({allocation})")
				skipped_count += 1
				continue

			# Create allocation
			result = create_leave_allocation(
				employee_id=emp_id,
				leave_type=leave_type,
				leaves_allocated=allocation,
				from_date=from_date,
				to_date=to_date,
				description=description,
				carry_forward=(leave_type == "Annual Leave")  # Only Annual Leave can be carried forward
			)

			if result:
				print(f"  ✓ Allocated {leave_type}: {allocation} days")
				emp_success += 1
			else:
				print(f"  ✗ Failed to allocate {leave_type}")
				emp_failed += 1

		print(f"  Summary: {emp_success} allocated, {emp_failed} failed")
		print("-" * 80)

		success_count += emp_success
		failed_count += emp_failed

	print("\n" + "="*80)
	print("✅ LEAVE ALLOCATION COMPLETE!")
	print(f"\nTotal Allocations: {success_count}")
	print(f"Failed: {failed_count}")
	print(f"Skipped (eligibility): {skipped_count}")
	print("="*80 + "\n")

	return {
		"status": "success",
		"total_employees": len(employees),
		"allocations_created": success_count,
		"allocations_failed": failed_count,
		"allocations_skipped": skipped_count
	}


def allocate_single_employee(employee_id, from_date=None, to_date=None,
							policy_name="HR-LPOL-2025-00002"):
	"""
	Allocate leaves for a single employee with opening balance

	Args:
		employee_id: Employee ID
		from_date: Allocation from date
		to_date: Allocation to date
		policy_name: Leave Policy name

	Returns:
		Dictionary with results
	"""
	print("\n" + "="*80)
	print(f"ALLOCATING LEAVES FOR EMPLOYEE: {employee_id}")
	print("="*80 + "\n")

	# Set dates if not provided
	if not from_date:
		from_date = today()
	if not to_date:
		to_date = add_years(getdate(from_date), 1)

	# Check if employee exists
	if not frappe.db.exists("Employee", employee_id):
		print(f"✗ Employee {employee_id} not found")
		return {"status": "failed", "message": "Employee not found"}

	# Get employee details
	emp = frappe.get_doc("Employee", employee_id)

	print(f"Employee: {emp.name} - {emp.employee_name}")
	print(f"Gender: {emp.gender}")
	print(f"Nationality: {emp.get('custom_nationality')}")
	print(f"Religion: {emp.get('custom_religion')}")
	print(f"Period: {from_date} to {to_date}\n")
	print("-" * 80 + "\n")

	# Get leave policy details
	leave_allocations = get_leave_policy_details(policy_name)

	if not leave_allocations:
		print("✗ No leave types found in policy")
		return {"status": "failed", "message": "No leave types in policy"}

	success_count = 0
	failed_count = 0
	skipped_count = 0

	for leave_data in leave_allocations:
		leave_type = leave_data["leave_type"]
		standard_allocation = leave_data["annual_allocation"]

		# Check eligibility
		leave_type_doc = frappe.get_doc("Leave Type", leave_type)

		# Gender restriction
		if hasattr(leave_type_doc, "custom_gender_specific") and leave_type_doc.custom_gender_specific:
			if leave_type_doc.custom_gender_specific != "All" and leave_type_doc.custom_gender_specific != emp.gender:
				print(f"⊘ Skipped {leave_type} - Gender restriction")
				skipped_count += 1
				continue

		# Religion restriction
		if hasattr(leave_type_doc, "custom_religion_specific") and leave_type_doc.custom_religion_specific:
			emp_religion = emp.get("custom_religion")
			if leave_type_doc.custom_religion_specific == "All (Muslim)" and emp_religion != "Muslim":
				print(f"⊘ Skipped {leave_type} - Religion restriction")
				skipped_count += 1
				continue
			elif leave_type_doc.custom_religion_specific == "Non-Muslim" and emp_religion == "Muslim":
				print(f"⊘ Skipped {leave_type} - Religion restriction")
				skipped_count += 1
				continue

		# Determine allocation
		if leave_type == "Annual Leave" and employee_id in OPENING_BALANCES:
			allocation = OPENING_BALANCES[employee_id]
			description = f"Opening balance as of November 2025: {allocation} days"
		else:
			allocation = standard_allocation
			description = f"Annual allocation from {policy_name}"

		# Skip zero/negative
		if allocation <= 0:
			print(f"⊘ Skipped {leave_type} - Zero/Negative balance ({allocation})")
			skipped_count += 1
			continue

		# Create allocation
		result = create_leave_allocation(
			employee_id=employee_id,
			leave_type=leave_type,
			leaves_allocated=allocation,
			from_date=from_date,
			to_date=to_date,
			description=description,
			carry_forward=(leave_type == "Annual Leave")
		)

		if result:
			print(f"✓ Allocated {leave_type}: {allocation} days")
			success_count += 1
		else:
			print(f"✗ Failed to allocate {leave_type}")
			failed_count += 1

	print("\n" + "-" * 80)
	print(f"✅ COMPLETE")
	print(f"Allocated: {success_count}")
	print(f"Failed: {failed_count}")
	print(f"Skipped: {skipped_count}")
	print("="*80 + "\n")

	return {
		"status": "success",
		"allocations_created": success_count,
		"allocations_failed": failed_count,
		"allocations_skipped": skipped_count
	}

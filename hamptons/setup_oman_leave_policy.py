# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Setup Oman Labor Law Compliant Leave Policy
Run using: bench --site [site] execute hamptons.setup_oman_leave_policy.setup_leave_types_and_policy
"""

import frappe
from frappe import _

# Leave Types Master Data based on Oman Labor Law
LEAVE_TYPES_MASTER = [
	{
		"leave_type_name": "Annual Leave",
		"max_leaves_allowed": 30,
		"is_carry_forward": 1,
		"max_continuous_days_allowed": 30,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_earned_leave": 1,
		"earned_leave_frequency": "Monthly",
		"rounding": 0.5,
		"allow_encashment": 1,
		"encashment_threshold_days": 0,
		"earning_component": "Leave Encashment",
		"description": "Annual leave as per Oman Labor Law - 30 days per year",
		"applicable_after": 365  # After 1 year of service
	},
	{
		"leave_type_name": "Sick Leave",
		"max_leaves_allowed": 21,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 21,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Sick leave with medical certificate - 21 days per year (15 days full pay, 6 days half pay)",
		"applicable_after": 90  # After probation
	},
	{
		"leave_type_name": "Paternity Leave",
		"max_leaves_allowed": 7,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 7,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Paternity leave for male employees - 7 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Marriage Leave",
		"max_leaves_allowed": 3,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 3,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Marriage leave - 3 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Bereavement Leave",
		"max_leaves_allowed": 3,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 3,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Bereavement leave for immediate family - 3 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Bereavement Leave - Extended Family",
		"max_leaves_allowed": 2,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 2,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Bereavement leave for extended family - 2 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Bereavement Leave - Child/Wife",
		"max_leaves_allowed": 10,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 10,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Bereavement leave for child or wife - 10 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Hajj Leave",
		"max_leaves_allowed": 15,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 15,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Hajj leave for Muslim employees - 15 days (once in service)",
		"applicable_after": 365
	},
	{
		"leave_type_name": "Exam Leave",
		"max_leaves_allowed": 15,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 15,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Exam leave for students - 15 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Bereavement Leave - Wife (Muslim Female)",
		"max_leaves_allowed": 130,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 130,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Bereavement leave for Muslim female employees (Iddah period) - 130 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Bereavement Leave - Wife (Non-Muslim Female)",
		"max_leaves_allowed": 14,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 14,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Bereavement leave for non-Muslim female employees - 14 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Compassionate Leave - Family Member",
		"max_leaves_allowed": 15,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 15,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Compassionate leave for critical illness of family member - 15 days",
		"applicable_after": 0
	},
	{
		"leave_type_name": "Maternity Leave",
		"max_leaves_allowed": 98,
		"is_carry_forward": 0,
		"max_continuous_days_allowed": 98,
		"is_optional_leave": 0,
		"allow_negative": 0,
		"include_holiday": 0,
		"is_lwp": 0,
		"allow_encashment": 0,
		"description": "Maternity leave for female employees - 98 days (50 days full pay, 48 days unpaid)",
		"applicable_after": 365  # After 1 year of service for full benefits
	}
]


def create_leave_type(leave_data):
	"""
	Create or update a Leave Type

	Args:
		leave_data: Dictionary containing leave type configuration

	Returns:
		Leave Type document
	"""
	leave_type_name = leave_data["leave_type_name"]

	try:
		# Check if leave type already exists
		if frappe.db.exists("Leave Type", leave_type_name):
			print(f"  Leave Type '{leave_type_name}' already exists, updating...")
			doc = frappe.get_doc("Leave Type", leave_type_name)
			doc.update(leave_data)
		else:
			print(f"  Creating new Leave Type '{leave_type_name}'...")
			doc = frappe.new_doc("Leave Type")
			doc.update(leave_data)

		doc.save(ignore_permissions=True)
		frappe.db.commit()
		print(f"  ✓ Leave Type '{leave_type_name}' created/updated successfully")
		return doc

	except Exception as e:
		frappe.log_error(
			message=f"Error creating leave type {leave_type_name}: {str(e)}",
			title="Leave Type Creation Error"
		)
		print(f"  ✗ Error creating leave type '{leave_type_name}': {str(e)}")
		frappe.db.rollback()
		return None


def create_leave_policy():
	"""
	Create Oman Labor Law Leave Policy

	Returns:
		Leave Policy document
	"""
	policy_name = "Oman Labor Law Leave Policy"

	try:
		# Check if policy already exists
		if frappe.db.exists("Leave Policy", policy_name):
			print(f"  Leave Policy '{policy_name}' already exists, updating...")
			doc = frappe.get_doc("Leave Policy", policy_name)
		else:
			print(f"  Creating new Leave Policy '{policy_name}'...")
			doc = frappe.new_doc("Leave Policy")
			doc.policy_name = policy_name
			doc.title = policy_name

		# Clear existing leave policy details
		doc.leave_policy_details = []

		# Add all leave types to the policy
		for leave_type_data in LEAVE_TYPES_MASTER:
			leave_type_name = leave_type_data["leave_type_name"]
			max_leaves = leave_type_data["max_leaves_allowed"]

			# Check if leave type exists before adding to policy
			if frappe.db.exists("Leave Type", leave_type_name):
				doc.append("leave_policy_details", {
					"leave_type": leave_type_name,
					"annual_allocation": max_leaves
				})
				print(f"    - Added {leave_type_name}: {max_leaves} days")
			else:
				print(f"    ✗ Warning: Leave Type '{leave_type_name}' not found, skipping...")

		doc.save(ignore_permissions=True)
		frappe.db.commit()
		print(f"  ✓ Leave Policy '{policy_name}' created/updated successfully")
		return doc

	except Exception as e:
		frappe.log_error(
			message=f"Error creating leave policy: {str(e)}",
			title="Leave Policy Creation Error"
		)
		print(f"  ✗ Error creating leave policy: {str(e)}")
		frappe.db.rollback()
		return None


def setup_leave_types_and_policy():
	"""
	Main function to set up all leave types and policy

	Run using:
	bench --site [site] execute hamptons.setup_oman_leave_policy.setup_leave_types_and_policy
	"""
	print("\n" + "="*70)
	print("SETTING UP OMAN LABOR LAW LEAVE TYPES AND POLICY")
	print("="*70 + "\n")

	# Step 1: Create all leave types
	print("Step 1: Creating Leave Types...")
	print("-" * 70)

	created_count = 0
	failed_count = 0

	for leave_data in LEAVE_TYPES_MASTER:
		result = create_leave_type(leave_data)
		if result:
			created_count += 1
		else:
			failed_count += 1

	print(f"\nLeave Types Summary: {created_count} created/updated, {failed_count} failed")
	print("-" * 70 + "\n")

	# Step 2: Create leave policy
	print("Step 2: Creating Leave Policy...")
	print("-" * 70)

	policy = create_leave_policy()

	if policy:
		print("-" * 70 + "\n")
		print("✅ SETUP COMPLETE!")
		print("\nNext Steps:")
		print("1. Go to: HR > Leave Policy Assignment")
		print("2. Create Leave Policy Assignment for employees")
		print("3. Or use Leave Control Panel to bulk assign")
		print("4. System will auto-allocate leaves based on:")
		print("   - Employee nationality (for Hajj Leave)")
		print("   - Employee gender (for Maternity/Paternity)")
		print("   - Employment duration (for Annual Leave)")
		print("\n" + "="*70 + "\n")
		return {
			"status": "success",
			"leave_types_created": created_count,
			"leave_types_failed": failed_count,
			"policy_name": policy.name
		}
	else:
		print("\n✗ SETUP FAILED - Please check error logs")
		print("="*70 + "\n")
		return {
			"status": "failed",
			"leave_types_created": created_count,
			"leave_types_failed": failed_count
		}


def assign_leave_policy_to_employee(employee_id, policy_name="Oman Labor Law Leave Policy",
									effective_from=None, carry_forward=1):
	"""
	Assign leave policy to a specific employee

	Args:
		employee_id: Employee ID
		policy_name: Name of the leave policy (default: Oman Labor Law Leave Policy)
		effective_from: Effective date (default: today)
		carry_forward: Whether to carry forward leaves (default: 1)

	Returns:
		Leave Policy Assignment document
	"""
	from frappe.utils import today, getdate

	if not effective_from:
		effective_from = today()

	try:
		# Check if employee exists
		if not frappe.db.exists("Employee", employee_id):
			print(f"✗ Employee {employee_id} not found")
			return None

		# Check if policy exists
		if not frappe.db.exists("Leave Policy", policy_name):
			print(f"✗ Leave Policy '{policy_name}' not found")
			return None

		# Check if assignment already exists
		existing = frappe.db.exists("Leave Policy Assignment", {
			"employee": employee_id,
			"leave_policy": policy_name,
			"effective_from": effective_from
		})

		if existing:
			print(f"  Leave Policy Assignment already exists for {employee_id}, updating...")
			doc = frappe.get_doc("Leave Policy Assignment", existing)
		else:
			print(f"  Creating Leave Policy Assignment for {employee_id}...")
			doc = frappe.new_doc("Leave Policy Assignment")
			doc.employee = employee_id
			doc.leave_policy = policy_name
			doc.effective_from = effective_from

		doc.carry_forward = carry_forward
		doc.save(ignore_permissions=True)
		doc.submit()
		frappe.db.commit()

		print(f"  ✓ Leave Policy assigned to {employee_id} successfully")
		return doc

	except Exception as e:
		frappe.log_error(
			message=f"Error assigning leave policy to {employee_id}: {str(e)}",
			title="Leave Policy Assignment Error"
		)
		print(f"  ✗ Error: {str(e)}")
		frappe.db.rollback()
		return None


def bulk_assign_leave_policy(filters=None, policy_name="Oman Labor Law Leave Policy"):
	"""
	Bulk assign leave policy to multiple employees

	Args:
		filters: Dictionary of filters (e.g., {"status": "Active", "department": "HR"})
		policy_name: Name of the leave policy

	Returns:
		Dictionary with results
	"""
	from frappe.utils import today

	print("\n" + "="*70)
	print("BULK ASSIGNING LEAVE POLICY TO EMPLOYEES")
	print("="*70 + "\n")

	# Default filter: Active employees only
	if not filters:
		filters = {"status": "Active"}

	# Get employees matching filters
	employees = frappe.get_all("Employee",
		filters=filters,
		fields=["name", "employee_name", "department", "designation"]
	)

	if not employees:
		print("✗ No employees found matching the filters")
		return {"status": "failed", "message": "No employees found"}

	print(f"Found {len(employees)} employees")
	print("-" * 70)

	success_count = 0
	failed_count = 0

	for emp in employees:
		result = assign_leave_policy_to_employee(
			employee_id=emp.name,
			policy_name=policy_name,
			effective_from=today()
		)

		if result:
			success_count += 1
		else:
			failed_count += 1

	print("\n" + "-" * 70)
	print(f"✅ BULK ASSIGNMENT COMPLETE")
	print(f"   Success: {success_count}")
	print(f"   Failed: {failed_count}")
	print("="*70 + "\n")

	return {
		"status": "success",
		"total_employees": len(employees),
		"success_count": success_count,
		"failed_count": failed_count
	}

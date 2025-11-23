# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Leave Control Panel Override
Fixes savepoint error when leave allocation validation fails
"""

import frappe
from frappe import _
from frappe.utils import get_link_to_form


def create_leave_policy_assignments(self, employees: list) -> dict:
	"""
	Override of Leave Control Panel's create_leave_policy_assignments method
	Handles validation errors gracefully without savepoint errors
	"""
	from_date, to_date = self.get_from_to_date()
	assignment_based_on = None if self.dates_based_on == "Custom Range" else self.dates_based_on
	failure = []
	success = []

	for employee in employees:
		# Start a new transaction for each employee
		frappe.db.begin()

		try:
			assignment = frappe.new_doc("Leave Policy Assignment")
			assignment.employee = employee
			assignment.assignment_based_on = assignment_based_on
			assignment.leave_policy = self.leave_policy
			assignment.effective_from = from_date or frappe.db.get_value(
				"Employee", employee, "date_of_joining"
			)
			assignment.effective_to = to_date
			assignment.leave_period = self.get("leave_period")
			assignment.carry_forward = self.carry_forward
			assignment.save()
			assignment.submit()

			# Commit successful assignment
			frappe.db.commit()

			success.append(
				{
					"doc": get_link_to_form("Leave Policy Assignment", assignment.name),
					"employee": employee,
				}
			)

		except frappe.exceptions.ValidationError as e:
			# Handle validation errors (like gender/religion restrictions)
			frappe.db.rollback()
			error_msg = str(e)

			# Log the error
			frappe.log_error(
				message=f"Leave allocation validation failed for employee {employee}: {error_msg}",
				title="Leave Allocation Validation Error"
			)

			# Show user-friendly message
			frappe.msgprint(
				msg=_("Leave allocation skipped for employee {0}: {1}").format(employee, error_msg),
				title=_("Validation Error"),
				indicator="orange"
			)

			failure.append(employee)

		except Exception as e:
			# Handle other errors
			frappe.db.rollback()

			frappe.log_error(
				message=f"Leave Policy Assignment failed for employee {employee}: {str(e)}",
				title="Leave Policy Assignment Error"
			)

			failure.append(employee)

	frappe.clear_messages()
	frappe.publish_realtime(
		"completed_bulk_leave_policy_assignment",
		message={"success": success, "failure": failure},
		doctype="Bulk Salary Structure Assignment",
		after_commit=True,
	)

	return {"success": success, "failure": failure}


def check_leave_eligibility(employee_id, leave_type_name):
	"""
	Check if an employee is eligible for a specific leave type
	Returns: (eligible: bool, reason: str)
	"""
	try:
		employee = frappe.get_doc("Employee", employee_id)
		leave_type = frappe.get_doc("Leave Type", leave_type_name)

		# Check gender restriction
		if hasattr(leave_type, "custom_gender_specific") and leave_type.custom_gender_specific:
			if leave_type.custom_gender_specific not in [None, '', 'All']:
				if leave_type.custom_gender_specific != employee.gender:
					return False, f"Gender restriction: requires {leave_type.custom_gender_specific}, employee is {employee.gender}"

		# Check religion restriction
		if hasattr(leave_type, "custom_religion_specific") and leave_type.custom_religion_specific:
			if leave_type.custom_religion_specific not in [None, '', 'All']:
				emp_religion = employee.get("custom_religion")

				if leave_type.custom_religion_specific == "All (Muslim)":
					if emp_religion != "Muslim":
						return False, f"Religion restriction: requires Muslim, employee is {emp_religion or 'not set'}"
				elif leave_type.custom_religion_specific == "Non-Muslim":
					if emp_religion == "Muslim":
						return False, f"Religion restriction: requires Non-Muslim, employee is Muslim"

		# Check once-in-service (Hajj Leave) - Flexible: Allow re-allocation if not consumed
		if hasattr(leave_type, "custom_once_in_service") and leave_type.custom_once_in_service:
			if leave_type_name == "Hajj Leave":
				# Check if Hajj Leave was actually CONSUMED (Leave Application approved and taken)
				consumed_leave = frappe.db.sql("""
					SELECT la.name, la.from_date, la.to_date
					FROM `tabLeave Application` la
					WHERE la.employee = %s
						AND la.leave_type = 'Hajj Leave'
						AND la.docstatus = 1
						AND la.status IN ('Approved', 'Open')
					LIMIT 1
				""", (employee_id,), as_dict=1)

				if consumed_leave:
					# Hajj Leave was actually consumed - block re-allocation
					return False, f"Hajj Leave already consumed (from {consumed_leave[0].from_date} to {consumed_leave[0].to_date})"

				# Check if there's an ACTIVE allocation (not expired, not cancelled)
				from frappe.utils import today

				active_allocation = frappe.db.sql("""
					SELECT name, from_date, to_date
					FROM `tabLeave Allocation`
					WHERE employee = %s
						AND leave_type = 'Hajj Leave'
						AND docstatus = 1
						AND to_date >= %s
					LIMIT 1
				""", (employee_id, today()), as_dict=1)

				if active_allocation:
					# There's an active allocation - don't create duplicate
					return False, f"Hajj Leave allocation already active (valid until {active_allocation[0].to_date})"

				# No consumed leave and no active allocation - allow (re-)allocation
				return True, None

		return True, None

	except Exception as e:
		frappe.logger().error(f"Error checking leave eligibility: {str(e)}")
		return True, None  # Allow if check fails


def override_leave_control_panel():
	"""
	Monkey patch Leave Control Panel and Leave Policy Assignment to handle validation gracefully
	"""
	try:
		from hrms.hr.doctype.leave_control_panel.leave_control_panel import LeaveControlPanel
		from hrms.hr.doctype.leave_policy_assignment.leave_policy_assignment import LeavePolicyAssignment

		# Replace Leave Control Panel method
		LeaveControlPanel.create_leave_policy_assignments = create_leave_policy_assignments

		# Patch Leave Policy Assignment to check eligibility and handle skipped leaves
		original_create_allocation = LeavePolicyAssignment.create_leave_allocation
		original_grant_leave = LeavePolicyAssignment.grant_leave_alloc_for_employee

		def patched_create_leave_allocation(self, annual_allocation, leave_details, date_of_joining):
			"""Check eligibility before creating allocation"""
			# Check if employee is eligible for this leave type
			eligible, reason = check_leave_eligibility(self.employee, leave_details.name)

			if not eligible:
				# Log that we're skipping this leave
				frappe.logger().info(
					f"Skipping {leave_details.name} for employee {self.employee}: {reason}"
				)
				# Return None to indicate skipped
				return None, 0

			# If eligible, proceed with original method
			return original_create_allocation(self, annual_allocation, leave_details, date_of_joining)

		def patched_grant_leave_alloc(self):
			"""Modified to handle None returns from create_leave_allocation"""
			if self.leaves_allocated:
				frappe.throw(_("Leave already have been assigned for this Leave Policy Assignment"))
			else:
				leave_allocations = {}
				from hrms.hr.doctype.leave_policy_assignment.leave_policy_assignment import get_leave_type_details
				leave_type_details = get_leave_type_details()

				leave_policy = frappe.get_doc("Leave Policy", self.leave_policy)
				date_of_joining = frappe.db.get_value("Employee", self.employee, "date_of_joining")

				skipped_leaves = []

				for leave_policy_detail in leave_policy.leave_policy_details:
					leave_details = leave_type_details.get(leave_policy_detail.leave_type)

					if not leave_details.is_lwp:
						leave_allocation, new_leaves_allocated = self.create_leave_allocation(
							leave_policy_detail.annual_allocation,
							leave_details,
							date_of_joining,
						)

						# Only add to dict if allocation was created (not None)
						if leave_allocation is not None:
							leave_allocations[leave_details.name] = {
								"name": leave_allocation,
								"leaves": new_leaves_allocated,
							}
						else:
							# Track skipped leaves
							skipped_leaves.append(leave_details.name)

				self.db_set("leaves_allocated", 1)

				# Log skipped leaves
				if skipped_leaves:
					frappe.logger().info(
						f"Leave Policy Assignment {self.name}: Skipped {len(skipped_leaves)} leaves for employee {self.employee}: {', '.join(skipped_leaves)}"
					)

				return leave_allocations

		LeavePolicyAssignment.create_leave_allocation = patched_create_leave_allocation
		LeavePolicyAssignment.grant_leave_alloc_for_employee = patched_grant_leave_alloc

		frappe.logger().info("Leave Control Panel and Leave Policy Assignment overrides applied successfully")
	except Exception as e:
		frappe.logger().error(f"Failed to override Leave Control Panel: {str(e)}")

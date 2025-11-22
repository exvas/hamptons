# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Leave Allocation Validation Override
Validates leave allocations based on gender, nationality, and religion restrictions
"""

import frappe
from frappe import _


def validate_leave_allocation(doc, method=None):
	"""
	Validate leave allocation against employee attributes
	Prevents allocation of gender/nationality/religion specific leaves to ineligible employees

	Args:
		doc: Leave Allocation document
		method: Method name (not used)
	"""
	# Skip if not a new allocation or if being cancelled
	if doc.docstatus == 2:  # Cancelled
		return

	# Get employee details
	employee = frappe.get_doc("Employee", doc.employee)

	# Get leave type details
	leave_type = frappe.get_doc("Leave Type", doc.leave_type)

	# Check gender restriction
	if hasattr(leave_type, "custom_gender_specific") and leave_type.custom_gender_specific:
		if leave_type.custom_gender_specific not in [None, '', 'All']:
			if leave_type.custom_gender_specific != employee.gender:
				frappe.throw(_(
					"Leave Type '{0}' is restricted to {1} employees. "
					"Employee {2} is {3}."
				).format(
					leave_type.name,
					leave_type.custom_gender_specific,
					employee.name,
					employee.gender
				))

	# Check nationality restriction
	if hasattr(leave_type, "custom_nationality_specific") and leave_type.custom_nationality_specific:
		if leave_type.custom_nationality_specific not in [None, '', 'All']:
			emp_nationality = employee.get("custom_nationality")
			if leave_type.custom_nationality_specific != emp_nationality:
				frappe.throw(_(
					"Leave Type '{0}' is restricted to {1} employees. "
					"Employee {2} nationality is {3}."
				).format(
					leave_type.name,
					leave_type.custom_nationality_specific,
					employee.name,
					emp_nationality or "not set"
				))

	# Check religion restriction
	if hasattr(leave_type, "custom_religion_specific") and leave_type.custom_religion_specific:
		if leave_type.custom_religion_specific not in [None, '', 'All']:
			emp_religion = employee.get("custom_religion")

			if leave_type.custom_religion_specific == "All (Muslim)":
				if emp_religion != "Muslim":
					frappe.throw(_(
						"Leave Type '{0}' is restricted to Muslim employees. "
						"Employee {1} religion is {2}."
					).format(
						leave_type.name,
						employee.name,
						emp_religion or "not set"
					))

			elif leave_type.custom_religion_specific == "Non-Muslim":
				if emp_religion == "Muslim":
					frappe.throw(_(
						"Leave Type '{0}' is restricted to Non-Muslim employees. "
						"Employee {1} is Muslim."
					).format(
						leave_type.name,
						employee.name
					))

	# Check once-in-service restriction (e.g., Hajj Leave)
	if hasattr(leave_type, "custom_once_in_service") and leave_type.custom_once_in_service:
		if leave_type.name == "Hajj Leave":
			# Check if employee has already taken Hajj leave
			if employee.get("custom_hajj_leave_taken"):
				frappe.throw(_(
					"Hajj Leave can only be availed once during service. "
					"Employee {0} has already taken Hajj Leave on {1}."
				).format(
					employee.name,
					employee.get("custom_hajj_leave_date") or "a previous date"
				))

			# Check if there's already an allocation for Hajj Leave
			existing_allocation = frappe.db.exists("Leave Allocation", {
				"employee": doc.employee,
				"leave_type": "Hajj Leave",
				"docstatus": ["<", 2],  # Not cancelled
				"name": ["!=", doc.name]  # Exclude current document
			})

			if existing_allocation:
				frappe.throw(_(
					"Hajj Leave allocation already exists for employee {0}. "
					"This leave can only be allocated once during service."
				).format(employee.name))


def on_submit_leave_allocation(doc, method=None):
	"""
	Update employee record when Hajj Leave is allocated

	Args:
		doc: Leave Allocation document
		method: Method name (not used)
	"""
	if doc.leave_type == "Hajj Leave":
		# Mark employee as having taken Hajj leave
		employee = frappe.get_doc("Employee", doc.employee)
		employee.custom_hajj_leave_taken = 1
		employee.custom_hajj_leave_date = doc.from_date
		employee.save(ignore_permissions=True)
		frappe.db.commit()

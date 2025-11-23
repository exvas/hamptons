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
	# Log that validation is being called
	frappe.logger().debug(f"Validation called for {doc.employee} - {doc.leave_type} via {method}")

	# Skip if being cancelled
	if doc.docstatus == 2:  # Cancelled
		return

	# Skip if custom fields don't exist (prevents errors on fresh installs)
	if not frappe.db.has_column("Employee", "custom_nationality"):
		frappe.logger().debug("Custom fields don't exist, skipping validation")
		return

	# Get employee details
	employee = frappe.get_doc("Employee", doc.employee)

	# Get leave type details - must use get_doc to ensure custom fields are loaded
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

	# Check once-in-service restriction (Hajj Leave) - Flexible: Allow re-allocation if not consumed
	if hasattr(leave_type, "custom_once_in_service") and leave_type.custom_once_in_service:
		if leave_type.name == "Hajj Leave":
			# Check if Hajj Leave was actually CONSUMED (Leave Application approved)
			consumed_leave = frappe.db.sql("""
				SELECT la.name, la.from_date, la.to_date
				FROM `tabLeave Application` la
				WHERE la.employee = %s
					AND la.leave_type = 'Hajj Leave'
					AND la.docstatus = 1
					AND la.status IN ('Approved', 'Open')
				LIMIT 1
			""", (doc.employee,), as_dict=1)

			if consumed_leave:
				# Hajj Leave was actually consumed - block re-allocation
				frappe.throw(_(
					"Hajj Leave can only be availed once during service. "
					"Employee {0} has already taken Hajj Leave from {1} to {2}."
				).format(
					employee.name,
					consumed_leave[0].from_date,
					consumed_leave[0].to_date
				))

			# Check if there's an ACTIVE allocation (not expired, not cancelled)
			from frappe.utils import today, getdate

			active_allocation = frappe.db.sql("""
				SELECT name, from_date, to_date
				FROM `tabLeave Allocation`
				WHERE employee = %s
					AND leave_type = 'Hajj Leave'
					AND docstatus = 1
					AND to_date >= %s
					AND name != %s
				LIMIT 1
			""", (doc.employee, today(), doc.name or ''), as_dict=1)

			if active_allocation:
				frappe.throw(_(
					"Hajj Leave allocation already exists for employee {0} (valid until {1}). "
					"Cannot create duplicate allocation."
				).format(employee.name, active_allocation[0].to_date))


def on_submit_leave_allocation(doc, method=None):
	"""
	Placeholder for future logic on Leave Allocation submission

	Note: We no longer mark Hajj Leave as taken when allocated.
	Instead, it's marked as taken only when Leave Application is approved.

	Args:
		doc: Leave Allocation document
		method: Method name (not used)
	"""
	# No automatic flag setting - employee can still apply for Hajj Leave
	pass

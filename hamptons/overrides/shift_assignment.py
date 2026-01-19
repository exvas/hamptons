# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Shift Assignment Override
Automatically closes old shift assignments when a new one is created
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days, today


def before_insert_shift_assignment(doc, method=None):
	"""
	Before inserting a new Shift Assignment, close any existing active assignments
	for the same employee by setting their End Date and Status to Inactive.

	Args:
		doc: Shift Assignment document
		method: Method name (not used)
	"""
	if not doc.employee:
		return

	# Find all active shift assignments for this employee
	active_assignments = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": doc.employee,
			"status": "Active",
			"docstatus": ["!=", 2]  # Not cancelled
		},
		fields=["name", "start_date", "end_date"]
	)

	if not active_assignments:
		return

	# Get the new assignment's start date (or today if not set)
	new_start_date = getdate(doc.start_date) if doc.start_date else getdate(today())

	# Close the old assignments
	for assignment in active_assignments:
		# Set end date to one day before the new assignment starts
		end_date = add_days(new_start_date, -1)

		# Update the old assignment
		frappe.db.set_value(
			"Shift Assignment",
			assignment.name,
			{
				"end_date": end_date,
				"status": "Inactive"
			},
			update_modified=True
		)

		frappe.msgprint(
			_("Previous Shift Assignment {0} has been closed with End Date {1} and set to Inactive.").format(
				frappe.bold(assignment.name),
				frappe.format(end_date, {"fieldtype": "Date"})
			),
			title=_("Previous Assignment Closed"),
			indicator="blue"
		)

	# Commit the changes
	frappe.db.commit()

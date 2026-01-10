# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Leave Application Override
Marks Hajj Leave as consumed when Leave Application is approved
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days, today


def validate_leave_application(doc, method=None):
	"""
	Validate Leave Application - enforce 2 weeks advance notice requirement for Annual Leave

	Args:
		doc: Leave Application document
		method: Method name (not used)
	"""
	# Only enforce 2 weeks advance notice for Annual Leave
	if doc.leave_type == "Annual Leave" and doc.from_date:
		minimum_from_date = add_days(today(), 14)
		leave_start_date = getdate(doc.from_date)

		if leave_start_date < getdate(minimum_from_date):
			days_diff = (getdate(minimum_from_date) - leave_start_date).days
			frappe.throw(
				_("Annual Leave must be submitted at least 2 weeks in advance. "
				  "Your selected start date is {0}, which is {1} day(s) before the minimum allowed date of {2}. "
				  "Please select a start date on or after {3}.").format(
					frappe.format(leave_start_date, {"fieldtype": "Date"}),
					days_diff,
					frappe.format(minimum_from_date, {"fieldtype": "Date"}),
					frappe.format(minimum_from_date, {"fieldtype": "Date"})
				),
				title=_("2 Weeks Advance Notice Required for Annual Leave")
			)


def on_submit_leave_application(doc, method=None):
	"""
	Mark Hajj Leave as consumed when Leave Application is submitted

	Args:
		doc: Leave Application document
		method: Method name (not used)
	"""
	if doc.leave_type == "Hajj Leave" and doc.status in ['Approved', 'Open']:
		# Mark employee as having consumed Hajj leave
		employee = frappe.get_doc("Employee", doc.employee)
		employee.custom_hajj_leave_taken = 1
		employee.custom_hajj_leave_date = doc.from_date
		employee.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.logger().info(
			f"Marked Hajj Leave as consumed for employee {doc.employee} "
			f"(Leave Application: {doc.name}, From: {doc.from_date})"
		)


def on_cancel_leave_application(doc, method=None):
	"""
	Unmark Hajj Leave if Leave Application is cancelled (before actual leave date)

	Args:
		doc: Leave Application document
		method: Method name (not used)
	"""
	if doc.leave_type == "Hajj Leave":
		from frappe.utils import today, getdate

		# Only unmark if the leave hasn't started yet
		if getdate(doc.from_date) > getdate(today()):
			employee = frappe.get_doc("Employee", doc.employee)

			# Check if there are any other approved Hajj Leave applications
			other_hajj_leaves = frappe.db.count("Leave Application", {
				"employee": doc.employee,
				"leave_type": "Hajj Leave",
				"docstatus": 1,
				"status": ["in", ["Approved", "Open"]],
				"name": ["!=", doc.name]
			})

			if other_hajj_leaves == 0:
				# No other approved Hajj Leave applications - unmark
				employee.custom_hajj_leave_taken = 0
				employee.custom_hajj_leave_date = None
				employee.save(ignore_permissions=True)
				frappe.db.commit()

				frappe.logger().info(
					f"Unmarked Hajj Leave for employee {doc.employee} "
					f"(Leave Application cancelled before leave date)"
				)

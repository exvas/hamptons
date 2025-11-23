# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Leave Application Override
Marks Hajj Leave as consumed when Leave Application is approved
"""

import frappe
from frappe import _


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

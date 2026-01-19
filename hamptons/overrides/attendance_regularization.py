# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Attendance Regularization Override
- Send notification to employee when Attendance Regularization is created
"""

import frappe
from frappe import _
from frappe.utils import get_url_to_form


def after_insert_attendance_regularization(doc, method=None):
	"""
	Send notification email to employee when Attendance Regularization is created

	Args:
		doc: Attendance Regularization document
		method: Method name (not used)
	"""
	if not doc.employee:
		return

	# Get employee details
	employee = frappe.get_doc("Employee", doc.employee)
	employee_email = employee.prefered_email or employee.company_email or employee.personal_email

	# Also get user email if employee is linked to a user
	user_email = None
	if employee.user_id:
		user_email = frappe.db.get_value("User", employee.user_id, "email")

	# Collect all recipient emails (remove duplicates)
	recipients = list(set(filter(None, [employee_email, user_email])))

	if not recipients:
		frappe.logger().warning(
			f"No email found for employee {doc.employee} - {doc.employee_name}"
		)
		return

	# Get URL to the document
	regularization_url = get_url_to_form("Attendance Regularization", doc.name)

	# Build email content
	subject = _("Attendance Regularization Created - {0}").format(doc.posting_date)

	message = _("""
		<h3>Attendance Regularization Notice</h3>
		<p>Dear {employee_name},</p>
		<p>An Attendance Regularization record has been created for you with the following details:</p>
		<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{posting_date}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Shift:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{shift}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Shift Time:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{start_time} - {end_time}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Late:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{late}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{status}</td></tr>
		</table>
		<p style="margin-top: 15px;">If you need to submit an Attendance Request to regularize your attendance, please click the button below to view the details and take action.</p>
		<p style="margin-top: 20px;">
			<a href="{regularization_url}" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Regularization</a>
		</p>
	""").format(
		employee_name=doc.employee_name,
		posting_date=frappe.format(doc.posting_date, {"fieldtype": "Date"}),
		shift=doc.shift or "Not assigned",
		start_time=doc.start_time or "-",
		end_time=doc.end_time or "-",
		late=doc.late or "No late",
		status=doc.status,
		regularization_url=regularization_url
	)

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype="Attendance Regularization",
			reference_name=doc.name,
			now=True
		)
		frappe.logger().info(
			f"Sent Attendance Regularization notification to {', '.join(recipients)} for {doc.name}"
		)
	except Exception as e:
		frappe.logger().error(
			f"Failed to send Attendance Regularization notification for {doc.name}: {str(e)}"
		)

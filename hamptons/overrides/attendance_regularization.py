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
	Queue email notification after Attendance Regularization is created.
	Uses background job to ensure record is committed before sending email.

	Args:
		doc: Attendance Regularization document
		method: Method name (not used)
	"""
	if not doc.employee:
		return

	# Determine the reason for regularization based on items and late value
	reason = determine_regularization_reason(doc)

	# Format late time properly (remove microseconds if present)
	late_formatted = None
	if doc.late:
		from datetime import timedelta
		if isinstance(doc.late, timedelta):
			total_secs = int(doc.late.total_seconds())
			hours = total_secs // 3600
			minutes = (total_secs % 3600) // 60
			late_formatted = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
		else:
			# It's a time object
			late_formatted = str(doc.late)[:8]  # HH:MM:SS only, no microseconds

	# Queue email notification to be sent AFTER the transaction is committed
	# This prevents sending emails for records that get rolled back
	frappe.enqueue(
		'hamptons.overrides.attendance_regularization.send_ar_notification_email',
		queue='short',
		timeout=300,
		at_front=False,
		ar_name=doc.name,
		employee=doc.employee,
		employee_name=doc.employee_name,
		posting_date=str(doc.posting_date),
		shift=doc.shift,
		start_time=str(doc.start_time) if doc.start_time else None,
		end_time=str(doc.end_time) if doc.end_time else None,
		late=late_formatted,
		status=doc.status,
		reason=reason
	)


def determine_regularization_reason(doc):
	"""
	Determine the reason for regularization based on the document data.

	Returns a human-readable reason string.
	"""
	reasons = []

	# Check for late entry
	if doc.late:
		reasons.append("Late Entry")

	# Check items for missing IN or OUT
	items = doc.attendance_regularization_item or []
	has_in = any(item.log_type == 'IN' for item in items)
	has_out = any(item.log_type == 'OUT' for item in items)

	if not has_in:
		reasons.append("Missing Check-in")
	if not has_out:
		reasons.append("Missing Check-out")

	# If we have both IN and OUT but no late, it might be early exit
	if has_in and has_out and not doc.late:
		reasons.append("Early Exit")

	return ", ".join(reasons) if reasons else "Attendance Review Required"


def send_ar_notification_email(ar_name, employee, employee_name, posting_date, shift, start_time, end_time, late, status, reason=None):
	"""
	Send notification email to employee about Attendance Regularization.
	This is called from a background job AFTER the record is committed.

	Args:
		ar_name: Attendance Regularization name
		employee: Employee ID
		employee_name: Employee name
		posting_date: Date of regularization
		shift: Shift name
		start_time: Shift start time
		end_time: Shift end time
		late: Late entry time (formatted, or None if not late)
		status: AR status
		reason: Human-readable reason for regularization
	"""
	# Email notifications for Attendance Regularization are disabled
	return

	# Verify the AR record actually exists in database
	if not frappe.db.exists("Attendance Regularization", ar_name):
		frappe.logger().warning(
			f"Skipping email for {ar_name}: Record not found in database (likely rolled back)"
		)
		return

	# Get employee details
	employee_doc = frappe.get_doc("Employee", employee)
	employee_email = employee_doc.prefered_email or employee_doc.company_email or employee_doc.personal_email

	# Also get user email if employee is linked to a user
	user_email = None
	if employee_doc.user_id:
		user_email = frappe.db.get_value("User", employee_doc.user_id, "email")

	# Collect all recipient emails (remove duplicates)
	recipients = list(set(filter(None, [employee_email, user_email])))

	if not recipients:
		frappe.logger().warning(
			f"No email found for employee {employee} - {employee_name}"
		)
		return

	# Get URL to the document
	regularization_url = get_url_to_form("Attendance Regularization", ar_name)

	# Build email content - only show Late row if there's an actual late value
	late_row = ""
	if late:
		late_row = f'<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Late By:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{late}</td></tr>'

	subject = _("Attendance Regularization - {0}").format(posting_date)

	message = _("""
		<h3>Attendance Regularization Notice</h3>
		<p>Dear {employee_name},</p>
		<p>An Attendance Regularization record has been created for you with the following details:</p>
		<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{posting_date}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Shift:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{shift}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Shift Time:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{start_time} - {end_time}</td></tr>
			{late_row}
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{status}</td></tr>
		</table>
		<p style="margin-top: 15px;">If you need to submit an Attendance Request to regularize your attendance, please click the button below to view the details and take action.</p>
		<p style="margin-top: 20px;">
			<a href="{regularization_url}" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Regularization</a>
		</p>
	""").format(
		employee_name=employee_name,
		posting_date=frappe.format(posting_date, {"fieldtype": "Date"}),
		reason=reason or "Attendance Review Required",
		shift=shift or "Not assigned",
		start_time=start_time or "-",
		end_time=end_time or "-",
		late_row=late_row,
		status=status,
		regularization_url=regularization_url
	)

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			message=message,
			reference_doctype="Attendance Regularization",
			reference_name=ar_name,
			now=True
		)
		frappe.logger().info(
			f"Sent Attendance Regularization notification to {', '.join(recipients)} for {ar_name}"
		)
	except Exception as e:
		frappe.logger().error(
			f"Failed to send Attendance Regularization notification for {ar_name}: {str(e)}"
		)

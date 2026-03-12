# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Leave Application Override
- Marks Hajj Leave as consumed when Leave Application is approved
- Custom workflow notifications for Leave Application (HOD-only approval)
- Auto-cancels conflicting attendance records when leave is submitted
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days, today, get_url_to_form
from hrms.hr.doctype.leave_application.leave_application import LeaveApplication


class HamptonsLeaveApplication(LeaveApplication):
	def validate_attendance(self):
		"""
		Override to cancel and delete conflicting attendance records instead of blocking.
		Biometric-generated Present attendance should be removed when leave is applied.
		"""
		attendance_records = frappe.get_all(
			"Attendance",
			filters={
				"employee": self.employee,
				"attendance_date": ("between", [self.from_date, self.to_date]),
				"status": ("in", ["Present", "Work From Home"]),
				"docstatus": 1,
				"half_day_status": ("!=", "Absent"),
			},
			fields=["name", "attendance_date"],
		)

		for record in attendance_records:
			attendance_doc = frappe.get_doc("Attendance", record.name)
			attendance_doc.cancel()
			frappe.delete_doc("Attendance", record.name, ignore_permissions=True)
			frappe.msgprint(
				_("Attendance for {0} on {1} has been cancelled to allow this leave application.").format(
					self.employee,
					frappe.format(record.attendance_date, {"fieldtype": "Date"}),
				),
				indicator="orange",
				alert=True,
			)


def validate_leave_application(doc, method=None):
	"""
	Validate Leave Application:
	- Sick Leave requires attachment (medical certificate)
	- Annual Leave: show warning for short notice
	"""
	# Sick Leave: require attachment before submission
	if doc.leave_type == "Sick Leave" and doc.docstatus == 1:
		attachments = frappe.get_all("File", filters={
			"attached_to_doctype": "Leave Application",
			"attached_to_name": doc.name
		})
		if not attachments:
			frappe.throw(
				_("Please attach a medical certificate/document before submitting a Sick Leave application."),
				title=_("Attachment Required")
			)

	# Show warning message for Annual Leave without 2 weeks advance notice
	if doc.leave_type == "Annual Leave" and doc.from_date:
		minimum_from_date = add_days(today(), 14)
		leave_start_date = getdate(doc.from_date)

		if leave_start_date < getdate(minimum_from_date):
			days_diff = (getdate(minimum_from_date) - leave_start_date).days
			frappe.msgprint(
				_("Note: Annual Leave should ideally be submitted at least 2 weeks in advance. "
				  "Your selected start date is {0}, which is {1} day(s) before the recommended date of {2}.").format(
					frappe.format(leave_start_date, {"fieldtype": "Date"}),
					days_diff,
					frappe.format(minimum_from_date, {"fieldtype": "Date"})
				),
				title=_("Early Notice Recommended for Annual Leave"),
				indicator="orange"
			)


def on_submit_leave_application(doc, method=None):
	"""Mark Hajj Leave as consumed when Leave Application is submitted."""
	if doc.leave_type == "Hajj Leave" and doc.status in ['Approved', 'Open']:
		employee = frappe.get_doc("Employee", doc.employee)
		employee.custom_hajj_leave_taken = 1
		employee.custom_hajj_leave_date = doc.from_date
		employee.save(ignore_permissions=True)
		frappe.db.commit()


def on_cancel_leave_application(doc, method=None):
	"""Unmark Hajj Leave if Leave Application is cancelled (before actual leave date)."""
	if doc.leave_type == "Hajj Leave":
		if getdate(doc.from_date) > getdate(today()):
			employee = frappe.get_doc("Employee", doc.employee)

			other_hajj_leaves = frappe.db.count("Leave Application", {
				"employee": doc.employee,
				"leave_type": "Hajj Leave",
				"docstatus": 1,
				"status": ["in", ["Approved", "Open"]],
				"name": ["!=", doc.name]
			})

			if other_hajj_leaves == 0:
				employee.custom_hajj_leave_taken = 0
				employee.custom_hajj_leave_date = None
				employee.save(ignore_permissions=True)
				frappe.db.commit()


def on_update_leave_application(doc, method=None):
	"""
	Send custom workflow notifications when Leave Application workflow state changes.
	Simple HOD-only approval flow (same pattern as Attendance Request).
	"""
	if not doc.has_value_changed("workflow_state"):
		return

	workflow_state = doc.workflow_state
	if not workflow_state:
		return

	# Log workflow action
	previous_state = doc.get_doc_before_save()
	from_state = previous_state.workflow_state if previous_state else ""
	_log_workflow_action(doc, from_state, workflow_state)

	employee = frappe.get_doc("Employee", doc.employee)
	employee_name = employee.employee_name
	employee_email = employee.prefered_email or employee.company_email or employee.personal_email

	leave_url = get_url_to_form("Leave Application", doc.name)

	context = {
		"employee_name": employee_name,
		"employee_id": doc.employee,
		"leave_type": doc.leave_type,
		"from_date": frappe.format(doc.from_date, {"fieldtype": "Date"}),
		"to_date": frappe.format(doc.to_date, {"fieldtype": "Date"}),
		"total_days": doc.total_leave_days,
		"reason": doc.description or "Not specified",
		"leave_url": leave_url,
		"workflow_state": workflow_state
	}

	if workflow_state == "Pending":
		# Notify HOD about new leave application
		_send_notification_to_hod(doc, context, "pending_approval")

	elif workflow_state == "Approved HOD":
		# Notify employee that HOD has approved (final approval)
		_send_notification_to_employee(employee_email, context, "approved")

	elif workflow_state == "Rejected HOD":
		# Notify employee that HOD has rejected
		_send_notification_to_employee(employee_email, context, "rejected")


def _send_notification_to_hod(doc, context, notification_type):
	"""Send notification to HOD (reports_to or department HOD)."""
	from hamptons.utils.email_utils import is_outgoing_email_enabled
	if not is_outgoing_email_enabled():
		return

	recipients = _get_hod_recipients(doc)
	if not recipients:
		return

	subject, message = _get_notification_content(notification_type, context)

	for recipient in recipients:
		try:
			frappe.sendmail(
				recipients=[recipient],
				subject=subject,
				message=message,
				reference_doctype="Leave Application",
				reference_name=doc.name,
				now=True
			)
		except Exception as e:
			frappe.logger().error(f"Leave notification failed for {recipient}: {str(e)}")


def _send_notification_to_employee(email, context, notification_type):
	"""Send notification to the employee."""
	from hamptons.utils.email_utils import is_outgoing_email_enabled
	if not is_outgoing_email_enabled():
		return

	if not email:
		return

	subject, message = _get_notification_content(notification_type, context)

	try:
		frappe.sendmail(
			recipients=[email],
			subject=subject,
			message=message,
			reference_doctype="Leave Application",
			reference_name=context.get("leave_url", "").split("/")[-1] if context.get("leave_url") else None,
			now=True
		)
	except Exception as e:
		frappe.logger().error(f"Leave notification failed for {email}: {str(e)}")


def _get_hod_recipients(doc):
	"""Get HOD email addresses - same logic as Attendance Request."""
	recipients = []
	employee = frappe.get_doc("Employee", doc.employee)

	if employee.reports_to:
		hod = frappe.get_doc("Employee", employee.reports_to)
		hod_email = hod.prefered_email or hod.company_email or hod.personal_email
		if hod_email:
			recipients.append(hod_email)

	if not recipients and employee.department:
		dept_hods = frappe.db.sql("""
			SELECT DISTINCT u.email
			FROM `tabUser` u
			INNER JOIN `tabHas Role` hr ON hr.parent = u.name
			INNER JOIN `tabEmployee` e ON e.user_id = u.name
			WHERE hr.role = 'HOD'
			AND e.department = %s
			AND u.enabled = 1
			AND u.email IS NOT NULL
		""", (employee.department,), as_dict=True)
		recipients.extend([d.email for d in dept_hods if d.email])

	return list(set(recipients))


def _get_notification_content(notification_type, context):
	"""Get email subject and message based on notification type."""
	leave_url = context.get("leave_url", "#")
	emp_name = context["employee_name"]
	emp_id = context["employee_id"]

	table = f"""
		<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Leave Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['leave_type']}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['from_date']}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['to_date']}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Days:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['total_days']}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['reason']}</td></tr>
		</table>"""

	btn_green = f'<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>'
	btn_red = f'<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>'

	templates = {
		"pending_approval": (
			_("Leave Application Pending Your Approval - {0}").format(emp_name),
			f"<h3>Leave Application Pending Approval</h3><p>Dear HOD,</p><p><strong>{emp_name}</strong> ({emp_id}) has submitted a leave application that requires your approval.</p>{table}{btn_green}"
		),
		"approved": (
			_("Your Leave Application - Approved"),
			f"<h3>Leave Application Approved</h3><p>Dear {emp_name},</p><p>Your leave application has been <strong style='color: green;'>approved</strong>.</p>{table}{btn_green}"
		),
		"rejected": (
			_("Your Leave Application - Rejected"),
			f"<h3>Leave Application Rejected</h3><p>Dear {emp_name},</p><p>Your leave application has been <strong style='color: red;'>rejected</strong>.</p>{table}<p>Please contact your HOD for more information.</p>{btn_red}"
		),
	}

	if notification_type in templates:
		return templates[notification_type]

	return (
		_("Leave Application Update - {0}").format(emp_name),
		f"<h3>Leave Application Update</h3><p>Leave application for <strong>{emp_name}</strong> has been updated. Current Status: {context['workflow_state']}</p><p><a href='{leave_url}'>View Leave Application</a></p>"
	)


def _log_workflow_action(doc, from_state, to_state):
	"""Log workflow action to Workflow Action Log."""
	action = "Approve" if "Approved" in to_state else "Reject" if "Rejected" in to_state else "Submit"
	try:
		from hamptons.hamptons.doctype.workflow_action_log.workflow_action_log import log_workflow_action
		log_workflow_action(
			reference_doctype="Leave Application",
			reference_name=doc.name,
			action=action,
			from_state=from_state or "",
			to_state=to_state
		)
	except Exception as e:
		frappe.logger().error(f"Failed to log workflow action for {doc.name}: {str(e)}")

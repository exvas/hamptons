# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Attendance Request Override
- Custom workflow notifications for Attendance Request (HOD-only approval)
- Link Attendance Request approval to Attendance Regularization
- Override validation to allow AR when attendance regularization is pending
"""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, get_url_to_form, getdate

from hrms.hr.doctype.attendance_request.attendance_request import AttendanceRequest


class HamptonsAttendanceRequest(AttendanceRequest):
	"""Override AttendanceRequest to handle regularization-aware validation.

	Standard HRMS blocks Attendance Requests when attendance already exists with the
	same status (e.g. Present → Present). In Hamptons, employees submit ARs to
	regularize early exits / late entries — the attendance record already exists but
	has a pending Attendance Regularization that needs approval via the AR workflow.
	"""

	@frappe.whitelist()
	def get_attendance_warnings(self):
		"""Mark regularization-pending dates as 'Regularize' instead of 'Skip'."""
		warnings = super().get_attendance_warnings()

		for warning in warnings:
			if (
				warning.get("action") == "Skip"
				and warning.get("reason") == "Attendance status unchanged"
				and self._needs_regularization(warning["date"])
			):
				attendance = self.get_attendance_doc(warning["date"])
				warning["action"] = "Overwrite"
				warning["reason"] = "Attendance regularization pending approval"
				if attendance:
					warning["record"] = attendance.name

		return warnings

	def create_or_update_attendance(self, date):
		"""Link AR to existing attendance when regularization is pending."""
		doc = self.get_attendance_doc(date)
		status = self.get_attendance_status(date)

		if doc and doc.status == status:
			# Status unchanged — just link the AR to the attendance record
			if not doc.attendance_request:
				doc.db_set("attendance_request", self.name)
		else:
			super().create_or_update_attendance(date)

	def _needs_regularization(self, date):
		"""Check if attendance on this date has a pending regularization or flagged deviation."""
		if frappe.db.exists(
			"Attendance Regularization",
			{
				"employee": self.employee,
				"posting_date": getdate(date),
				"docstatus": 0,
				"status": "Pending",
			},
		):
			return True

		# Fallback: attendance flagged with late_entry or early_exit but no regularization
		attendance = self.get_attendance_doc(date)
		if attendance and (attendance.late_entry or attendance.early_exit):
			return True

		return False


def on_update_attendance_request(doc, method=None):
	"""
	Send custom workflow notifications when Attendance Request workflow state changes.
	Simple HOD-only approval flow.
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

	request_url = get_url_to_form("Attendance Request", doc.name)

	context = {
		"employee_name": employee_name,
		"employee_id": doc.employee,
		"from_date": frappe.format(doc.from_date, {"fieldtype": "Date"}),
		"to_date": frappe.format(doc.to_date, {"fieldtype": "Date"}) if doc.to_date else frappe.format(doc.from_date, {"fieldtype": "Date"}),
		"reason": doc.reason or "Not specified",
		"request_url": request_url,
		"workflow_state": workflow_state
	}

	if workflow_state == "Pending":
		# Notify HOD about new attendance request
		_send_notification_to_hod(doc, context, "pending_approval")

	elif workflow_state == "Approved HOD":
		# Notify employee that HOD has approved (final approval)
		_send_notification_to_employee(employee_email, context, "approved")
		# Update linked Attendance Regularization
		update_linked_attendance_regularization(doc, "Approved")

	elif workflow_state == "Rejected HOD":
		# Notify employee that HOD has rejected
		_send_notification_to_employee(employee_email, context, "rejected")
		# Update linked Attendance Regularization
		update_linked_attendance_regularization(doc, "Rejected")


def update_linked_attendance_regularization(doc, status):
	"""
	Update the linked Attendance Regularization status when Attendance Request is approved/rejected.
	"""
	attendance_date = getdate(doc.from_date)

	linked_regularization = frappe.db.get_value(
		"Attendance Regularization",
		{
			"employee": doc.employee,
			"posting_date": attendance_date,
			"docstatus": 0,
			"status": "Pending"
		},
		"name"
	)

	if not linked_regularization:
		return

	try:
		regularization_doc = frappe.get_doc("Attendance Regularization", linked_regularization)
		regularization_doc.status = status
		regularization_doc.save(ignore_permissions=True)

		frappe.msgprint(
			_("Attendance Regularization {0} has been {1}").format(
				frappe.utils.get_link_to_form("Attendance Regularization", linked_regularization),
				status
			),
			indicator="green" if status == "Approved" else "orange"
		)
	except Exception as e:
		frappe.log_error(
			message=str(e),
			title=f"Failed to update Attendance Regularization - {linked_regularization}"
		)


def _send_notification_to_hod(doc, context, notification_type):
	"""Email notifications for Attendance Request are disabled."""
	return


def _send_notification_to_employee(email, context, notification_type):
	"""Email notifications for Attendance Request are disabled."""
	return


def _get_hod_recipients(doc):
	"""Get HOD email addresses."""
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
	request_url = context.get("request_url", "#")
	emp_name = context["employee_name"]
	emp_id = context["employee_id"]

	table = f"""
		<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['from_date']}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['to_date']}</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{context['reason']}</td></tr>
		</table>"""

	btn_green = f'<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>'
	btn_red = f'<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>'

	templates = {
		"pending_approval": (
			_("Attendance Request Pending Your Approval - {0}").format(emp_name),
			f"<h3>Attendance Request Pending Approval</h3><p>Dear HOD,</p><p><strong>{emp_name}</strong> ({emp_id}) has submitted an attendance request that requires your approval.</p>{table}{btn_green}"
		),
		"approved": (
			_("Your Attendance Request - Approved"),
			f"<h3>Attendance Request Approved</h3><p>Dear {emp_name},</p><p>Your attendance request has been <strong style='color: green;'>approved</strong>. Your attendance has been regularized.</p>{table}{btn_green}"
		),
		"rejected": (
			_("Your Attendance Request - Rejected"),
			f"<h3>Attendance Request Rejected</h3><p>Dear {emp_name},</p><p>Your attendance request has been <strong style='color: red;'>rejected</strong>.</p>{table}<p>Please contact your HOD for more information.</p>{btn_red}"
		),
	}

	if notification_type in templates:
		return templates[notification_type]

	return (
		_("Attendance Request Update - {0}").format(emp_name),
		f"<h3>Attendance Request Update</h3><p>Attendance request for <strong>{emp_name}</strong> has been updated. Current Status: {context['workflow_state']}</p><p><a href='{request_url}'>View Attendance Request</a></p>"
	)


def _log_workflow_action(doc, from_state, to_state):
	"""Log workflow action to Workflow Action Log."""
	action = "Approve" if "Approved" in to_state else "Reject" if "Rejected" in to_state else "Submit"
	try:
		from hamptons.hamptons.doctype.workflow_action_log.workflow_action_log import log_workflow_action
		log_workflow_action(
			reference_doctype="Attendance Request",
			reference_name=doc.name,
			action=action,
			from_state=from_state or "",
			to_state=to_state
		)
	except Exception as e:
		frappe.logger().error(f"Failed to log workflow action for {doc.name}: {str(e)}")

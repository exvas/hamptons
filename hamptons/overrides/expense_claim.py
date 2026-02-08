"""
Expense Claim Override
- Custom workflow notifications for Expense Claim approval chain
- Same workflow pattern as Leave Application: Employee → HOD → HR / GM
"""

import frappe
from frappe import _
from frappe.utils import get_url_to_form


def on_update_expense_claim(doc, method=None):
	"""
	Send custom workflow notifications when Expense Claim workflow state changes.
	"""
	if not doc.has_value_changed("workflow_state"):
		return

	workflow_state = doc.workflow_state
	if not workflow_state:
		return

	employee = frappe.get_doc("Employee", doc.employee)
	employee_name = employee.employee_name
	employee_email = employee.prefered_email or employee.company_email or employee.personal_email

	claim_url = get_url_to_form("Expense Claim", doc.name)

	context = {
		"employee_name": employee_name,
		"employee_id": doc.employee,
		"total_amount": frappe.format(doc.total_claimed_amount, {"fieldtype": "Currency"}),
		"claim_url": claim_url,
		"workflow_state": workflow_state,
		"doc_name": doc.name
	}

	if workflow_state == "Pending":
		_send_notification_to_role(doc, "HOD", context, "pending_approval")

	elif workflow_state == "Approved HOD":
		_send_notification_to_role(doc, "Leave Approver", context, "pending_hr_approval")
		_send_notification_to_employee(employee_email, context, "hod_approved")

	elif workflow_state == "Rejected HOD":
		_send_notification_to_employee(employee_email, context, "hod_rejected")

	elif workflow_state == "Approved HR":
		_send_notification_to_employee(employee_email, context, "fully_approved")

	elif workflow_state == "Rejected HR":
		_send_notification_to_employee(employee_email, context, "hr_rejected")

	elif workflow_state == "Approved GM":
		_send_notification_to_employee(employee_email, context, "gm_approved")
		_send_notification_to_role(doc, "Hr Approver", context, "gm_approved_info")

	elif workflow_state == "Rejected GM":
		_send_notification_to_employee(employee_email, context, "gm_rejected")


def _send_notification_to_role(doc, role, context, notification_type):
	from hamptons.utils.email_utils import is_outgoing_email_enabled
	if not is_outgoing_email_enabled():
		return

	recipients = _get_role_recipients(doc, role)
	if not recipients:
		return

	subject, message = _get_notification_content(notification_type, context)

	for recipient in recipients:
		try:
			frappe.sendmail(
				recipients=[recipient],
				subject=subject,
				message=message,
				reference_doctype="Expense Claim",
				reference_name=doc.name,
				now=True
			)
		except Exception as e:
			frappe.logger().error(f"Expense Claim notification failed for {recipient}: {str(e)}")


def _send_notification_to_employee(email, context, notification_type):
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
			reference_doctype="Expense Claim",
			reference_name=context.get("doc_name"),
			now=True
		)
	except Exception as e:
		frappe.logger().error(f"Expense Claim notification failed for {email}: {str(e)}")


def _get_role_recipients(doc, role):
	recipients = []
	employee = frappe.get_doc("Employee", doc.employee)

	if role == "HOD":
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

	elif role in ("Leave Approver", "Hr Approver"):
		if doc.expense_approver:
			recipients.append(doc.expense_approver)
		else:
			approvers = frappe.db.sql("""
				SELECT DISTINCT u.email
				FROM `tabUser` u
				INNER JOIN `tabHas Role` hr ON hr.parent = u.name
				WHERE hr.role = 'Hr Approver'
				AND u.enabled = 1
				AND u.email IS NOT NULL
			""", as_dict=True)
			recipients.extend([d.email for d in approvers if d.email])

	return list(set(recipients))


def _get_notification_content(notification_type, context):
	claim_url = context.get("claim_url", "#")
	emp_name = context["employee_name"]
	emp_id = context["employee_id"]
	amount = context["total_amount"]

	table = f"""
		<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Employee:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{emp_name} ({emp_id})</td></tr>
			<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Amount:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{amount}</td></tr>
		</table>"""

	btn_green = f'<p style="margin-top: 20px;"><a href="{claim_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Expense Claim</a></p>'
	btn_blue = f'<p style="margin-top: 20px;"><a href="{claim_url}" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Expense Claim</a></p>'
	btn_red = f'<p style="margin-top: 20px;"><a href="{claim_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Expense Claim</a></p>'

	templates = {
		"pending_approval": (
			_("Expense Claim Pending Your Approval - {0}").format(emp_name),
			f"<h3>Expense Claim Pending Approval</h3><p>Dear HOD,</p><p><strong>{emp_name}</strong> ({emp_id}) has submitted an expense claim that requires your approval.</p>{table}{btn_green}"
		),
		"pending_hr_approval": (
			_("Expense Claim Pending HR Approval - {0}").format(emp_name),
			f"<h3>Expense Claim Pending HR Approval</h3><p>Dear HR Team,</p><p>An expense claim from <strong>{emp_name}</strong> ({emp_id}) has been approved by HOD and is now pending your approval.</p>{table}{btn_blue}"
		),
		"hod_approved": (
			_("Your Expense Claim - HOD Approved"),
			f"<h3>Expense Claim Update</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: green;'>approved by your HOD</strong> and is now pending HR approval.</p>{table}{btn_green}"
		),
		"hod_rejected": (
			_("Your Expense Claim - Rejected by HOD"),
			f"<h3>Expense Claim Rejected</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: red;'>rejected by your HOD</strong>.</p>{table}<p>Please contact your HOD for more information.</p>{btn_red}"
		),
		"fully_approved": (
			_("Your Expense Claim - Approved"),
			f"<h3>Expense Claim Approved</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: green;'>fully approved</strong>.</p>{table}{btn_green}"
		),
		"hr_rejected": (
			_("Your Expense Claim - Rejected by HR"),
			f"<h3>Expense Claim Rejected</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: red;'>rejected by HR</strong>.</p>{table}<p>Please contact HR for more information.</p>{btn_red}"
		),
		"gm_approved": (
			_("Your Expense Claim - Approved by GM"),
			f"<h3>Expense Claim Approved</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: green;'>approved by the General Manager</strong>.</p>{table}{btn_green}"
		),
		"gm_approved_info": (
			_("Expense Claim Approved by GM - {0}").format(emp_name),
			f"<h3>Expense Claim Approved by GM</h3><p>Dear HR Team,</p><p>An expense claim from <strong>{emp_name}</strong> ({emp_id}) has been approved by the General Manager.</p>{table}{btn_green}"
		),
		"gm_rejected": (
			_("Your Expense Claim - Rejected by GM"),
			f"<h3>Expense Claim Rejected</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: red;'>rejected by the General Manager</strong>.</p>{table}<p>Please contact the General Manager for more information.</p>{btn_red}"
		),
	}

	if notification_type in templates:
		return templates[notification_type]

	return (
		_("Expense Claim Update - {0}").format(emp_name),
		f"<h3>Expense Claim Update</h3><p>Expense claim for <strong>{emp_name}</strong> has been updated. Current Status: {context['workflow_state']}</p><p><a href='{claim_url}'>View Expense Claim</a></p>"
	)

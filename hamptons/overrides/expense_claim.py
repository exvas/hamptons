"""
Expense Claim Override
- Custom workflow notifications for Expense Claim (HOD-only approval)
- Same pattern as Attendance Request and Leave Application
"""

import frappe
from frappe import _
from frappe.utils import get_url_to_form


def on_update_expense_claim(doc, method=None):
	"""
	Send custom workflow notifications when Expense Claim workflow state changes.
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
		# Notify HOD about new expense claim
		_send_notification_to_hod(doc, context, "pending_approval")

	elif workflow_state == "Approved HOD":
		# Notify employee that HOD has approved (final approval)
		_send_notification_to_employee(employee_email, context, "approved")

	elif workflow_state == "Rejected HOD":
		# Notify employee that HOD has rejected
		_send_notification_to_employee(employee_email, context, "rejected")


def _send_notification_to_hod(doc, context, notification_type):
	"""Email notifications for Expense Claim are disabled."""
	return


def _send_notification_to_employee(email, context, notification_type):
	"""Email notifications for Expense Claim are disabled."""
	return


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
	btn_red = f'<p style="margin-top: 20px;"><a href="{claim_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Expense Claim</a></p>'

	templates = {
		"pending_approval": (
			_("Expense Claim Pending Your Approval - {0}").format(emp_name),
			f"<h3>Expense Claim Pending Approval</h3><p>Dear HOD,</p><p><strong>{emp_name}</strong> ({emp_id}) has submitted an expense claim that requires your approval.</p>{table}{btn_green}"
		),
		"approved": (
			_("Your Expense Claim - Approved"),
			f"<h3>Expense Claim Approved</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: green;'>approved</strong>.</p>{table}{btn_green}"
		),
		"rejected": (
			_("Your Expense Claim - Rejected"),
			f"<h3>Expense Claim Rejected</h3><p>Dear {emp_name},</p><p>Your expense claim has been <strong style='color: red;'>rejected</strong>.</p>{table}<p>Please contact your HOD for more information.</p>{btn_red}"
		),
	}

	if notification_type in templates:
		return templates[notification_type]

	return (
		_("Expense Claim Update - {0}").format(emp_name),
		f"<h3>Expense Claim Update</h3><p>Expense claim for <strong>{emp_name}</strong> has been updated. Current Status: {context['workflow_state']}</p><p><a href='{claim_url}'>View Expense Claim</a></p>"
	)


def _log_workflow_action(doc, from_state, to_state):
	"""Log workflow action to Workflow Action Log."""
	action = "Approve" if "Approved" in to_state else "Reject" if "Rejected" in to_state else "Submit"
	try:
		from hamptons.hamptons.doctype.workflow_action_log.workflow_action_log import log_workflow_action
		log_workflow_action(
			reference_doctype="Expense Claim",
			reference_name=doc.name,
			action=action,
			from_state=from_state or "",
			to_state=to_state
		)
	except Exception as e:
		frappe.logger().error(f"Failed to log workflow action for {doc.name}: {str(e)}")

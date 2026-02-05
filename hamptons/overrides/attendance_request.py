# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Attendance Request Override
- Custom workflow notifications for Attendance Request
- Link Attendance Request approval to Attendance Regularization
"""

import frappe
from frappe import _
from frappe.utils import get_url_to_form, getdate


def on_update_attendance_request(doc, method=None):
	"""
	Send custom workflow notifications when Attendance Request workflow state changes

	Args:
		doc: Attendance Request document
		method: Method name (not used)
	"""
	# Check if workflow_state has changed
	if not doc.has_value_changed("workflow_state"):
		return

	workflow_state = doc.workflow_state
	if not workflow_state:
		return

	# Get employee details
	employee = frappe.get_doc("Employee", doc.employee)
	employee_name = employee.employee_name
	employee_email = employee.prefered_email or employee.company_email or employee.personal_email

	# Get attendance request URL
	request_url = get_url_to_form("Attendance Request", doc.name)

	# Build common context for email
	context = {
		"employee_name": employee_name,
		"employee_id": doc.employee,
		"from_date": frappe.format(doc.from_date, {"fieldtype": "Date"}),
		"to_date": frappe.format(doc.to_date, {"fieldtype": "Date"}) if doc.to_date else frappe.format(doc.from_date, {"fieldtype": "Date"}),
		"reason": doc.reason or "Not specified",
		"request_url": request_url,
		"workflow_state": workflow_state
	}

	# Send notification based on workflow state
	if workflow_state == "Pending":
		# Notify HOD about new attendance request
		send_notification_to_role(doc, "HOD", context, "pending_approval")

	elif workflow_state == "Approved HOD":
		# Notify HR Approver about attendance request pending their approval
		send_notification_to_role(doc, "Hr Approver", context, "pending_hr_approval")
		# Also notify employee that HOD has approved
		send_notification_to_employee(employee_email, employee_name, context, "hod_approved")

	elif workflow_state == "Rejected HOD":
		# Notify employee that HOD has rejected
		send_notification_to_employee(employee_email, employee_name, context, "hod_rejected")

	elif workflow_state == "Approved HR":
		# Notify employee that request is fully approved
		send_notification_to_employee(employee_email, employee_name, context, "fully_approved")
		# Update linked Attendance Regularization
		update_linked_attendance_regularization(doc, "Approved")

	elif workflow_state == "Rejected HR":
		# Notify employee that HR has rejected
		send_notification_to_employee(employee_email, employee_name, context, "hr_rejected")
		# Update linked Attendance Regularization
		update_linked_attendance_regularization(doc, "Rejected")


def update_linked_attendance_regularization(doc, status):
	"""
	Update the linked Attendance Regularization status when Attendance Request is approved/rejected

	Args:
		doc: Attendance Request document
		status: Status to set ("Approved" or "Rejected")
	"""
	# Find linked Attendance Regularization based on employee and date
	attendance_date = getdate(doc.from_date)

	linked_regularization = frappe.db.get_value(
		"Attendance Regularization",
		{
			"employee": doc.employee,
			"posting_date": attendance_date,
			"docstatus": 0,  # Draft
			"status": "Pending"
		},
		"name"
	)

	if not linked_regularization:
		frappe.logger().info(
			f"No pending Attendance Regularization found for employee {doc.employee} on {attendance_date}"
		)
		return

	try:
		regularization_doc = frappe.get_doc("Attendance Regularization", linked_regularization)

		# Update the status - this will trigger the auto-approve/reject logic
		regularization_doc.status = status
		regularization_doc.save(ignore_permissions=True)

		frappe.logger().info(
			f"Updated Attendance Regularization {linked_regularization} to {status} "
			f"based on Attendance Request {doc.name}"
		)

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


def send_notification_to_role(doc, role, context, notification_type):
	"""
	Send notification to users with a specific role

	Args:
		doc: Attendance Request document
		role: Role name to notify (e.g., "HOD", "Hr Approver")
		context: Email context dictionary
		notification_type: Type of notification for subject/message
	"""
	# Check if outgoing email is enabled
	from hamptons.utils.email_utils import is_outgoing_email_enabled
	if not is_outgoing_email_enabled():
		frappe.logger().info(f"Skipping attendance request notification: No enabled outgoing email account")
		return

	recipients = get_role_recipients(doc, role)

	if not recipients:
		frappe.logger().warning(f"No recipients found for role {role} for attendance request {doc.name}")
		return

	subject, message = get_notification_content(notification_type, context)

	for recipient in recipients:
		try:
			frappe.sendmail(
				recipients=[recipient],
				subject=subject,
				message=message,
				reference_doctype="Attendance Request",
				reference_name=doc.name,
				now=True
			)
		except Exception as e:
			frappe.logger().error(f"Failed to send email to {recipient}: {str(e)}")


def send_notification_to_employee(email, employee_name, context, notification_type):
	"""
	Send notification to the employee

	Args:
		email: Employee email address
		employee_name: Employee name
		context: Email context dictionary
		notification_type: Type of notification for subject/message
	"""
	# Check if outgoing email is enabled
	from hamptons.utils.email_utils import is_outgoing_email_enabled
	if not is_outgoing_email_enabled():
		frappe.logger().info(f"Skipping employee notification: No enabled outgoing email account")
		return

	if not email:
		frappe.logger().warning(f"No email found for employee {employee_name}")
		return

	subject, message = get_notification_content(notification_type, context)

	try:
		frappe.sendmail(
			recipients=[email],
			subject=subject,
			message=message,
			reference_doctype="Attendance Request",
			reference_name=context.get("request_url", "").split("/")[-1] if context.get("request_url") else None,
			now=True
		)
	except Exception as e:
		frappe.logger().error(f"Failed to send email to {email}: {str(e)}")


def get_role_recipients(doc, role):
	"""
	Get email addresses of users with the specified role

	Args:
		doc: Attendance Request document
		role: Role name

	Returns:
		List of email addresses
	"""
	recipients = []

	# For HOD role, get the department head
	if role == "HOD":
		# Try to get department head from employee's reports_to
		employee = frappe.get_doc("Employee", doc.employee)
		if employee.reports_to:
			hod_employee = frappe.get_doc("Employee", employee.reports_to)
			hod_email = hod_employee.prefered_email or hod_employee.company_email or hod_employee.personal_email
			if hod_email:
				recipients.append(hod_email)

		# If no reports_to, get users with HOD role in the same department
		if not recipients and employee.department:
			department_hods = frappe.db.sql("""
				SELECT DISTINCT u.email
				FROM `tabUser` u
				INNER JOIN `tabHas Role` hr ON hr.parent = u.name
				INNER JOIN `tabEmployee` e ON e.user_id = u.name
				WHERE hr.role = 'HOD'
				AND e.department = %s
				AND u.enabled = 1
				AND u.email IS NOT NULL
			""", (employee.department,), as_dict=True)
			recipients.extend([d.email for d in department_hods if d.email])

	# For Hr Approver role
	elif role == "Hr Approver":
		# Get users with Hr Approver role
		hr_approvers = frappe.db.sql("""
			SELECT DISTINCT u.email
			FROM `tabUser` u
			INNER JOIN `tabHas Role` hr ON hr.parent = u.name
			WHERE hr.role = 'Hr Approver'
			AND u.enabled = 1
			AND u.email IS NOT NULL
		""", as_dict=True)
		recipients.extend([d.email for d in hr_approvers if d.email])

	return list(set(recipients))  # Remove duplicates


def get_notification_content(notification_type, context):
	"""
	Get email subject and message based on notification type

	Args:
		notification_type: Type of notification
		context: Email context dictionary

	Returns:
		Tuple of (subject, message)
	"""
	request_url = context.get("request_url", "#")

	if notification_type == "pending_approval":
		subject = _("Attendance Request Pending Your Approval - {0}").format(context["employee_name"])
		message = _("""
			<h3>Attendance Request Pending Approval</h3>
			<p>Dear HOD,</p>
			<p><strong>{employee_name}</strong> ({employee_id}) has submitted an attendance request that requires your approval.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
			</table>
			<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>
		""").format(**context)

	elif notification_type == "pending_hr_approval":
		subject = _("Attendance Request Pending HR Approval - {0}").format(context["employee_name"])
		message = _("""
			<h3>Attendance Request Pending HR Approval</h3>
			<p>Dear HR Team,</p>
			<p>An attendance request from <strong>{employee_name}</strong> ({employee_id}) has been approved by HOD and is now pending your approval.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
			</table>
			<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>
		""").format(**context)

	elif notification_type == "hod_approved":
		subject = _("Your Attendance Request - HOD Approved")
		message = _("""
			<h3>Attendance Request Update</h3>
			<p>Dear {employee_name},</p>
			<p>Your attendance request has been <strong style="color: green;">approved by your HOD</strong> and is now pending HR approval.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">Pending HR Approval</td></tr>
			</table>
			<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>
		""").format(**context)

	elif notification_type == "hod_rejected":
		subject = _("Your Attendance Request - Rejected by HOD")
		message = _("""
			<h3>Attendance Request Rejected</h3>
			<p>Dear {employee_name},</p>
			<p>We regret to inform you that your attendance request has been <strong style="color: red;">rejected by your HOD</strong>.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: red;">Rejected by HOD</td></tr>
			</table>
			<p>Please contact your HOD for more information.</p>
			<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>
		""").format(**context)

	elif notification_type == "fully_approved":
		subject = _("Your Attendance Request - Approved")
		message = _("""
			<h3>Attendance Request Approved</h3>
			<p>Dear {employee_name},</p>
			<p>Congratulations! Your attendance request has been <strong style="color: green;">fully approved</strong>.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: green;">Approved</td></tr>
			</table>
			<p>Your attendance has been regularized.</p>
			<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>
		""").format(**context)

	elif notification_type == "hr_rejected":
		subject = _("Your Attendance Request - Rejected by HR")
		message = _("""
			<h3>Attendance Request Rejected</h3>
			<p>Dear {employee_name},</p>
			<p>We regret to inform you that your attendance request has been <strong style="color: red;">rejected by HR</strong>.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: red;">Rejected by HR</td></tr>
			</table>
			<p>Please contact HR for more information.</p>
			<p style="margin-top: 20px;"><a href="{request_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Attendance Request</a></p>
		""").format(**context)

	else:
		subject = _("Attendance Request Update - {0}").format(context["employee_name"])
		message = _("""
			<h3>Attendance Request Update</h3>
			<p>Attendance request for <strong>{employee_name}</strong> has been updated.</p>
			<p>Current Status: {workflow_state}</p>
			<p><a href="{request_url}">View Attendance Request</a></p>
		""").format(**context)

	return subject, message

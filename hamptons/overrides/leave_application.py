# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

"""
Leave Application Override
- Marks Hajj Leave as consumed when Leave Application is approved
- Custom workflow notifications for Leave Application
"""

import frappe
from frappe import _
from frappe.utils import getdate, add_days, today, get_url_to_form


def validate_leave_application(doc, method=None):
	"""
	Validate Leave Application - show warning for Annual Leave without 2 weeks advance notice

	Args:
		doc: Leave Application document
		method: Method name (not used)
	"""
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


def on_update_leave_application(doc, method=None):
	"""
	Send custom workflow notifications when Leave Application workflow state changes

	Args:
		doc: Leave Application document
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

	# Get leave application URL
	leave_url = get_url_to_form("Leave Application", doc.name)

	# Build common context for email
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

	# Send notification based on workflow state
	if workflow_state == "Pending":
		# Notify HOD about new leave application
		send_notification_to_role(doc, "HOD", context, "pending_approval")

	elif workflow_state == "Approved HOD":
		# Notify Leave Approver (HR) about leave pending their approval
		send_notification_to_role(doc, "Leave Approver", context, "pending_hr_approval")
		# Also notify employee that HOD has approved
		send_notification_to_employee(employee_email, employee_name, context, "hod_approved")

	elif workflow_state == "Rejected HOD":
		# Notify employee that HOD has rejected
		send_notification_to_employee(employee_email, employee_name, context, "hod_rejected")

	elif workflow_state == "Approved HR":
		# Notify employee that leave is fully approved
		send_notification_to_employee(employee_email, employee_name, context, "fully_approved")

	elif workflow_state == "Rejected HR":
		# Notify employee that HR has rejected
		send_notification_to_employee(employee_email, employee_name, context, "hr_rejected")


def send_notification_to_role(doc, role, context, notification_type):
	"""
	Send notification to users with a specific role in the employee's department

	Args:
		doc: Leave Application document
		role: Role name to notify (e.g., "HOD", "Leave Approver")
		context: Email context dictionary
		notification_type: Type of notification for subject/message
	"""
	recipients = get_role_recipients(doc, role)

	if not recipients:
		frappe.logger().warning(f"No recipients found for role {role} for leave application {doc.name}")
		return

	subject, message = get_notification_content(notification_type, context)

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
	if not email:
		frappe.logger().warning(f"No email found for employee {employee_name}")
		return

	subject, message = get_notification_content(notification_type, context)

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
		frappe.logger().error(f"Failed to send email to {email}: {str(e)}")


def get_role_recipients(doc, role):
	"""
	Get email addresses of users with the specified role

	Args:
		doc: Leave Application document
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

	# For Leave Approver role
	elif role == "Leave Approver":
		# First try to get the leave_approver field from leave application
		if doc.leave_approver:
			recipients.append(doc.leave_approver)
		else:
			# Get users with Leave Approver role
			leave_approvers = frappe.db.sql("""
				SELECT DISTINCT u.email
				FROM `tabUser` u
				INNER JOIN `tabHas Role` hr ON hr.parent = u.name
				WHERE hr.role = 'Leave Approver'
				AND u.enabled = 1
				AND u.email IS NOT NULL
			""", as_dict=True)
			recipients.extend([d.email for d in leave_approvers if d.email])

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
	leave_url = context.get("leave_url", "#")

	if notification_type == "pending_approval":
		subject = _("Leave Application Pending Your Approval - {0}").format(context["employee_name"])
		message = _("""
			<h3>Leave Application Pending Approval</h3>
			<p>Dear HOD,</p>
			<p><strong>{employee_name}</strong> ({employee_id}) has submitted a leave application that requires your approval.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Leave Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{leave_type}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Days:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_days}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
			</table>
			<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>
		""").format(**context)

	elif notification_type == "pending_hr_approval":
		subject = _("Leave Application Pending HR Approval - {0}").format(context["employee_name"])
		message = _("""
			<h3>Leave Application Pending HR Approval</h3>
			<p>Dear HR Team,</p>
			<p>A leave application from <strong>{employee_name}</strong> ({employee_id}) has been approved by HOD and is now pending your approval.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Leave Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{leave_type}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Days:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_days}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Reason:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{reason}</td></tr>
			</table>
			<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #2196F3; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>
		""").format(**context)

	elif notification_type == "hod_approved":
		subject = _("Your Leave Application - HOD Approved")
		message = _("""
			<h3>Leave Application Update</h3>
			<p>Dear {employee_name},</p>
			<p>Your leave application has been <strong style="color: green;">approved by your HOD</strong> and is now pending HR approval.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Leave Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{leave_type}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Days:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_days}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">Pending HR Approval</td></tr>
			</table>
			<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>
		""").format(**context)

	elif notification_type == "hod_rejected":
		subject = _("Your Leave Application - Rejected by HOD")
		message = _("""
			<h3>Leave Application Rejected</h3>
			<p>Dear {employee_name},</p>
			<p>We regret to inform you that your leave application has been <strong style="color: red;">rejected by your HOD</strong>.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Leave Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{leave_type}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Days:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_days}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: red;">Rejected by HOD</td></tr>
			</table>
			<p>Please contact your HOD for more information.</p>
			<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>
		""").format(**context)

	elif notification_type == "fully_approved":
		subject = _("Your Leave Application - Approved")
		message = _("""
			<h3>Leave Application Approved</h3>
			<p>Dear {employee_name},</p>
			<p>Congratulations! Your leave application has been <strong style="color: green;">fully approved</strong>.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Leave Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{leave_type}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Days:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_days}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: green;">Approved</td></tr>
			</table>
			<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>
		""").format(**context)

	elif notification_type == "hr_rejected":
		subject = _("Your Leave Application - Rejected by HR")
		message = _("""
			<h3>Leave Application Rejected</h3>
			<p>Dear {employee_name},</p>
			<p>We regret to inform you that your leave application has been <strong style="color: red;">rejected by HR</strong>.</p>
			<table style="border-collapse: collapse; width: 100%; max-width: 500px;">
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Leave Type:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{leave_type}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>From Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{from_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>To Date:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{to_date}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Total Days:</strong></td><td style="padding: 8px; border: 1px solid #ddd;">{total_days}</td></tr>
				<tr><td style="padding: 8px; border: 1px solid #ddd;"><strong>Status:</strong></td><td style="padding: 8px; border: 1px solid #ddd; color: red;">Rejected by HR</td></tr>
			</table>
			<p>Please contact HR for more information.</p>
			<p style="margin-top: 20px;"><a href="{leave_url}" style="background-color: #f44336; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">View Leave Application</a></p>
		""").format(**context)

	else:
		subject = _("Leave Application Update - {0}").format(context["employee_name"])
		message = _("""
			<h3>Leave Application Update</h3>
			<p>Leave application for <strong>{employee_name}</strong> has been updated.</p>
			<p>Current Status: {workflow_state}</p>
			<p><a href="{leave_url}">View Leave Application</a></p>
		""").format(**context)

	return subject, message

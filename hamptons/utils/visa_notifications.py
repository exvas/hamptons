# Copyright (c) 2026, Hamptons and contributors
# For license information, please see license.txt

"""
Family Visa Date expiry notification.
Sends email alerts X days before the visa date expires,
based on Hamptons Settings configuration.
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate, formatdate


def send_visa_expiry_alerts():
	"""
	Scheduled job: check employees whose Family Visa Date is expiring
	within the configured 'Before Notify' days and send email alerts.

	Uses Hamptons Settings:
	- enable_alert: must be checked
	- before_notify: number of days before expiry to notify
	- email_recipients: comma/newline separated email addresses
	"""
	settings = frappe.get_single("Hamptons Settings")

	if not settings.enable_alert:
		return

	before_days = int(settings.before_notify or 30)
	recipients_raw = settings.email_recipients or ""

	# Parse recipients (comma or newline separated)
	recipients = [
		r.strip() for r in recipients_raw.replace("\n", ",").split(",")
		if r.strip()
	]

	if not recipients:
		frappe.logger().warning("Visa expiry alerts enabled but no email recipients configured")
		return

	# Calculate the target date: today + before_notify days
	target_date = add_days(today(), before_days)

	# Find active employees whose family visa date is expiring on or before the target date
	# and hasn't expired more than 30 days ago (avoid alerting for very old records)
	employees = frappe.db.sql("""
		SELECT name, employee_name, department, designation,
			   custom_family_member_id_card, custom_family_visa_date
		FROM tabEmployee
		WHERE status = 'Active'
		AND custom_family_visa_date IS NOT NULL
		AND custom_family_visa_date <= %s
		AND custom_family_visa_date >= %s
		ORDER BY custom_family_visa_date ASC
	""", (target_date, today()), as_dict=True)

	if not employees:
		return

	# Build email content
	subject = _("Family Visa Expiry Alert - {0} Employee(s)").format(len(employees))

	rows = ""
	for emp in employees:
		days_remaining = (getdate(emp.custom_family_visa_date) - getdate(today())).days
		if days_remaining < 0:
			status = f'<span style="color: red; font-weight: bold;">Expired {abs(days_remaining)} days ago</span>'
		elif days_remaining == 0:
			status = '<span style="color: red; font-weight: bold;">Expires Today</span>'
		else:
			status = f'<span style="color: orange; font-weight: bold;">{days_remaining} days remaining</span>'

		rows += f"""
		<tr>
			<td style="padding: 8px; border: 1px solid #ddd;">{emp.name}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{emp.employee_name}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{emp.department or '-'}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{emp.custom_family_member_id_card or '-'}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{formatdate(emp.custom_family_visa_date)}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{status}</td>
		</tr>
		"""

	message = f"""
	<h3>Family Visa Expiry Alert</h3>
	<p>The following {len(employees)} employee(s) have family visas expiring within {before_days} days:</p>
	<table style="border-collapse: collapse; width: 100%;">
		<thead>
			<tr style="background-color: #f2f2f2;">
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Employee ID</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Employee Name</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Department</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Family Member ID</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Visa Expiry Date</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Status</th>
			</tr>
		</thead>
		<tbody>
			{rows}
		</tbody>
	</table>
	<p style="margin-top: 15px; color: #666;">This is an automated alert from Hamptons HRMS.</p>
	"""

	from hamptons.utils.email_utils import send_email_if_enabled
	send_email_if_enabled(
		recipients=recipients,
		subject=subject,
		message=message,
		now=True
	)

	frappe.logger().info(
		f"Sent visa expiry alert for {len(employees)} employees to {len(recipients)} recipients"
	)

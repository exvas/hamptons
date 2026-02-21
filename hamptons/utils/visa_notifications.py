# Copyright (c) 2026, Hamptons and contributors
# For license information, please see license.txt

"""
Family Visa Date expiry notification.
Sends email alerts X days before the visa date expires,
based on Hamptons Settings configuration.
Uses Employee Family Info child table for per-family-member tracking.
"""

import frappe
from frappe import _
from frappe.utils import today, add_days, getdate, formatdate


def send_visa_expiry_alerts():
	"""
	Scheduled job: check family members whose Visa Date is expiring
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

	# Find family members with expiring visas from the child table
	expiring = frappe.db.sql("""
		SELECT fi.family_member_name, fi.relationship, fi.id_card, fi.visa_date, fi.remarks,
			   e.name as employee_id, e.employee_name, e.department
		FROM `tabEmployee Family Info` fi
		INNER JOIN `tabEmployee` e ON fi.parent = e.name AND fi.parenttype = 'Employee'
		WHERE e.status = 'Active'
		AND fi.visa_date IS NOT NULL
		AND fi.visa_date <= %s
		AND fi.visa_date >= %s
		ORDER BY fi.visa_date ASC
	""", (target_date, today()), as_dict=True)

	if not expiring:
		return

	# Build email content
	subject = _("Family Visa Expiry Alert - {0} Record(s)").format(len(expiring))

	rows = ""
	for rec in expiring:
		days_remaining = (getdate(rec.visa_date) - getdate(today())).days
		if days_remaining < 0:
			status = f'<span style="color: red; font-weight: bold;">Expired {abs(days_remaining)} days ago</span>'
		elif days_remaining == 0:
			status = '<span style="color: red; font-weight: bold;">Expires Today</span>'
		else:
			status = f'<span style="color: orange; font-weight: bold;">{days_remaining} days remaining</span>'

		rows += f"""
		<tr>
			<td style="padding: 8px; border: 1px solid #ddd;">{rec.employee_id}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{rec.employee_name}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{rec.department or '-'}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{rec.family_member_name or '-'}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{rec.relationship or '-'}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{rec.id_card or '-'}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{formatdate(rec.visa_date)}</td>
			<td style="padding: 8px; border: 1px solid #ddd;">{status}</td>
		</tr>
		"""

	message = f"""
	<h3>Family Visa Expiry Alert</h3>
	<p>The following {len(expiring)} family member(s) have visas expiring within {before_days} days:</p>
	<table style="border-collapse: collapse; width: 100%;">
		<thead>
			<tr style="background-color: #f2f2f2;">
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Employee ID</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Employee Name</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Department</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Family Member</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Relationship</th>
				<th style="padding: 8px; border: 1px solid #ddd; text-align: left;">ID Card</th>
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
		f"Sent visa expiry alert for {len(expiring)} family members to {len(recipients)} recipients"
	)

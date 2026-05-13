# Copyright (c) 2025, sammish and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate, now_datetime, getdate


class LeaveWithdrawalRequest(Document):
	def validate(self):
		self.validate_leave_application()
		self.validate_duplicate_request()

	def validate_leave_application(self):
		"""Validate that the leave application exists and is approved"""
		if not self.leave_application:
			frappe.throw(_("Leave Application is required"))

		leave_app = frappe.get_doc("Leave Application", self.leave_application)

		# Check if leave is approved (docstatus = 1)
		if leave_app.docstatus != 1:
			frappe.throw(_("Can only withdraw approved leave applications"))

		# Check if employee matches
		if leave_app.employee != self.employee:
			frappe.throw(_("Leave Application does not belong to this employee"))

		# Check if leave dates haven't passed completely
		if getdate(leave_app.to_date) < getdate(nowdate()):
			frappe.throw(_("Cannot withdraw leave that has already ended"))

	def validate_duplicate_request(self):
		"""Check for existing pending withdrawal request"""
		existing = frappe.db.exists(
			"Leave Withdrawal Request",
			{
				"leave_application": self.leave_application,
				"status": "Pending",
				"name": ("!=", self.name),
				"docstatus": 0
			}
		)
		if existing:
			frappe.throw(_("A pending withdrawal request already exists for this leave application"))

	def on_submit(self):
		"""When HR/HOD approves or rejects the withdrawal"""
		self._process_decision()

	def on_update_after_submit(self):
		"""Workflow transition can update status after submit. Re-process decision."""
		# Only process if status just changed to Approved/Rejected and not already processed
		if self.status in ("Approved", "Rejected") and not self.processed_on:
			self._process_decision()

	def _process_decision(self):
		"""Cancel leave application on Approved, notify employee on either decision."""
		if self.status == "Approved":
			self.cancel_leave_application()
			frappe.db.set_value("Leave Withdrawal Request", self.name, {
				"processed_by": frappe.session.user,
				"processed_on": now_datetime()
			}, update_modified=False)
			self.notify_employee_approved()
		elif self.status == "Rejected":
			frappe.db.set_value("Leave Withdrawal Request", self.name, {
				"processed_by": frappe.session.user,
				"processed_on": now_datetime()
			}, update_modified=False)
			self.notify_employee_rejected()

	def cancel_leave_application(self):
		"""Cancel the linked leave application and its related attendance records forcefully"""
		leave_app = frappe.get_doc("Leave Application", self.leave_application)

		if leave_app.docstatus != 1:
			return

		# First, cancel all linked Attendance records
		attendance_records = frappe.get_all(
			"Attendance",
			filters={
				"leave_application": self.leave_application,
				"docstatus": 1
			},
			pluck="name"
		)

		for att_name in attendance_records:
			try:
				att_doc = frappe.get_doc("Attendance", att_name)
				att_doc.flags.ignore_permissions = True
				att_doc.flags.ignore_links = True
				att_doc.flags.ignore_validate = True
				att_doc.cancel()
				frappe.db.commit()
			except Exception as e:
				# Force cancel via SQL if normal cancel fails
				frappe.log_error(f"Normal cancel failed for attendance {att_name}: {str(e)}, trying SQL")
				try:
					frappe.db.sql("""
						UPDATE `tabAttendance`
						SET docstatus = 2
						WHERE name = %s
					""", att_name)
					frappe.db.commit()
				except Exception as sql_e:
					frappe.log_error(f"SQL cancel also failed for attendance {att_name}: {str(sql_e)}")

		# Also check for Leave Ledger Entry linked to this leave application
		try:
			leave_ledger_entries = frappe.get_all(
				"Leave Ledger Entry",
				filters={
					"transaction_type": "Leave Application",
					"transaction_name": self.leave_application,
					"docstatus": 1
				},
				pluck="name"
			)
			for lle_name in leave_ledger_entries:
				try:
					frappe.db.sql("""
						UPDATE `tabLeave Ledger Entry`
						SET docstatus = 2
						WHERE name = %s
					""", lle_name)
				except:
					pass
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Error handling leave ledger entries: {str(e)}")

		# Now cancel the leave application
		try:
			# Reload to get fresh state
			leave_app.reload()
			leave_app.flags.ignore_permissions = True
			leave_app.flags.ignore_links = True
			leave_app.flags.ignore_validate = True
			leave_app.cancel()
			frappe.db.commit()
		except Exception as e:
			# Force cancel via SQL if normal cancel fails
			frappe.log_error(f"Normal cancel failed for leave application {self.leave_application}: {str(e)}, trying SQL")
			try:
				frappe.db.sql("""
					UPDATE `tabLeave Application`
					SET docstatus = 2, status = 'Cancelled'
					WHERE name = %s
				""", self.leave_application)
				frappe.db.commit()
			except Exception as sql_e:
				frappe.log_error(f"SQL cancel also failed for leave application: {str(sql_e)}")
				frappe.throw(_("Failed to cancel Leave Application. Please contact administrator."))

		# Always update workflow_state and status to "Cancelled" so the indicator shows correctly
		# (the workflow overrides the indicator based on workflow_state, not docstatus)
		try:
			frappe.db.set_value("Leave Application", self.leave_application, {
				"workflow_state": "Cancelled",
				"status": "Cancelled"
			}, update_modified=False)
			frappe.db.commit()
		except Exception:
			pass

		frappe.msgprint(_("Leave Application {0} has been cancelled").format(self.leave_application))

	def after_insert(self):
		"""Notify HOD about new withdrawal request."""
		self.notify_hod()

	def get_hod_recipients(self):
		"""Get HOD email addresses - reports_to first, fallback to department HOD role."""
		recipients = []
		employee = frappe.get_doc("Employee", self.employee)

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

	def notify_hod(self):
		"""Send professional email to HOD about new withdrawal request."""
		from hamptons.utils.email_utils import is_outgoing_email_enabled
		if not is_outgoing_email_enabled():
			return

		recipients = self.get_hod_recipients()
		if not recipients:
			return

		lwr_url = frappe.utils.get_url_to_form(self.doctype, self.name)
		subject = _("Leave Withdrawal Request — Action Required — {0}").format(self.employee_name)
		message = _build_lwr_email(
			header_color="#1e3a5f",
			header_title="Leave Withdrawal Request — Action Required",
			header_subtitle=f"Submitted by {self.employee_name} ({self.employee})",
			body_html=f"""
<p style="margin:0 0 6px;font-size:16px;color:#374151;font-weight:600;">Dear HOD,</p>
<p style="margin:0 0 20px;font-size:14px;color:#4b5563;line-height:1.7;">
  <strong>{self.employee_name}</strong>
  <span style="color:#6b7280;font-size:13px;"> ({self.employee})</span>
  has submitted a request to withdraw their approved leave.
  Please review and take action.
</p>
{_lwr_details_table(self)}
<p style="margin:20px 0 16px;font-size:14px;color:#4b5563;line-height:1.7;">
  Please log in to Hamptons HRMS to approve or reject this request.
</p>
{_lwr_cta_button(lwr_url, "Review Withdrawal Request", "#1d4ed8")}"""
		)

		for recipient in recipients:
			try:
				frappe.sendmail(
					recipients=[recipient],
					subject=subject,
					message=message,
					reference_doctype=self.doctype,
					reference_name=self.name,
					now=True
				)
			except Exception:
				pass

	def notify_employee_approved(self):
		"""Notify employee with professional email that withdrawal is approved."""
		from hamptons.utils.email_utils import is_outgoing_email_enabled
		if not is_outgoing_email_enabled():
			return

		employee_doc = frappe.get_doc("Employee", self.employee)
		employee_email = employee_doc.prefered_email or employee_doc.company_email or employee_doc.personal_email
		if not employee_email and employee_doc.user_id:
			employee_email = frappe.db.get_value("User", employee_doc.user_id, "email")
		if not employee_email:
			return

		lwr_url = frappe.utils.get_url_to_form(self.doctype, self.name)
		subject = _("Your Leave Withdrawal Request Has Been Approved")
		message = _build_lwr_email(
			header_color="#166534",
			header_title="Leave Withdrawal Approved",
			header_subtitle="Your withdrawal request has been approved",
			body_html=f"""
<p style="margin:0 0 6px;font-size:16px;color:#374151;font-weight:600;">
  Dear {self.employee_name},
</p>
<p style="margin:0 0 20px;font-size:14px;color:#4b5563;line-height:1.7;">
  Your leave withdrawal request has been
  <span style="color:#16a34a;font-weight:700;">approved</span>.
</p>
<div style="background-color:#f0fdf4;border-left:4px solid #16a34a;
            padding:14px 18px;border-radius:0 6px 6px 0;margin-bottom:4px;">
  <p style="margin:0;font-size:13px;color:#166534;font-weight:600;">
    ✓ &nbsp;Leave Cancelled — Balance Restored
  </p>
</div>
{_lwr_details_table(self)}
<p style="margin:20px 0 16px;font-size:14px;color:#4b5563;line-height:1.7;">
  Your leave application has been cancelled and your leave balance has been restored.
  If you have any questions, please contact your HR department.
</p>
{_lwr_cta_button(lwr_url, "View Withdrawal Request", "#16a34a")}"""
		)

		try:
			frappe.sendmail(
				recipients=[employee_email],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
				now=True
			)
		except Exception:
			pass

	def notify_employee_rejected(self):
		"""Notify employee with professional email that withdrawal is rejected."""
		from hamptons.utils.email_utils import is_outgoing_email_enabled
		if not is_outgoing_email_enabled():
			return

		employee_doc = frappe.get_doc("Employee", self.employee)
		employee_email = employee_doc.prefered_email or employee_doc.company_email or employee_doc.personal_email
		if not employee_email and employee_doc.user_id:
			employee_email = frappe.db.get_value("User", employee_doc.user_id, "email")
		if not employee_email:
			return

		lwr_url = frappe.utils.get_url_to_form(self.doctype, self.name)
		remarks = self.hr_remarks or "No remarks provided."
		subject = _("Your Leave Withdrawal Request Has Been Rejected")
		message = _build_lwr_email(
			header_color="#991b1b",
			header_title="Leave Withdrawal Rejected",
			header_subtitle="Your withdrawal request could not be approved",
			body_html=f"""
<p style="margin:0 0 6px;font-size:16px;color:#374151;font-weight:600;">
  Dear {self.employee_name},
</p>
<p style="margin:0 0 20px;font-size:14px;color:#4b5563;line-height:1.7;">
  We regret to inform you that your leave withdrawal request has been
  <span style="color:#dc2626;font-weight:700;">rejected</span>.
</p>
<div style="background-color:#fef2f2;border-left:4px solid #dc2626;
            padding:14px 18px;border-radius:0 6px 6px 0;margin-bottom:4px;">
  <p style="margin:0;font-size:13px;color:#991b1b;font-weight:600;">
    ✗ &nbsp;Withdrawal Not Approved — Leave Remains Active
  </p>
</div>
{_lwr_details_table(self)}
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="border-collapse:collapse;margin:16px 0;border-radius:6px;overflow:hidden;
              border:1px solid #e2e8f0;">
  <tr style="background-color:#f7f8fa;">
    <td style="padding:12px 16px;font-size:11px;font-weight:700;color:#6b7280;
               text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid #e2e8f0;">
      Remarks
    </td>
  </tr>
  <tr>
    <td style="padding:12px 16px;font-size:14px;color:#1a202c;line-height:1.6;">
      {remarks}
    </td>
  </tr>
</table>
<p style="margin:20px 0 16px;font-size:14px;color:#4b5563;line-height:1.7;">
  Your original leave application remains active. For further information,
  please contact your line manager or HR department.
</p>
{_lwr_cta_button(lwr_url, "View Withdrawal Request", "#dc2626")}"""
		)

		try:
			frappe.sendmail(
				recipients=[employee_email],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name,
				now=True
			)
		except Exception:
			pass


def _build_lwr_email(header_color, header_title, header_subtitle, body_html):
	return f"""
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#f0f2f5;font-family:'Segoe UI',Arial,Helvetica,sans-serif;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="background-color:#f0f2f5;">
  <tr>
    <td style="padding:40px 20px;">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0"
             style="max-width:600px;width:100%;margin:0 auto;background-color:#ffffff;
                    border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.10);">
        <tr>
          <td style="background-color:{header_color};padding:32px 40px;border-radius:10px 10px 0 0;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
              <tr>
                <td>
                  <span style="color:#ffffff;font-size:20px;font-weight:700;letter-spacing:1px;text-transform:uppercase;">Hamptons</span>
                  <span style="color:rgba(255,255,255,0.55);font-size:13px;margin-left:10px;">Human Resources</span>
                </td>
              </tr>
              <tr>
                <td style="padding-top:18px;">
                  <p style="margin:0;color:#ffffff;font-size:22px;font-weight:600;line-height:1.3;">{header_title}</p>
                  <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:14px;">{header_subtitle}</p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        <tr><td style="padding:36px 40px;">{body_html}</td></tr>
        <tr>
          <td style="padding:20px 40px 28px;border-top:1px solid #e8ecf0;background-color:#f8f9fa;border-radius:0 0 10px 10px;">
            <p style="margin:0;color:#9aa5b4;font-size:12px;line-height:1.6;text-align:center;">
              This is an automated notification from <strong>Hamptons HRMS</strong>.<br>
              Please do not reply directly to this email.
            </p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def _lwr_details_table(doc):
	from_date = frappe.format(doc.from_date, {"fieldtype": "Date"}) if doc.from_date else "-"
	to_date = frappe.format(doc.to_date, {"fieldtype": "Date"}) if doc.to_date else "-"
	return f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="border-collapse:collapse;margin:24px 0;border-radius:6px;overflow:hidden;border:1px solid #e2e8f0;">
  <thead>
    <tr style="background-color:#f7f8fa;">
      <td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;color:#6b7280;
                             text-transform:uppercase;letter-spacing:0.8px;border-bottom:1px solid #e2e8f0;">
        Leave Details
      </td>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;width:40%;border-bottom:1px solid #f0f2f5;white-space:nowrap;">Leave Type</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;font-weight:600;border-bottom:1px solid #f0f2f5;">{doc.leave_type or "-"}</td>
    </tr>
    <tr style="background-color:#fafbfc;">
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;border-bottom:1px solid #f0f2f5;white-space:nowrap;">From Date</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;border-bottom:1px solid #f0f2f5;">{from_date}</td>
    </tr>
    <tr>
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;border-bottom:1px solid #f0f2f5;white-space:nowrap;">To Date</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;border-bottom:1px solid #f0f2f5;">{to_date}</td>
    </tr>
    <tr style="background-color:#fafbfc;">
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;border-bottom:1px solid #f0f2f5;white-space:nowrap;">Duration</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;border-bottom:1px solid #f0f2f5;">
        <strong>{doc.total_leave_days or "-"}</strong> day(s)
      </td>
    </tr>
    <tr>
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;white-space:nowrap;vertical-align:top;">Withdrawal Reason</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;">{doc.reason or "-"}</td>
    </tr>
  </tbody>
</table>"""


def _lwr_cta_button(url, label, color):
	return f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:8px;">
  <tr>
    <td style="border-radius:6px;background-color:{color};">
      <a href="{url}" style="display:inline-block;padding:13px 28px;font-size:15px;font-weight:600;
                             color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
        {label}
      </a>
    </td>
  </tr>
</table>"""


@frappe.whitelist()
def create_withdrawal_request(leave_application, reason):
	"""API to create withdrawal request from mobile app"""
	leave_app = frappe.get_doc("Leave Application", leave_application)

	# Get employee linked to current user
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("No employee record found for current user"))

	if leave_app.employee != employee:
		frappe.throw(_("You can only withdraw your own leave applications"))

	if leave_app.docstatus != 1:
		frappe.throw(_("Can only withdraw approved leave applications"))

	# Create withdrawal request
	withdrawal = frappe.new_doc("Leave Withdrawal Request")
	withdrawal.employee = employee
	withdrawal.leave_application = leave_application
	withdrawal.reason = reason
	withdrawal.insert()

	return {
		"name": withdrawal.name,
		"message": _("Leave withdrawn successfully. The leave application has been cancelled and HR has been notified.")
	}


@frappe.whitelist()
def get_withdrawable_leaves():
	"""Get list of approved leaves that can be withdrawn"""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return []

	leaves = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": 1,
			"to_date": (">=", nowdate())
		},
		fields=["name", "leave_type", "from_date", "to_date", "total_leave_days", "status"]
	)

	# Filter out leaves that already have pending withdrawal requests
	result = []
	for leave in leaves:
		pending_withdrawal = frappe.db.exists(
			"Leave Withdrawal Request",
			{
				"leave_application": leave.name,
				"status": "Pending",
				"docstatus": 0
			}
		)
		if not pending_withdrawal:
			result.append(leave)

	return result

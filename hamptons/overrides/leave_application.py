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


@frappe.whitelist()
def get_leave_balance_map_annual_only():
	"""Mobile app leave balance map - only returns Annual Leave."""
	from hrms.api import get_leave_balance_map
	full_map = get_leave_balance_map()
	return {k: v for k, v in full_map.items() if k == "Annual Leave"}


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
	- Sick Leave requires attachment (medical certificate) on every save (except first save)
	- Annual Leave: show warning for short notice
	"""
	# Sick Leave: require medical certificate (Attach field or sidebar attachment)
	if doc.leave_type == "Sick Leave":
		has_attach_field = bool(doc.custom_medical_certificate)
		has_sidebar_attachment = False
		if not doc.is_new():
			has_sidebar_attachment = bool(frappe.get_all("File", filters={
				"attached_to_doctype": "Leave Application",
				"attached_to_name": doc.name
			}, limit=1))

		if not has_attach_field and not has_sidebar_attachment:
			frappe.throw(
				_("Please upload a medical certificate before saving a Sick Leave application."),
				title=_("Medical Certificate Required")
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


def _build_email(header_color, header_title, header_subtitle, body_html, footer_note=""):
	"""Wrap content in a professional Hamptons-branded email shell."""
	return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f0f2f5;font-family:'Segoe UI',Arial,Helvetica,sans-serif;">
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="background-color:#f0f2f5;">
  <tr>
    <td style="padding:40px 20px;">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0"
             style="max-width:600px;width:100%;margin:0 auto;background-color:#ffffff;
                    border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,0.10);">

        <!-- Header -->
        <tr>
          <td style="background-color:{header_color};padding:32px 40px;
                     border-radius:10px 10px 0 0;">
            <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
              <tr>
                <td>
                  <span style="color:#ffffff;font-size:20px;font-weight:700;
                               letter-spacing:1px;text-transform:uppercase;">
                    Hamptons
                  </span>
                  <span style="color:rgba(255,255,255,0.55);font-size:13px;
                               margin-left:10px;font-weight:400;">
                    Human Resources
                  </span>
                </td>
              </tr>
              <tr>
                <td style="padding-top:18px;">
                  <p style="margin:0;color:#ffffff;font-size:22px;font-weight:600;
                             line-height:1.3;">
                    {header_title}
                  </p>
                  <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:14px;">
                    {header_subtitle}
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:36px 40px;">
            {body_html}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 40px 28px;border-top:1px solid #e8ecf0;
                     background-color:#f8f9fa;border-radius:0 0 10px 10px;">
            <p style="margin:0;color:#9aa5b4;font-size:12px;line-height:1.6;text-align:center;">
              This is an automated notification from <strong>Hamptons HRMS</strong>.<br>
              Please do not reply directly to this email.
              {'<br>' + footer_note if footer_note else ''}
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>
</body>
</html>"""


def _leave_details_table(context):
	"""Return a styled details table for leave application emails."""
	return f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="border-collapse:collapse;margin:24px 0;border-radius:6px;overflow:hidden;
              border:1px solid #e2e8f0;">
  <thead>
    <tr style="background-color:#f7f8fa;">
      <td colspan="2" style="padding:12px 16px;font-size:11px;font-weight:700;
                             color:#6b7280;text-transform:uppercase;letter-spacing:0.8px;
                             border-bottom:1px solid #e2e8f0;">
        Leave Details
      </td>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;width:40%;
                 border-bottom:1px solid #f0f2f5;white-space:nowrap;">Leave Type</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;font-weight:600;
                 border-bottom:1px solid #f0f2f5;">{context['leave_type']}</td>
    </tr>
    <tr style="background-color:#fafbfc;">
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;
                 border-bottom:1px solid #f0f2f5;white-space:nowrap;">From Date</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;
                 border-bottom:1px solid #f0f2f5;">{context['from_date']}</td>
    </tr>
    <tr>
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;
                 border-bottom:1px solid #f0f2f5;white-space:nowrap;">To Date</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;
                 border-bottom:1px solid #f0f2f5;">{context['to_date']}</td>
    </tr>
    <tr style="background-color:#fafbfc;">
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;
                 border-bottom:1px solid #f0f2f5;white-space:nowrap;">Duration</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;
                 border-bottom:1px solid #f0f2f5;">
        <strong>{context['total_days']}</strong> day(s)
      </td>
    </tr>
    <tr>
      <td style="padding:12px 16px;font-size:14px;color:#6b7280;white-space:nowrap;
                 vertical-align:top;">Reason</td>
      <td style="padding:12px 16px;font-size:14px;color:#1a202c;">{context['reason']}</td>
    </tr>
  </tbody>
</table>"""


def _cta_button(url, label, color):
	"""Return a styled CTA button."""
	return f"""
<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:8px;">
  <tr>
    <td style="border-radius:6px;background-color:{color};">
      <a href="{url}"
         style="display:inline-block;padding:13px 28px;font-size:15px;font-weight:600;
                color:#ffffff;text-decoration:none;letter-spacing:0.3px;">
        {label}
      </a>
    </td>
  </tr>
</table>"""


def _get_notification_content(notification_type, context):
	"""Return (subject, html_message) for the given notification type."""
	leave_url = context.get("leave_url", "#")
	emp_name = context["employee_name"]
	emp_id = context["employee_id"]
	details = _leave_details_table(context)

	if notification_type == "pending_approval":
		subject = _("Leave Request Pending Your Approval — {0}").format(emp_name)
		body = f"""
<p style="margin:0 0 6px;font-size:16px;color:#374151;font-weight:600;">
  Dear HOD,
</p>
<p style="margin:0 0 20px;font-size:14px;color:#4b5563;line-height:1.7;">
  <strong>{emp_name}</strong>
  <span style="color:#6b7280;font-size:13px;"> ({emp_id})</span>
  has submitted a leave application that requires your review and approval.
</p>
{details}
<p style="margin:20px 0 16px;font-size:14px;color:#4b5563;line-height:1.7;">
  Please log in to Hamptons HRMS to review the request and take action.
</p>
{_cta_button(leave_url, "Review Leave Application", "#1d4ed8")}"""
		message = _build_email(
			header_color="#1e3a5f",
			header_title="Leave Application — Action Required",
			header_subtitle=f"Submitted by {emp_name} ({emp_id})",
			body_html=body
		)

	elif notification_type == "approved":
		subject = _("Your Leave Application Has Been Approved")
		body = f"""
<p style="margin:0 0 6px;font-size:16px;color:#374151;font-weight:600;">
  Dear {emp_name},
</p>
<p style="margin:0 0 20px;font-size:14px;color:#4b5563;line-height:1.7;">
  We are pleased to inform you that your leave application has been
  <span style="color:#16a34a;font-weight:700;">approved</span>.
</p>
<div style="background-color:#f0fdf4;border-left:4px solid #16a34a;
            padding:14px 18px;border-radius:0 6px 6px 0;margin-bottom:4px;">
  <p style="margin:0;font-size:13px;color:#166534;font-weight:600;">
    ✓ &nbsp;Leave Approved
  </p>
</div>
{details}
<p style="margin:20px 0 16px;font-size:14px;color:#4b5563;line-height:1.7;">
  Your leave has been recorded in the system. If you have any questions,
  please contact your HR department.
</p>
{_cta_button(leave_url, "View Leave Application", "#16a34a")}"""
		message = _build_email(
			header_color="#166534",
			header_title="Leave Application Approved",
			header_subtitle="Your leave request has been approved",
			body_html=body
		)

	elif notification_type == "rejected":
		subject = _("Your Leave Application Has Been Rejected")
		body = f"""
<p style="margin:0 0 6px;font-size:16px;color:#374151;font-weight:600;">
  Dear {emp_name},
</p>
<p style="margin:0 0 20px;font-size:14px;color:#4b5563;line-height:1.7;">
  We regret to inform you that your leave application has been
  <span style="color:#dc2626;font-weight:700;">rejected</span>.
</p>
<div style="background-color:#fef2f2;border-left:4px solid #dc2626;
            padding:14px 18px;border-radius:0 6px 6px 0;margin-bottom:4px;">
  <p style="margin:0;font-size:13px;color:#991b1b;font-weight:600;">
    ✗ &nbsp;Leave Not Approved
  </p>
</div>
{details}
<p style="margin:20px 0 16px;font-size:14px;color:#4b5563;line-height:1.7;">
  For further information or to discuss this decision, please contact
  your line manager or HR department.
</p>
{_cta_button(leave_url, "View Leave Application", "#dc2626")}"""
		message = _build_email(
			header_color="#991b1b",
			header_title="Leave Application Rejected",
			header_subtitle="Your leave request could not be approved",
			body_html=body
		)

	else:
		subject = _("Leave Application Update — {0}").format(emp_name)
		body = f"""
<p style="margin:0 0 16px;font-size:14px;color:#4b5563;line-height:1.7;">
  Your leave application status has been updated to
  <strong>{context['workflow_state']}</strong>.
</p>
{details}
{_cta_button(leave_url, "View Leave Application", "#1d4ed8")}"""
		message = _build_email(
			header_color="#1e3a5f",
			header_title="Leave Application Update",
			header_subtitle=f"Status: {context['workflow_state']}",
			body_html=body
		)

	return subject, message


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

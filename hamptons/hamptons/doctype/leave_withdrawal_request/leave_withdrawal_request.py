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
		"""When HR approves the withdrawal"""
		if self.status == "Approved":
			self.cancel_leave_application()
			self.processed_by = frappe.session.user
			self.processed_on = now_datetime()
			frappe.db.set_value("Leave Withdrawal Request", self.name, {
				"processed_by": self.processed_by,
				"processed_on": self.processed_on
			})
			self.notify_employee_approved()
		elif self.status == "Rejected":
			self.processed_by = frappe.session.user
			self.processed_on = now_datetime()
			frappe.db.set_value("Leave Withdrawal Request", self.name, {
				"processed_by": self.processed_by,
				"processed_on": self.processed_on
			})
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

		# Always update workflow_state to "Cancelled" so the indicator shows correctly
		# (the workflow overrides the indicator based on workflow_state, not docstatus)
		try:
			frappe.db.set_value("Leave Application", self.leave_application, "workflow_state", "Cancelled")
			frappe.db.commit()
		except Exception:
			pass

		frappe.msgprint(_("Leave Application {0} has been cancelled").format(self.leave_application))

	def after_insert(self):
		"""Notify HR about the new withdrawal request pending review"""
		self.notify_hr()

	def notify_hr(self):
		"""Send notification to HR about leave withdrawal"""
		# Get HR Manager users
		hr_users = frappe.get_all(
			"Has Role",
			filters={"role": ["in", ["HR Manager", "HR User"]], "parenttype": "User"},
			fields=["parent"],
			distinct=True
		)

		if not hr_users:
			return

		# Filter out system users and invalid email addresses
		valid_hr_users = []
		for hr_user in hr_users:
			user_email = hr_user.parent
			# Skip system users and non-email usernames
			if user_email in ["Administrator", "Guest"] or "@" not in user_email:
				continue
			# Check if user is enabled
			if frappe.db.get_value("User", user_email, "enabled"):
				valid_hr_users.append(hr_user)

		if not valid_hr_users:
			return

		subject = _("Leave Withdrawn by {0}").format(self.employee_name)
		message = _("""
			<p>Employee <b>{employee_name}</b> ({employee}) has withdrawn their leave.</p>
			<p><b>Leave Details:</b></p>
			<ul>
				<li>Leave Type: {leave_type}</li>
				<li>From: {from_date}</li>
				<li>To: {to_date}</li>
				<li>Days: {total_leave_days}</li>
			</ul>
			<p><b>Reason for Withdrawal:</b></p>
			<p>{reason}</p>
			<p>The leave application <b>{leave_application}</b> has been cancelled and leave balance restored.</p>
			<p><a href="/app/leave-withdrawal-request/{name}">View Details</a></p>
		""").format(
			employee_name=self.employee_name,
			employee=self.employee,
			leave_type=self.leave_type,
			from_date=self.from_date,
			to_date=self.to_date,
			total_leave_days=self.total_leave_days,
			reason=self.reason,
			leave_application=self.leave_application,
			name=self.name
		)

		# Check if outgoing email is enabled before sending
		from hamptons.utils.email_utils import is_outgoing_email_enabled
		if is_outgoing_email_enabled():
			for hr_user in valid_hr_users:
				try:
					frappe.sendmail(
						recipients=[hr_user.parent],
						subject=subject,
						message=message,
						reference_doctype=self.doctype,
						reference_name=self.name
					)
				except Exception:
					pass  # Continue even if email fails

		# Create notification in system
		for hr_user in valid_hr_users:
			try:
				notification = frappe.new_doc("Notification Log")
				notification.subject = subject
				notification.for_user = hr_user.parent
				notification.type = "Alert"
				notification.document_type = self.doctype
				notification.document_name = self.name
				notification.email_content = message
				notification.insert(ignore_permissions=True)
			except Exception:
				pass

	def notify_employee_approved(self):
		"""Notify employee that withdrawal is approved"""
		# Check if outgoing email is enabled
		from hamptons.utils.email_utils import is_outgoing_email_enabled
		if not is_outgoing_email_enabled():
			return

		employee_user = frappe.db.get_value("Employee", self.employee, "user_id")
		if not employee_user:
			return

		subject = _("Leave Withdrawal Approved")
		message = _("""
			<p>Your leave withdrawal request has been <b style="color:green;">Approved</b>.</p>
			<p><b>Leave Details:</b></p>
			<ul>
				<li>Leave Type: {leave_type}</li>
				<li>From: {from_date}</li>
				<li>To: {to_date}</li>
			</ul>
			<p>The leave application has been cancelled and leave balance restored.</p>
		""").format(
			leave_type=self.leave_type,
			from_date=self.from_date,
			to_date=self.to_date
		)

		try:
			frappe.sendmail(
				recipients=[employee_user],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name
			)
		except Exception:
			pass

	def notify_employee_rejected(self):
		"""Notify employee that withdrawal is rejected"""
		# Check if outgoing email is enabled
		from hamptons.utils.email_utils import is_outgoing_email_enabled
		if not is_outgoing_email_enabled():
			return

		employee_user = frappe.db.get_value("Employee", self.employee, "user_id")
		if not employee_user:
			return

		subject = _("Leave Withdrawal Rejected")
		message = _("""
			<p>Your leave withdrawal request has been <b style="color:red;">Rejected</b>.</p>
			<p><b>Leave Details:</b></p>
			<ul>
				<li>Leave Type: {leave_type}</li>
				<li>From: {from_date}</li>
				<li>To: {to_date}</li>
			</ul>
			<p><b>HR Remarks:</b> {remarks}</p>
		""").format(
			leave_type=self.leave_type,
			from_date=self.from_date,
			to_date=self.to_date,
			remarks=self.hr_remarks or "No remarks"
		)

		try:
			frappe.sendmail(
				recipients=[employee_user],
				subject=subject,
				message=message,
				reference_doctype=self.doctype,
				reference_name=self.name
			)
		except Exception:
			pass


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

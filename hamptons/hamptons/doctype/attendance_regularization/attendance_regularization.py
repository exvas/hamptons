# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AttendanceRegularization(Document):
	def validate(self):
		"""Auto-approve or reject based on status field"""
		# Only auto-process if status changed and doc is draft
		if self.docstatus != 0:
			return

		# Check if status was changed in this save
		if self.has_value_changed("status"):
			old_status = self.get_doc_before_save().status if self.get_doc_before_save() else None

			# Auto-approve if manually changed to Approved
			if self.status == "Approved" and old_status != "Approved":
				# Set flag to trigger approval after save
				self._needs_auto_approval = True

			# Auto-reject if manually changed to Rejected
			elif self.status == "Rejected" and old_status != "Rejected":
				# Set flag to trigger rejection after save
				self._needs_auto_rejection = True

	def on_update(self):
		"""Handle auto-approval/rejection after save"""
		if getattr(self, '_needs_auto_approval', False):
			frappe.enqueue(
				'hamptons.hamptons.doctype.attendance_regularization.attendance_regularization.auto_approve_regularization',
				queue='short',
				timeout=300,
				regularization_name=self.name,
				now=frappe.flags.in_test
			)
		elif getattr(self, '_needs_auto_rejection', False):
			frappe.enqueue(
				'hamptons.hamptons.doctype.attendance_regularization.attendance_regularization.auto_reject_regularization',
				queue='short',
				timeout=300,
				regularization_name=self.name,
				now=frappe.flags.in_test
			)

	@frappe.whitelist()
	def approve(self):
		"""Approve the regularization request - update Absent to Present or create Present attendance"""
		if self.status not in ("Pending", "Approved"):
			frappe.throw(_("Only Pending or Approved requests can be approved"))

		if self.docstatus != 0:
			frappe.throw(_("Only draft documents can be approved"))

		if not self.shift:
			frappe.throw(_("Shift Type is required to approve Attendance Regularization"))

		attendance_date = getdate(self.posting_date)

		try:
			# Check if attendance already exists (e.g. Absent from single-checkin consolidation)
			existing_attendance = frappe.db.exists(
				"Attendance",
				{
					"employee": self.employee,
					"attendance_date": attendance_date,
					"docstatus": 1
				}
			)

			if existing_attendance:
				# Update existing Absent attendance to Present
				att_doc = frappe.get_doc("Attendance", existing_attendance)
				if att_doc.status == "Absent":
					frappe.db.sql("""
						UPDATE `tabAttendance`
						SET status = 'Present', custom_attendance_regularization = %s
						WHERE name = %s
					""", (self.name, existing_attendance))

				self.status = "Approved"
				self.attendance = existing_attendance
				self.submit()
				frappe.db.commit()

				frappe.msgprint(
					_("Attendance Regularization approved. Attendance {0} updated to Present").format(
						frappe.utils.get_link_to_form("Attendance", existing_attendance)
					),
					indicator="green"
				)
			else:
				# No existing attendance - create new Present attendance
				attendance = frappe.get_doc({
					"doctype": "Attendance",
					"employee": self.employee,
					"employee_name": self.employee_name,
					"attendance_date": attendance_date,
					"shift": self.shift,
					"status": "Present",
					"custom_attendance_regularization": self.name,
					"company": frappe.defaults.get_user_default("Company")
				})
				attendance.insert(ignore_permissions=True)
				attendance.submit()

				self.status = "Approved"
				self.attendance = attendance.name
				self.submit()
				frappe.db.commit()

				frappe.msgprint(
					_("Attendance Regularization approved. Attendance {0} created as Present").format(
						frappe.utils.get_link_to_form("Attendance", attendance.name)
					),
					indicator="green"
				)

		except Exception as e:
			frappe.log_error(
				message=str(e),
				title=f"Attendance Approval Failed - {self.name}"
			)
			frappe.throw(_("Failed to approve attendance: {0}").format(str(e)))
	
	@frappe.whitelist()
	def reject(self):
		"""Reject the regularization request - keep Absent or create Absent attendance"""
		if self.status not in ("Pending", "Rejected"):
			frappe.throw(_("Only Pending or Rejected requests can be rejected"))

		if self.docstatus != 0:
			frappe.throw(_("Only draft documents can be rejected"))

		if not self.shift:
			frappe.throw(_("Shift Type is required to reject Attendance Regularization"))

		attendance_date = getdate(self.posting_date)

		try:
			# Check if attendance already exists (e.g. Absent from single-checkin consolidation)
			existing_attendance = frappe.db.exists(
				"Attendance",
				{
					"employee": self.employee,
					"attendance_date": attendance_date,
					"docstatus": 1
				}
			)

			if existing_attendance:
				# Absent attendance already exists - just link and submit AR
				frappe.db.sql("""
					UPDATE `tabAttendance`
					SET custom_attendance_regularization = %s
					WHERE name = %s
				""", (self.name, existing_attendance))

				self.status = "Rejected"
				self.attendance = existing_attendance
				self.submit()
				frappe.db.commit()

				frappe.msgprint(
					_("Attendance Regularization rejected. Attendance {0} remains Absent").format(
						frappe.utils.get_link_to_form("Attendance", existing_attendance)
					),
					indicator="orange"
				)
			else:
				# No existing attendance - create new Absent attendance
				attendance = frappe.get_doc({
					"doctype": "Attendance",
					"employee": self.employee,
					"employee_name": self.employee_name,
					"attendance_date": attendance_date,
					"shift": self.shift,
					"status": "Absent",
					"custom_attendance_regularization": self.name,
					"company": frappe.defaults.get_user_default("Company")
				})
				attendance.insert(ignore_permissions=True)
				attendance.submit()

				self.status = "Rejected"
				self.attendance = attendance.name
				self.submit()
				frappe.db.commit()

				frappe.msgprint(
					_("Attendance Regularization rejected. Attendance {0} marked as Absent").format(
						frappe.utils.get_link_to_form("Attendance", attendance.name)
					),
					indicator="orange"
				)

		except Exception as e:
			frappe.log_error(
				message=str(e),
				title=f"Attendance Rejection Failed - {self.name}"
			)
			frappe.throw(_("Failed to reject attendance: {0}").format(str(e)))
	
	def on_cancel(self):
		"""Handle cancellation of Attendance Regularization and cancel all linked attendance records"""
		cancelled_count = 0
		failed_list = []
		
		# Find all attendance records linked to this regularization
		linked_attendance = frappe.get_all(
			"Attendance",
			filters={
				"custom_attendance_regularization": self.name,
				"docstatus": 1  # Only submitted records
			},
			pluck="name"
		)
		
		# Cancel all linked attendance records
		for attendance_name in linked_attendance:
			try:
				attendance_doc = frappe.get_doc("Attendance", attendance_name)
				attendance_doc.cancel()
				cancelled_count += 1
			except Exception as e:
				failed_list.append(attendance_name)
				frappe.log_error(
					message=str(e),
					title=f"Failed to cancel Attendance {attendance_name} - {self.name}"
				)
		
		# Show summary message
		if cancelled_count > 0:
			frappe.msgprint(
				_("Successfully cancelled {0} linked Attendance record(s)").format(cancelled_count),
				indicator="green"
			)
		
		if failed_list:
			frappe.msgprint(
				_("Failed to cancel {0} Attendance record(s): {1}").format(len(failed_list), ", ".join(failed_list)),
				indicator="orange"
			)
	
	def on_trash(self):
		"""Prevent deletion if submitted and not cancelled"""
		# Allow deletion only if document is Draft (docstatus=0) or Cancelled (docstatus=2)
		if self.docstatus == 1:  # Submitted
			frappe.throw(
				_("Cannot delete submitted Attendance Regularization. Please cancel it first.")
			)

		# If cancelled, check and warn about linked attendance
		if self.docstatus == 2 and self.attendance:
			try:
				attendance_doc = frappe.get_doc("Attendance", self.attendance)
				if attendance_doc.docstatus == 1:  # Still submitted
					frappe.throw(
						_("Cannot delete because linked Attendance {0} is still active. Please cancel it first.").format(self.attendance)
					)
			except frappe.DoesNotExistError:
				# Attendance already deleted, safe to proceed
				pass

	@frappe.whitelist()
	def fetch_shift_details(self):
		"""
		Fetch shift details for the employee on the posting date.
		This method is called from the client-side to avoid date parsing errors.
		"""
		if not self.employee or not self.posting_date:
			return

		from hamptons.overrides.employee_checkin import get_active_shift_assignment

		shift_assignment = get_active_shift_assignment(self.employee, getdate(self.posting_date))
		if shift_assignment and shift_assignment.shift_type:
			shift_type = frappe.get_doc("Shift Type", shift_assignment.shift_type)
			self.shift = shift_type.name
			self.start_time = shift_type.start_time
			self.end_time = shift_type.end_time
			return True
		return False


def auto_approve_regularization(regularization_name):
	"""
	Background job to auto-approve a regularization.
	Called when status is manually changed to 'Approved'.
	"""
	try:
		doc = frappe.get_doc("Attendance Regularization", regularization_name)

		if doc.docstatus == 0 and doc.status == "Approved":
			attendance_date = getdate(doc.posting_date)

			# Check if attendance already exists (e.g. Absent from single-checkin)
			existing_attendance = frappe.db.exists(
				"Attendance",
				{
					"employee": doc.employee,
					"attendance_date": attendance_date,
					"docstatus": 1
				}
			)

			if existing_attendance:
				# Update existing Absent attendance to Present
				att_doc = frappe.get_doc("Attendance", existing_attendance)
				if att_doc.status == "Absent":
					frappe.db.sql("""
						UPDATE `tabAttendance`
						SET status = 'Present', custom_attendance_regularization = %s
						WHERE name = %s
					""", (doc.name, existing_attendance))

				doc.attendance = existing_attendance
				doc.submit()
				frappe.db.commit()
			else:
				# Create new Present attendance
				attendance = frappe.get_doc({
					"doctype": "Attendance",
					"employee": doc.employee,
					"employee_name": doc.employee_name,
					"attendance_date": attendance_date,
					"shift": doc.shift,
					"status": "Present",
					"custom_attendance_regularization": doc.name,
					"company": frappe.defaults.get_user_default("Company")
				})
				attendance.insert(ignore_permissions=True)
				attendance.submit()

				doc.attendance = attendance.name
				doc.submit()
				frappe.db.commit()

			frappe.logger().info(
				f"Auto-approved regularization {regularization_name}"
			)
	except Exception as e:
		frappe.log_error(
			message=str(e),
			title=f"Auto-Approval Failed - {regularization_name}"
		)


def auto_reject_regularization(regularization_name):
	"""
	Background job to auto-reject a regularization.
	Called when status is manually changed to 'Rejected'.
	"""
	try:
		doc = frappe.get_doc("Attendance Regularization", regularization_name)

		if doc.docstatus == 0 and doc.status == "Rejected":
			attendance_date = getdate(doc.posting_date)

			# Check if Absent attendance already exists (from single-checkin consolidation)
			existing_attendance = frappe.db.exists(
				"Attendance",
				{
					"employee": doc.employee,
					"attendance_date": attendance_date,
					"docstatus": 1
				}
			)

			if existing_attendance:
				# Absent already exists - just link and submit AR
				frappe.db.sql("""
					UPDATE `tabAttendance`
					SET custom_attendance_regularization = %s
					WHERE name = %s
				""", (doc.name, existing_attendance))

				doc.attendance = existing_attendance
				doc.submit()
				frappe.db.commit()
			else:
				# Create new Absent attendance
				attendance = frappe.get_doc({
					"doctype": "Attendance",
					"employee": doc.employee,
					"employee_name": doc.employee_name,
					"attendance_date": attendance_date,
					"shift": doc.shift,
					"status": "Absent",
					"custom_attendance_regularization": doc.name,
					"company": frappe.defaults.get_user_default("Company")
				})
				attendance.insert(ignore_permissions=True)
				attendance.submit()

				doc.attendance = attendance.name
				doc.submit()
				frappe.db.commit()

			frappe.logger().info(
				f"Auto-rejected regularization {regularization_name}"
			)
	except Exception as e:
		frappe.log_error(
			message=str(e),
			title=f"Auto-Rejection Failed - {regularization_name}"
		)
# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AttendanceRegularization(Document):
	@frappe.whitelist()
	def approve(self):
		"""Approve the regularization request and create Present attendance"""
		if self.status != "Pending":
			frappe.throw(_("Only Pending requests can be approved"))
		
		if self.docstatus != 0:
			frappe.throw(_("Only draft documents can be approved"))
		
		if not self.shift:
			frappe.throw(_("Shift Type is required to approve Attendance Regularization"))
		
		attendance_date = getdate(self.posting_date)
		
		# Check if attendance already exists
		existing_attendance = frappe.db.exists(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": attendance_date,
				"docstatus": ["<", 2]
			}
		)
		
		if existing_attendance:
			frappe.throw(
				_("Attendance already exists for {0} on {1}").format(
					self.employee_name,
					frappe.format(attendance_date, {"fieldtype": "Date"})
				)
			)
		
		# Create Present attendance
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
		
		try:
			attendance.insert(ignore_permissions=True)
			attendance.submit()
			
			# Update status to Approved
			self.status = "Approved"
			self.attendance = attendance.name
			
			# Submit the Attendance Regularization document
			self.submit()
			frappe.db.commit()
			
			frappe.msgprint(
				_("Attendance Regularization approved and submitted. Attendance {0} created as Present").format(
					frappe.utils.get_link_to_form("Attendance", attendance.name)
				),
				indicator="green"
			)
			
		except Exception as e:
			frappe.log_error(
				message=str(e),
				title=f"Attendance Creation Failed - {self.name}"
			)
			frappe.throw(_("Failed to create attendance: {0}").format(str(e)))
	
	@frappe.whitelist()
	def reject(self):
		"""Reject the regularization request and create Absent attendance"""
		if self.status != "Pending":
			frappe.throw(_("Only Pending requests can be rejected"))
		
		if self.docstatus != 0:
			frappe.throw(_("Only draft documents can be rejected"))
		
		if not self.shift:
			frappe.throw(_("Shift Type is required to reject Attendance Regularization"))
		
		attendance_date = getdate(self.posting_date)
		
		# Check if attendance already exists
		existing_attendance = frappe.db.exists(
			"Attendance",
			{
				"employee": self.employee,
				"attendance_date": attendance_date,
				"docstatus": ["<", 2]
			}
		)
		
		if existing_attendance:
			frappe.throw(
				_("Attendance already exists for {0} on {1}").format(
					self.employee_name,
					frappe.format(attendance_date, {"fieldtype": "Date"})
				)
			)
		
		# Create Absent attendance
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
		
		try:
			attendance.insert(ignore_permissions=True)
			attendance.submit()
			
			# Update status to Rejected
			self.status = "Rejected"
			self.attendance = attendance.name
			
			# Submit the Attendance Regularization document
			self.submit()
			frappe.db.commit()
			
			frappe.msgprint(
				_("Attendance Regularization rejected and submitted. Attendance {0} marked as Absent").format(
					frappe.utils.get_link_to_form("Attendance", attendance.name)
				),
				indicator="orange"
			)
			
		except Exception as e:
			frappe.log_error(
				message=str(e),
				title=f"Attendance Creation Failed - {self.name}"
			)
			frappe.throw(_("Failed to create attendance: {0}").format(str(e)))
	
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
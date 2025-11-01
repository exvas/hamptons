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
			
			# Update regularization status
			self.db_set("status", "Approved", update_modified=True)
			self.db_set("attendance", attendance.name, update_modified=False)
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
				title=f"Attendance Creation Failed - {self.name}"
			)
			frappe.throw(_("Failed to create attendance: {0}").format(str(e)))
	
	@frappe.whitelist()
	def reject(self):
		"""Reject the regularization request and create Absent attendance"""
		if self.status != "Pending":
			frappe.throw(_("Only Pending requests can be rejected"))
		
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
			
			# Update regularization status
			self.db_set("status", "Rejected", update_modified=True)
			self.db_set("attendance", attendance.name, update_modified=False)
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
				title=f"Attendance Creation Failed - {self.name}"
			)
			frappe.throw(_("Failed to create attendance: {0}").format(str(e)))
	
	def on_trash(self):
		"""Prevent deletion if already approved or rejected"""
		if self.status in ["Approved", "Rejected"]:
			frappe.throw(
				_("Cannot delete {0} Attendance Regularization").format(self.status)
			)
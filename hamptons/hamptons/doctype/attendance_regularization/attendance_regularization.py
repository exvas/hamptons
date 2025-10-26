# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class AttendanceRegularization(Document):
	def on_cancel(self):
		"""Clear links when regularization is cancelled"""
		# Check if linked to submitted attendance
		attendance = frappe.db.sql(
			"""SELECT name FROM `tabAttendance` 
			   WHERE custom_attendance_regularization=%s AND docstatus=1""",
			self.name, as_dict=1
		)
		
		if attendance:
			frappe.throw(
				_("Cannot cancel: Linked to submitted Attendance {0}").format(
					frappe.utils.get_link_to_form("Attendance", attendance[0].name)
				)
			)
		
		# Clear custom_attendance_regularization from all linked checkins
		for item in self.attendance_regularization_item:
			if item.employee_checkin:
				frappe.db.set_value(
					"Employee Checkin",
					item.employee_checkin,
					"custom_attendance_regularization",
					None,
					update_modified=False
				)
		
		frappe.db.commit()
	
	def on_trash(self):
		"""Prevent deletion if linked to submitted attendance"""
		# Check if linked to submitted attendance
		attendance = frappe.db.sql(
			"""SELECT name FROM `tabAttendance` 
			   WHERE custom_attendance_regularization=%s AND docstatus=1""",
			self.name, as_dict=1
		)
		
		if attendance:
			frappe.throw(
				_("Cannot delete: Linked to submitted Attendance {0}").format(
					frappe.utils.get_link_to_form("Attendance", attendance[0].name)
				)
			)
		
		# Clear custom_attendance_regularization from all linked checkins
		for item in self.attendance_regularization_item:
			if item.employee_checkin:
				frappe.db.set_value(
					"Employee Checkin",
					item.employee_checkin,
					"custom_attendance_regularization",
					None,
					update_modified=False
				)
		
		frappe.db.commit()
	@frappe.whitelist()
	def on_submit(self):
		"""Create attendance record when regularization is submitted"""
		if not self.shift:
			frappe.throw(_("Shift Type is required to submit Attendance Regularization"))
		
		# Get shift configuration
		shift = frappe.get_doc("Shift Type", self.shift)
		
		# Use posting_date instead of self.time (which doesn't exist)
		attendance_date = getdate(self.posting_date)
		
		# Check if attendance already exists for this date
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
		
		# Determine attendance status based on late time
		status = "Present"
		late_entry = 0
		leave_type = None
		
		if self.late:
			# Extract hours from late time
			late_hours = int(str(self.late).split(":")[0])
			
			# Check if shift has half-day threshold configured
			half_day_threshold = getattr(shift, "working_hours_threshold_for_half_day", None)
			
			if half_day_threshold and late_hours >= half_day_threshold:
				status = "Half Day"
				# Try to get default leave type for half day from Hamptons Settings or use fallback
				leave_type = frappe.db.get_single_value(
					"HR Settings", "default_leave_type"
				)
			else:
				status = "Present"
				late_entry = 1
		
		# Create attendance record
		attendance = frappe.get_doc({
			"doctype": "Attendance",
			"employee": self.employee,
			"employee_name": self.employee_name,
			"attendance_date": attendance_date,
			"shift": self.shift,
			"status": status,
			"custom_attendance_regularization": self.name,
			"late_entry": late_entry,
			"company": frappe.defaults.get_user_default("Company")
		})
		
		# Add leave type if half day
		if status == "Half Day" and leave_type:
			attendance.leave_type = leave_type
		
		try:
			attendance.insert(ignore_permissions=True)
			attendance.submit()
			
			# Update regularization with attendance reference
			self.db_set("attendance", attendance.name, update_modified=False)
			self.db_set("status", "Completed", update_modified=False)
			
			frappe.db.commit()
			
			frappe.msgprint(
				_("Attendance {0} created successfully").format(
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
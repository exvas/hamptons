# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AttendanceRegularization(Document):
	def on_cancel(self):
		attendance = frappe.db.sql(""" SELECT * FROM `tabAttendance` WHERE custom_attendance_regularization=%s and docstatus=1""",self.name,as_dict=1)
		if len(attendance) > 0:
			message = "Attendance Regularization is linked with attendance <a href='/app/attendance/" + attendance[0].name + "'>" + attendance[0].name + "</a>"
			print(message)
			frappe.throw(message)
		frappe.db.sql(""" UPDATE `tabEmployee Checkin` SET custom_attendance_regularization=%s WHERE name=%s""",
					  ("", self.employee_checkin))
		frappe.db.sql(""" UPDATE `tabAttendance Regularization` SET employee_checkin=%s WHERE name=%s""",
					  ("", self.name))
		frappe.db.commit()
	def on_trash(self):
		attendance = frappe.db.sql(""" SELECT * FROM `tabAttendance` WHERE custom_attendance_regularization=%s and docstatus=1""",self.name,as_dict=1)
		if len(attendance) > 0:
			message = "Attendance Regularization is linked with attendance <a href='/app/attendance/" + attendance[0].name + "'>" + attendance[0].name + "</a>"
			print(message)
			frappe.throw(message)
		frappe.db.sql(""" UPDATE `tabEmployee Checkin` SET custom_attendance_regularization=%s WHERE name=%s""",
					  ("", self.employee_checkin))
		frappe.db.sql(""" UPDATE `tabAttendance Regularization` SET employee_checkin=%s WHERE name=%s""",
					  ("", self.name))
		frappe.db.commit()
	@frappe.whitelist()
	def on_submit(self):
		shift = frappe.get_doc("Shift Type",self.shift)
		default_leave_type_for_half_day = frappe.db.get_single_value("Bios Settings", "default_leave_type_for_half_day")
		leave_type = frappe.db.get_single_value("Bios Settings", "attendance_regularization_leave_type")

		obj = {
			'doctype': "Attendance",
			"employee": self.employee,
			"employee_name":self.employee_name,
			"shift": self.shift,
			"custom_attendance_regularization": self.name,
			"attendance_date": frappe.utils.getdate(self.time),
			"status": "Present" if self.workflow_state == 'Approved' and  int(str(self.late).split(":")[0]) < shift.working_hours_threshold_for_half_day else "Half Day" if self.workflow_state == "Approved" and  int(str(self.late).split(":")[0]) >= shift.working_hours_threshold_for_half_day else "On Leave"
		}
		if obj['status'] == 'On Leave':
			if not leave_type:
				frappe.throw("Please Setup Attendance Regularization Leave Type in Bios Settings first")
			obj['leave_type'] = leave_type
		if self.workflow_state == 'Approved':
			obj["late_entry"] = 1
		if obj['status'] == "Half Day":
			obj['leave_type'] = default_leave_type_for_half_day
		att = frappe.get_doc(obj).insert()
		att.submit()
		frappe.db.commit()
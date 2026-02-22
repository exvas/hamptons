"""
One-time patch: Fix Attendance records that were approved via
Attendance Regularization but left with working_hours=0 and missing out_time.

This happens because the old approve() logic only set status='Present' without
updating in_time, out_time, working_hours, late_entry, early_exit.
"""

import frappe
from frappe.utils import time_diff_in_hours, getdate


def execute():
	# 1. Fix submitted ARs where linked Attendance has working_hours=0
	approved_ars = frappe.db.sql("""
		SELECT
			ar.name as ar_name,
			ar.attendance,
			ar.shift,
			ar.posting_date,
			a.in_time as att_in_time,
			a.out_time as att_out_time,
			a.working_hours
		FROM `tabAttendance Regularization` ar
		INNER JOIN `tabAttendance` a ON ar.attendance = a.name
		WHERE ar.docstatus = 1
		AND ar.status = 'Approved'
		AND a.docstatus = 1
		AND a.status = 'Present'
		AND (a.working_hours IS NULL OR a.working_hours = 0)
	""", as_dict=True)

	fixed_count = 0
	error_count = 0

	for ar_data in approved_ars:
		try:
			items = frappe.db.sql("""
				SELECT time, log_type
				FROM `tabAttendance Regularization Item`
				WHERE parent = %s
				ORDER BY time
			""", (ar_data['ar_name'],), as_dict=True)

			if not items:
				continue

			first_in_time = items[0].time
			last_out_time = items[-1].time if len(items) > 1 else None

			update_parts = []
			update_params = []

			if first_in_time and not ar_data.get('att_in_time'):
				update_parts.append("in_time = %s")
				update_params.append(first_in_time)

			if last_out_time and not ar_data.get('att_out_time'):
				update_parts.append("out_time = %s")
				update_params.append(last_out_time)

			if first_in_time and last_out_time:
				wh = time_diff_in_hours(last_out_time, first_in_time)
				update_parts.append("working_hours = %s")
				update_params.append(round(wh, 2))

				if ar_data.get('shift'):
					try:
						from hamptons.overrides.attendance_utils import calculate_late_early_times
						shift_type = frappe.get_doc("Shift Type", ar_data['shift'])
						late_early = calculate_late_early_times(
							first_in_time,
							last_out_time,
							shift_type,
							getdate(ar_data['posting_date'])
						)
						update_parts.append("late_entry = %s")
						update_params.append(1 if late_early.get('late_time') else 0)
						update_parts.append("early_exit = %s")
						update_params.append(1 if late_early.get('early_exit_time') else 0)
					except Exception:
						pass

			if update_parts:
				update_params.append(ar_data['attendance'])
				frappe.db.sql(
					f"UPDATE `tabAttendance` SET {', '.join(update_parts)} WHERE name = %s",
					tuple(update_params)
				)
				fixed_count += 1

		except Exception as e:
			frappe.log_error(
				message=str(e),
				title=f"Patch: Fix AR Attendance Fields - {ar_data['ar_name']}"
			)
			error_count += 1

	# 2. Fix submitted ARs that were never linked to their Attendance
	unlinked_ars = frappe.db.sql("""
		SELECT
			ar.name as ar_name,
			ar.employee,
			ar.posting_date
		FROM `tabAttendance Regularization` ar
		WHERE ar.docstatus = 1
		AND ar.status = 'Approved'
		AND (ar.attendance IS NULL OR ar.attendance = '')
	""", as_dict=True)

	for ar_data in unlinked_ars:
		try:
			att_name = frappe.db.get_value(
				"Attendance",
				{"employee": ar_data['employee'], "attendance_date": ar_data['posting_date'], "docstatus": 1},
				"name"
			)
			if att_name:
				frappe.db.sql("""
					UPDATE `tabAttendance`
					SET custom_attendance_regularization = %s
					WHERE name = %s AND (custom_attendance_regularization IS NULL OR custom_attendance_regularization = '')
				""", (ar_data['ar_name'], att_name))

				frappe.db.sql("""
					UPDATE `tabAttendance Regularization`
					SET attendance = %s
					WHERE name = %s
				""", (att_name, ar_data['ar_name']))
				fixed_count += 1
		except Exception as e:
			error_count += 1
			frappe.log_error(
				message=str(e),
				title=f"Patch: Link Unlinked AR - {ar_data['ar_name']}"
			)

	if fixed_count > 0:
		frappe.db.commit()

	print(f"Patch complete: Fixed {fixed_count} attendance records, {error_count} errors")

# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime, formatdate, get_time_str


def execute(filters=None):
	"""
	Execute the Employee Checkin Report

	Returns:
		columns: List of column definitions
		data: List of data rows
	"""
	# Check if Attendance Regularization DocType exists on this site
	if not frappe.db.exists("DocType", "Attendance Regularization"):
		frappe.throw(_("Attendance Regularization DocType is not installed on this site"))

	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	"""Define the columns for the report"""
	return [
		{
			"fieldname": "date",
			"label": _("Date"),
			"fieldtype": "Date",
			"width": 120
		},
		{
			"fieldname": "employee",
			"label": _("Employee ID"),
			"fieldtype": "Link",
			"options": "Employee",
			"width": 120
		},
		{
			"fieldname": "employee_name",
			"label": _("Employee Name"),
			"fieldtype": "Data",
			"width": 180
		},
		{
			"fieldname": "department",
			"label": _("Department"),
			"fieldtype": "Link",
			"options": "Department",
			"width": 200
		},
		{
			"fieldname": "designation",
			"label": _("Designation"),
			"fieldtype": "Link",
			"options": "Designation",
			"width": 200
		},
		{
			"fieldname": "shift",
			"label": _("Shift"),
			"fieldtype": "Link",
			"options": "Shift Type",
			"width": 180
		},
		{
			"fieldname": "shift_start",
			"label": _("Shift Start"),
			"fieldtype": "Time",
			"width": 100
		},
		{
			"fieldname": "shift_end",
			"label": _("Shift End"),
			"fieldtype": "Time",
			"width": 100
		},
		{
			"fieldname": "first_in",
			"label": _("First Check-in"),
			"fieldtype": "Datetime",
			"width": 240
		},
		{
			"fieldname": "last_out",
			"label": _("Last Check-out"),
			"fieldtype": "Datetime",
			"width": 240
		},
		{
			"fieldname": "total_checkins",
			"label": _("Total Check-ins"),
			"fieldtype": "Int",
			"width": 140
		},
		{
			"fieldname": "working_hours",
			"label": _("Working Hours"),
			"fieldtype": "Float",
			"width": 140,
			"precision": 2
		},
		{
			"fieldname": "late_by",
			"label": _("Late By"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "early_exit_by",
			"label": _("Early Exit By"),
			"fieldtype": "Data",
			"width": 120
		},
		{
			"fieldname": "device_id",
			"label": _("Device/Location"),
			"fieldtype": "Data",
			"width": 210
		},
		{
			"fieldname": "regularization",
			"label": _("Regularization"),
			"fieldtype": "Link",
			"options": "Attendance Regularization",
			"width": 150
		},
		{
			"fieldname": "regularization_status",
			"label": _("Reg. Status"),
			"fieldtype": "Data",
			"width": 100
		},
		{
			"fieldname": "attendance",
			"label": _("Attendance"),
			"fieldtype": "Link",
			"options": "Attendance",
			"width": 150
		},
		{
			"fieldname": "attendance_status",
			"label": _("Final Status"),
			"fieldtype": "Data",
			"width": 100
		}
	]


def get_data(filters):
	"""Get the data for the report based on filters"""
	conditions = get_conditions(filters)
	
	# Get employee check-ins with aggregated data
	# Fixed: Properly handle single checkin case based on log_type
	# - Single IN checkin: show as first_in only (no last_out)
	# - Single OUT checkin: show as last_out only (no first_in)
	# - Multiple checkins: first IN is first_in, last OUT (or last checkin) is last_out
	data = frappe.db.sql("""
		SELECT
			DATE(ec.time) as date,
			ec.employee,
			ec.employee_name,
			emp.department,
			emp.designation,
			sa.shift_type as shift,
			st.start_time as shift_start,
			st.end_time as shift_end,
			CASE
				-- If there's an actual IN checkin, use the min IN time
				WHEN MAX(CASE WHEN ec.log_type = 'IN' THEN 1 ELSE 0 END) = 1
					THEN MIN(CASE WHEN ec.log_type = 'IN' THEN ec.time ELSE NULL END)
				-- If multiple checkins exist (2+) but no IN type, use the first one as IN
				WHEN COUNT(*) > 1
					THEN MIN(ec.time)
				-- Single checkin with OUT type only = no check-in (NULL)
				ELSE CASE WHEN MIN(ec.log_type) = 'OUT' THEN NULL ELSE MIN(ec.time) END
			END as first_in,
			CASE
				-- If there's an actual OUT checkin, use the max OUT time
				WHEN MAX(CASE WHEN ec.log_type = 'OUT' THEN 1 ELSE 0 END) = 1
					THEN MAX(CASE WHEN ec.log_type = 'OUT' THEN ec.time ELSE NULL END)
				-- If multiple checkins exist (2+), treat the last one as OUT
				WHEN COUNT(*) > 1
					THEN MAX(ec.time)
				-- Single checkin with no OUT type = no checkout (NULL)
				ELSE NULL
			END as last_out,
			COUNT(*) as total_checkins,
			GROUP_CONCAT(DISTINCT ec.device_id ORDER BY ec.time SEPARATOR ', ') as device_id,
			ar.name as regularization,
			ar.status as regularization_status,
			att.name as attendance,
			att.status as attendance_status
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		LEFT JOIN `tabShift Assignment` sa ON sa.employee = ec.employee
			AND sa.docstatus = 1
			AND sa.start_date <= DATE(ec.time)
			AND (sa.end_date IS NULL OR sa.end_date >= DATE(ec.time))
		LEFT JOIN `tabShift Type` st ON st.name = sa.shift_type
		LEFT JOIN `tabAttendance Regularization` ar ON ar.employee = ec.employee
			AND ar.posting_date = DATE(ec.time)
		LEFT JOIN `tabAttendance` att ON att.employee = ec.employee
			AND att.attendance_date = DATE(ec.time)
			AND att.docstatus = 1
		WHERE 1=1 {conditions}
		GROUP BY DATE(ec.time), ec.employee
		ORDER BY DATE(ec.time) DESC, ec.employee_name
	""".format(conditions=conditions), filters, as_dict=1)
	
	# Process the data to calculate working hours and late/early times
	for row in data:
		# Calculate working hours (only if both first_in and last_out exist)
		if row.get('first_in') and row.get('last_out'):
			first_in_dt = get_datetime(row['first_in'])
			last_out_dt = get_datetime(row['last_out'])
			time_diff = last_out_dt - first_in_dt
			row['working_hours'] = round(time_diff.total_seconds() / 3600, 2)
		else:
			row['working_hours'] = None  # Show as empty instead of 0.0

		# Calculate late arrival
		if row.get('first_in') and row.get('shift_start'):
			first_in_dt = get_datetime(row['first_in'])
			shift_start_dt = get_datetime(str(row['date']) + ' ' + str(row['shift_start']))

			if first_in_dt > shift_start_dt:
				late_diff = first_in_dt - shift_start_dt
				hours = int(late_diff.total_seconds() // 3600)
				minutes = int((late_diff.total_seconds() % 3600) // 60)
				row['late_by'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
			else:
				row['late_by'] = "On Time"
		elif not row.get('first_in'):
			row['late_by'] = "No Check-in"  # Indicate missing check-in

		# Calculate early exit (only if last_out exists)
		if row.get('last_out') and row.get('shift_end'):
			last_out_dt = get_datetime(row['last_out'])
			shift_end_dt = get_datetime(str(row['date']) + ' ' + str(row['shift_end']))

			if last_out_dt < shift_end_dt:
				early_diff = shift_end_dt - last_out_dt
				hours = int(early_diff.total_seconds() // 3600)
				minutes = int((early_diff.total_seconds() % 3600) // 60)
				row['early_exit_by'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
			else:
				row['early_exit_by'] = "On Time"
		elif not row.get('last_out'):
			row['early_exit_by'] = "No Checkout"  # Indicate missing checkout

		# Compute final status based on Attendance record (created after approval)
		# Priority: Attendance status > Regularization status > Computed status
		if row.get('attendance_status'):
			# Attendance record exists (created after Regularization approval)
			# Keep the attendance_status as-is (Present, Absent, Half Day, On Leave, etc.)
			pass
		elif row.get('regularization'):
			# Regularization exists but no Attendance yet
			# Map regularization status to a meaningful final status
			reg_status = row.get('regularization_status', '')
			if reg_status == 'Approved':
				row['attendance_status'] = 'Approved (Pending Attendance)'
			elif reg_status == 'Pending':
				row['attendance_status'] = 'Pending Approval'
			elif reg_status == 'Rejected':
				row['attendance_status'] = 'Rejected'
			else:
				row['attendance_status'] = reg_status
		else:
			# No regularization exists - compute status based on issues
			has_issues = False
			issues = []

			# Check for late arrival
			if row.get('late_by') and row.get('late_by') not in ("On Time", "No Check-in"):
				has_issues = True
				issues.append("Late")

			# Check for missing check-in
			if row.get('late_by') == "No Check-in":
				has_issues = True
				issues.append("No Check-in")

			# Check for early exit
			if row.get('early_exit_by') and row.get('early_exit_by') not in ("On Time", "No Checkout"):
				has_issues = True
				issues.append("Early Exit")

			# Check for no checkout
			if row.get('early_exit_by') == "No Checkout":
				has_issues = True
				issues.append("No Checkout")

			# Set computed status
			if has_issues:
				row['regularization_status'] = "Needs Review"
				row['attendance_status'] = "Needs Review"
			else:
				row['regularization_status'] = "OK"
				row['attendance_status'] = "OK"

	return data


def get_conditions(filters):
	"""Build SQL conditions based on filters"""
	conditions = []
	
	if filters.get("from_date"):
		conditions.append("DATE(ec.time) >= %(from_date)s")
	
	if filters.get("to_date"):
		conditions.append("DATE(ec.time) <= %(to_date)s")
	
	if filters.get("employee"):
		conditions.append("ec.employee = %(employee)s")
	
	if filters.get("department"):
		conditions.append("emp.department = %(department)s")
	
	if filters.get("designation"):
		conditions.append("emp.designation = %(designation)s")
	
	if filters.get("shift"):
		conditions.append("sa.shift_type = %(shift)s")
	
	if filters.get("log_type"):
		conditions.append("ec.log_type = %(log_type)s")
	
	if filters.get("device_id"):
		conditions.append("ec.device_id = %(device_id)s")
	
	if filters.get("show_only_late"):
		conditions.append("""
			EXISTS (
				SELECT 1 FROM `tabEmployee Checkin` ec2
				INNER JOIN `tabShift Assignment` sa2 ON sa2.employee = ec2.employee 
					AND sa2.docstatus = 1 
					AND sa2.start_date <= DATE(ec2.time)
					AND (sa2.end_date IS NULL OR sa2.end_date >= DATE(ec2.time))
				INNER JOIN `tabShift Type` st2 ON st2.name = sa2.shift_type
				WHERE ec2.employee = ec.employee
					AND DATE(ec2.time) = DATE(ec.time)
					AND ec2.log_type = 'IN'
					AND TIME(ec2.time) > st2.start_time
			)
		""")
	
	if filters.get("show_only_with_regularization"):
		conditions.append("ar.name IS NOT NULL")
	
	return " AND " + " AND ".join(conditions) if conditions else ""

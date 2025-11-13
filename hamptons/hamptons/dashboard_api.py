# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import now_datetime, get_datetime, getdate, add_days, formatdate, get_time_str


@frappe.whitelist()
def get_checkin_dashboard_data(date=None):
	"""
	Get comprehensive check-in data for the dashboard

	Args:
		date: Date to get data for (defaults to today)

	Returns:
		Dictionary with dashboard data
	"""
	# Check if Attendance Regularization DocType exists on this site
	if not frappe.db.exists("DocType", "Attendance Regularization"):
		frappe.throw(_("Attendance Regularization DocType is not installed on this site"))

	if not date:
		date = getdate()
	else:
		date = getdate(date)

	# Get today's check-ins with employee details
	checkins_today = frappe.db.sql("""
		SELECT 
			ec.name,
			ec.employee,
			ec.employee_name,
			emp.department,
			ec.time,
			ec.log_type,
			ec.device_id,
			ec.shift,
			sa.shift_type,
			st.start_time,
			st.end_time
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		LEFT JOIN `tabShift Assignment` sa ON sa.employee = ec.employee 
			AND sa.docstatus = 1 
			AND sa.start_date <= DATE(ec.time)
			AND (sa.end_date IS NULL OR sa.end_date >= DATE(ec.time))
		LEFT JOIN `tabShift Type` st ON st.name = sa.shift_type
		WHERE DATE(ec.time) = %s
		ORDER BY ec.time DESC
		LIMIT 50
	""", (date,), as_dict=1)
	
	# Get summary stats
	summary = frappe.db.sql("""
		SELECT 
			COUNT(DISTINCT employee) as total_employees,
			COUNT(*) as total_checkins,
			SUM(CASE WHEN log_type = 'IN' THEN 1 ELSE 0 END) as total_in,
			SUM(CASE WHEN log_type = 'OUT' THEN 1 ELSE 0 END) as total_out
		FROM `tabEmployee Checkin`
		WHERE DATE(time) = %s
	""", (date,), as_dict=1)[0]
	
	# Get department-wise breakdown
	dept_breakdown = frappe.db.sql("""
		SELECT 
			emp.department,
			COUNT(DISTINCT ec.employee) as employee_count,
			COUNT(*) as checkin_count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE DATE(ec.time) = %s
		GROUP BY emp.department
		ORDER BY checkin_count DESC
	""", (date,), as_dict=1)
	
	# Get pending regularizations
	pending_regularizations = frappe.db.sql("""
		SELECT 
			name,
			employee,
			employee_name,
			posting_date,
			late,
			status,
			shift
		FROM `tabAttendance Regularization`
		WHERE status = 'Open'
		ORDER BY posting_date DESC, late DESC
		LIMIT 10
	""", as_dict=1)
	
	# Get late arrivals today
	late_arrivals = frappe.db.sql("""
		SELECT 
			ec.employee,
			ec.employee_name,
			emp.department,
			ec.time,
			st.start_time,
			TIMEDIFF(TIME(ec.time), st.start_time) as late_by
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		INNER JOIN `tabShift Assignment` sa ON sa.employee = ec.employee 
			AND sa.docstatus = 1 
			AND sa.start_date <= DATE(ec.time)
			AND (sa.end_date IS NULL OR sa.end_date >= DATE(ec.time))
		INNER JOIN `tabShift Type` st ON st.name = sa.shift_type
		WHERE DATE(ec.time) = %s
			AND ec.log_type = 'IN'
			AND TIME(ec.time) > st.start_time
		ORDER BY late_by DESC
		LIMIT 10
	""", (date,), as_dict=1)
	
	# Format the data
	for checkin in checkins_today:
		checkin['time_formatted'] = formatdate(checkin['time'], "dd MMM yyyy hh:mm a")
		checkin['time_only'] = get_time_str(checkin['time'])
		
		# Calculate if late/early
		if checkin.get('start_time') and checkin.get('log_type') == 'IN':
			checkin_time = get_datetime(checkin['time']).time()
			if checkin_time > checkin['start_time']:
				diff = get_datetime(checkin['time']) - get_datetime(str(getdate(checkin['time'])) + ' ' + str(checkin['start_time']))
				hours = int(diff.total_seconds() // 3600)
				minutes = int((diff.total_seconds() % 3600) // 60)
				checkin['late_by'] = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
				checkin['is_late'] = True
	
	return {
		"date": date,
		"date_formatted": formatdate(date, "dd MMM yyyy"),
		"summary": summary,
		"checkins_today": checkins_today,
		"dept_breakdown": dept_breakdown,
		"pending_regularizations": pending_regularizations,
		"late_arrivals": late_arrivals
	}


@frappe.whitelist()
def get_employee_checkin_details(employee, from_date=None, to_date=None):
	"""
	Get detailed check-in information for a specific employee

	Args:
		employee: Employee ID
		from_date: Start date (defaults to 7 days ago)
		to_date: End date (defaults to today)

	Returns:
		Dictionary with employee check-in details
	"""
	# Check if Attendance Regularization DocType exists on this site
	if not frappe.db.exists("DocType", "Attendance Regularization"):
		frappe.throw(_("Attendance Regularization DocType is not installed on this site"))

	if not from_date:
		from_date = add_days(getdate(), -7)
	else:
		from_date = getdate(from_date)
	
	if not to_date:
		to_date = getdate()
	else:
		to_date = getdate(to_date)
	
	# Get employee info
	employee_info = frappe.db.get_value("Employee", employee, 
		["employee_name", "department", "designation", "attendance_device_id"], 
		as_dict=1)
	
	# Get check-ins
	checkins = frappe.db.sql("""
		SELECT 
			ec.name,
			ec.time,
			ec.log_type,
			ec.device_id,
			ec.shift,
			DATE(ec.time) as date,
			ar.name as regularization,
			ar.status as regularization_status
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabAttendance Regularization` ar ON ar.employee = ec.employee 
			AND ar.posting_date = DATE(ec.time)
		WHERE ec.employee = %s
			AND DATE(ec.time) BETWEEN %s AND %s
		ORDER BY ec.time DESC
	""", (employee, from_date, to_date), as_dict=1)
	
	# Group by date
	checkins_by_date = {}
	for checkin in checkins:
		date_key = str(checkin['date'])
		if date_key not in checkins_by_date:
			checkins_by_date[date_key] = {
				'date': checkin['date'],
				'date_formatted': formatdate(checkin['date'], "dd MMM yyyy"),
				'checkins': []
			}
		checkins_by_date[date_key]['checkins'].append({
			'name': checkin['name'],
			'time': checkin['time'],
			'time_formatted': get_time_str(checkin['time']),
			'log_type': checkin['log_type'],
			'device_id': checkin['device_id'],
			'shift': checkin['shift'],
			'regularization': checkin['regularization'],
			'regularization_status': checkin['regularization_status']
		})
	
	return {
		"employee": employee,
		"employee_info": employee_info,
		"from_date": from_date,
		"to_date": to_date,
		"checkins_by_date": list(checkins_by_date.values())
	}


@frappe.whitelist()
def get_device_usage_stats(from_date=None, to_date=None):
	"""
	Get statistics on device/location usage for check-ins
	
	Args:
		from_date: Start date (defaults to today)
		to_date: End date (defaults to today)
	
	Returns:
		List of device usage statistics
	"""
	if not from_date:
		from_date = getdate()
	else:
		from_date = getdate(from_date)
	
	if not to_date:
		to_date = getdate()
	else:
		to_date = getdate(to_date)
	
	device_stats = frappe.db.sql("""
		SELECT 
			device_id,
			COUNT(*) as total_checkins,
			COUNT(DISTINCT employee) as unique_employees,
			SUM(CASE WHEN log_type = 'IN' THEN 1 ELSE 0 END) as check_ins,
			SUM(CASE WHEN log_type = 'OUT' THEN 1 ELSE 0 END) as check_outs
		FROM `tabEmployee Checkin`
		WHERE DATE(time) BETWEEN %s AND %s
			AND device_id IS NOT NULL
		GROUP BY device_id
		ORDER BY total_checkins DESC
	""", (from_date, to_date), as_dict=1)
	
	return device_stats

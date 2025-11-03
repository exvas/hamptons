# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt, getdate, add_days, now_datetime
import json


@frappe.whitelist()
def get_analytics_data(filters):
	"""Get comprehensive analytics data for employee check-ins"""
	
	if isinstance(filters, str):
		filters = json.loads(filters)
	
	from_date = filters.get('from_date')
	to_date = filters.get('to_date')
	employee = filters.get('employee')
	department = filters.get('department')
	
	# Build filter conditions
	conditions = ["ec.time BETWEEN %(from_date)s AND %(to_date)s"]
	values = {'from_date': from_date, 'to_date': to_date}
	
	if employee:
		conditions.append("ec.employee = %(employee)s")
		values['employee'] = employee
	
	if department:
		conditions.append("emp.department = %(department)s")
		values['department'] = department
	
	where_clause = " AND ".join(conditions)
	
	return {
		'summary': get_summary_stats(where_clause, values),
		'daily_trend': get_daily_trend(where_clause, values),
		'checkin_type': get_checkin_type_distribution(where_clause, values),
		'hourly_distribution': get_hourly_distribution(where_clause, values),
		'department_wise': get_department_wise_stats(where_clause, values),
		'top_employees': get_top_employees(where_clause, values),
		'device_usage': get_device_usage(where_clause, values)
	}


def get_summary_stats(where_clause, values):
	"""Get summary statistics"""
	
	query = f"""
		SELECT 
			COUNT(*) as total_checkins,
			COUNT(DISTINCT ec.employee) as unique_employees,
			COUNT(DISTINCT ec.device_id) as total_devices
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause}
	"""
	
	result = frappe.db.sql(query, values, as_dict=True)
	stats = result[0] if result else {}
	
	# Calculate average daily check-ins
	from_date = getdate(values['from_date'])
	to_date = getdate(values['to_date'])
	days = (to_date - from_date).days + 1
	
	avg_daily = flt(stats.get('total_checkins', 0)) / days if days > 0 else 0
	
	# Calculate change from previous period
	prev_from = add_days(from_date, -days)
	prev_to = add_days(from_date, -1)
	
	prev_query = f"""
		SELECT COUNT(*) as prev_count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE ec.time BETWEEN %(prev_from)s AND %(prev_to)s
	"""
	
	if values.get('employee'):
		prev_query += " AND ec.employee = %(employee)s"
	if values.get('department'):
		prev_query += " AND emp.department = %(department)s"
	
	prev_values = values.copy()
	prev_values.update({'prev_from': prev_from, 'prev_to': prev_to})
	
	prev_result = frappe.db.sql(prev_query, prev_values, as_dict=True)
	prev_count = prev_result[0].get('prev_count', 0) if prev_result else 0
	
	change_percentage = 0
	if prev_count > 0:
		change_percentage = round(((stats.get('total_checkins', 0) - prev_count) / prev_count) * 100, 1)
	
	return {
		'total_checkins': stats.get('total_checkins', 0),
		'unique_employees': stats.get('unique_employees', 0),
		'total_devices': stats.get('total_devices', 0),
		'avg_daily_checkins': round(avg_daily, 1),
		'change_percentage': change_percentage
	}


def get_daily_trend(where_clause, values):
	"""Get daily check-in trend"""
	
	query = f"""
		SELECT 
			DATE(ec.time) as date,
			COUNT(*) as count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause}
		GROUP BY DATE(ec.time)
		ORDER BY date
	"""
	
	return frappe.db.sql(query, values, as_dict=True)


def get_checkin_type_distribution(where_clause, values):
	"""Get check-in vs check-out distribution"""
	
	query = f"""
		SELECT 
			ec.log_type,
			COUNT(*) as count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause}
		GROUP BY ec.log_type
	"""
	
	return frappe.db.sql(query, values, as_dict=True)


def get_hourly_distribution(where_clause, values):
	"""Get hourly distribution of check-ins"""
	
	query = f"""
		SELECT 
			HOUR(ec.time) as hour,
			COUNT(*) as count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause}
		GROUP BY HOUR(ec.time)
		ORDER BY hour
	"""
	
	return frappe.db.sql(query, values, as_dict=True)


def get_department_wise_stats(where_clause, values):
	"""Get department-wise check-in statistics"""
	
	query = f"""
		SELECT 
			emp.department,
			COUNT(*) as count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause}
		GROUP BY emp.department
		ORDER BY count DESC
		LIMIT 10
	"""
	
	return frappe.db.sql(query, values, as_dict=True)


def get_top_employees(where_clause, values):
	"""Get top employees by check-in count"""
	
	query = f"""
		SELECT 
			ec.employee,
			emp.employee_name,
			emp.department,
			SUM(CASE WHEN ec.log_type = 'IN' THEN 1 ELSE 0 END) as check_ins,
			SUM(CASE WHEN ec.log_type = 'OUT' THEN 1 ELSE 0 END) as check_outs,
			COUNT(*) as total
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause}
		GROUP BY ec.employee, emp.employee_name, emp.department
		ORDER BY total DESC
		LIMIT 10
	"""
	
	return frappe.db.sql(query, values, as_dict=True)


def get_device_usage(where_clause, values):
	"""Get device usage statistics"""
	
	query = f"""
		SELECT 
			ec.device_id,
			COUNT(*) as count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause} AND ec.device_id IS NOT NULL
		GROUP BY ec.device_id
		ORDER BY count DESC
		LIMIT 10
	"""
	
	return frappe.db.sql(query, values, as_dict=True)


@frappe.whitelist()
def export_to_excel(filters):
	"""Export analytics data to Excel"""
	
	if isinstance(filters, str):
		filters = json.loads(filters)
	
	from frappe.utils.xlsxutils import make_xlsx
	
	# Get data
	from_date = filters.get('from_date')
	to_date = filters.get('to_date')
	employee = filters.get('employee')
	department = filters.get('department')
	
	conditions = ["time BETWEEN %(from_date)s AND %(to_date)s"]
	values = {'from_date': from_date, 'to_date': to_date}
	
	if employee:
		conditions.append("ec.employee = %(employee)s")
		values['employee'] = employee
	
	if department:
		conditions.append("ec.employee IN (SELECT name FROM `tabEmployee` WHERE department = %(department)s)")
		values['department'] = department
	
	where_clause = " AND ".join(conditions)
	
	data = frappe.db.sql(f"""
		SELECT 
			ec.time,
			ec.employee,
			emp.employee_name,
			emp.department,
			emp.designation,
			ec.log_type,
			ec.device_id,
			ec.skip_auto_attendance
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE {where_clause}
		ORDER BY ec.time DESC
	""", values, as_dict=True)
	
	# Prepare data for Excel
	rows = [['Time', 'Employee ID', 'Employee Name', 'Department', 'Designation', 'Type', 'Device ID', 'Skip Auto Attendance']]
	
	for d in data:
		rows.append([
			str(d.get('time', '')),
			d.get('employee', ''),
			d.get('employee_name', ''),
			d.get('department', ''),
			d.get('designation', ''),
			d.get('log_type', ''),
			d.get('device_id', ''),
			d.get('skip_auto_attendance', 0)
		])
	
	# Create Excel file
	xlsx_file = make_xlsx(rows, "Employee Checkin Analytics")
	
	# Save file
	from frappe.utils.file_manager import save_file
	
	file_doc = save_file(
		fname=f"Employee_Checkin_Analytics_{from_date}_to_{to_date}.xlsx",
		content=xlsx_file.getvalue(),
		dt="Page",
		dn="employee-checkin-analytics",
		is_private=1
	)
	
	return {
		'file_url': file_doc.file_url
	}

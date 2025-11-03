# Copyright (c) 2024, Momscode and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate


def get_data():
	"""
	Get department-wise attendance for today
	Returns data for donut chart showing check-ins by department
	"""
	today = getdate()
	
	# Query to get check-ins grouped by department for today
	dept_data = frappe.db.sql("""
		SELECT 
			COALESCE(emp.department, 'Not Assigned') as department,
			COUNT(DISTINCT ec.employee) as employee_count
		FROM `tabEmployee Checkin` ec
		LEFT JOIN `tabEmployee` emp ON emp.name = ec.employee
		WHERE DATE(ec.time) = %s
		GROUP BY emp.department
		ORDER BY employee_count DESC
	""", (today,), as_dict=1)
	
	# Prepare data structure for chart
	labels = []
	values = []
	
	for dept in dept_data:
		labels.append(dept['department'] or 'Not Assigned')
		values.append(dept['employee_count'])
	
	return {
		"labels": labels,
		"datasets": [
			{
				"name": "Employees",
				"values": values
			}
		],
		"colors": ["#5E64FF", "#29CD42", "#FF5858", "#FFA00A", "#A463F2", "#FF6C37"]
	}
